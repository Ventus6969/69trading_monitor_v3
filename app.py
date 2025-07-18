#!/usr/bin/env python3
"""
69交易機器人監控系統 v3.2 - 帶登入認證
包含數據顯示、同步監控、API接口、登入認證
"""
from flask import Flask, render_template, jsonify, session
from datetime import datetime
import logging
import os
import sqlite3
import json
import subprocess

# 導入認證模組
from auth import setup_auth_routes, configure_session, login_required

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 配置session和認證
configure_session(app)
setup_auth_routes(app)

DB_PATH = "data/trading_signals.db"
SYNC_STATE_FILE = "data/sync_state.json"

@app.route('/')
@login_required
def dashboard():
    """主儀表板頁面 - 需要登入"""
    try:
        basic_stats = get_basic_stats_simple()
        recent_signals = get_recent_signals_simple(5)
        
        return render_template('dashboard.html', 
                             basic_stats=basic_stats,
                             recent_signals=recent_signals,
                             db_status="connected",
                             db_path=DB_PATH,
                             db_exists=os.path.exists(DB_PATH),
                             last_updated=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                             username=session.get('username', 'Unknown'),
                             login_time=session.get('login_time', ''))
                             
    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}")
        return render_template('dashboard.html', 
                             basic_stats=get_empty_stats(),
                             recent_signals=[],
                             db_status="error",
                             db_path=DB_PATH,
                             db_exists=os.path.exists(DB_PATH),
                             last_updated=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                             username=session.get('username', 'Unknown'),
                             login_time=session.get('login_time', ''),
                             error=str(e))

@app.route('/api/health')
def health():
    """健康檢查API - 無需登入"""
    return jsonify({
        'status': 'healthy',
        'version': 'v3.2',
        'database_exists': os.path.exists(DB_PATH),
        'database_path': DB_PATH,
        'timestamp': datetime.now().isoformat(),
        'auth_enabled': True
    })

@app.route('/api/stats')
@login_required
def api_stats():
    """統計數據API - 需要登入"""
    try:
        stats = get_basic_stats_simple()
        stats['user'] = session.get('username', 'Unknown')
        return jsonify(stats)
    except Exception as e:
        logger.error(f"API stats error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/sync')
@login_required
def api_sync():
    """手動同步API - 需要登入"""
    try:
        from smart_sync import sync_from_remote
        result = sync_from_remote()
        
        return jsonify({
            'success': True,
            'result': result,
            'timestamp': datetime.now().isoformat(),
            'triggered_by': session.get('username', 'Unknown')
        })
    except Exception as e:
        logger.error(f"Sync error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/signals')
@login_required
def api_signals():
    """信號數據API - 需要登入"""
    try:
        limit = int(request.args.get('limit', 10))
        signals = get_recent_signals_simple(limit)
        return jsonify({
            'signals': signals,
            'count': len(signals),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"API signals error: {str(e)}")
        return jsonify({'error': str(e)}), 500

def get_basic_stats_simple():
    """獲取基本統計信息 - 簡化版"""
    try:
        if not os.path.exists(DB_PATH):
            return get_empty_stats()
            
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # 基本統計
            cursor.execute("SELECT COUNT(*) FROM signals_received")
            total_signals = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM orders_executed")
            total_orders = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM trading_results WHERE is_successful = 1")
            successful_trades = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM trading_results WHERE is_successful = 0")
            failed_trades = cursor.fetchone()[0]
            
            cursor.execute("SELECT SUM(final_pnl) FROM trading_results WHERE final_pnl IS NOT NULL")
            total_pnl_result = cursor.fetchone()[0]
            total_pnl = total_pnl_result if total_pnl_result else 0.0
            
            # ML統計
            cursor.execute("SELECT COUNT(*) FROM ml_features_v2")
            ml_features_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM ml_signal_quality")
            ml_decisions_count = cursor.fetchone()[0]
            
            # 計算勝率
            total_trades = successful_trades + failed_trades
            win_rate = (successful_trades / total_trades * 100) if total_trades > 0 else 0
            
            return {
                'total_signals': total_signals,
                'total_orders': total_orders,
                'total_trades': total_trades,
                'successful_trades': successful_trades,
                'failed_trades': failed_trades,
                'win_rate': round(win_rate, 2),
                'total_pnl': round(total_pnl, 2),
                'ml_features_count': ml_features_count,
                'ml_decisions_count': ml_decisions_count,
                'ml_progress': round((ml_features_count / 50) * 100, 1) if ml_features_count <= 50 else 100
            }
            
    except Exception as e:
        logger.error(f"統計數據獲取錯誤: {str(e)}")
        return get_empty_stats()

def get_recent_signals_simple(limit=5):
    """獲取最近的信號 - 只顯示主要交易結果"""
    try:
        if not os.path.exists(DB_PATH):
            return []
            
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # 修改查詢：只取主訂單，並優先顯示交易結果
            cursor.execute("""
                SELECT 
                    sr.id, 
                    sr.signal_type, 
                    sr.symbol, 
                    sr.side, 
                    sr.timestamp,
                    CASE 
                        WHEN tr.exit_method IS NOT NULL THEN tr.exit_method
                        WHEN oe.status IS NOT NULL THEN oe.status
                        ELSE 'PENDING'
                    END as final_status,
                    COALESCE(tr.final_pnl, 0) as final_pnl,
                    tr.is_successful
                FROM signals_received sr
                LEFT JOIN orders_executed oe ON sr.id = oe.signal_id 
                    AND oe.client_order_id NOT LIKE '%T'  -- 排除止盈單
                    AND oe.client_order_id NOT LIKE '%S'  -- 排除止損單
                LEFT JOIN trading_results tr ON oe.id = tr.order_id
                ORDER BY sr.timestamp DESC
                LIMIT ?
            """, (limit,))
            
            results = []
            for row in cursor.fetchall():
                signal_id, signal_type, symbol, side, timestamp, final_status, final_pnl, is_successful = row
                
                # 轉換時間戳
                try:
                    dt = datetime.fromtimestamp(timestamp)
                    formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    formatted_time = str(timestamp)
                
                # 轉換狀態顯示 - 保持原有的TP/SL顯示
                if final_status == 'TAKE_PROFIT':
                    display_status = 'TP_FILLED'
                    result_icon = '✅'
                elif final_status == 'STOP_LOSS':
                    display_status = 'SL_FILLED' 
                    result_icon = '❌'
                elif final_status == 'FILLED':
                    display_status = 'FILLED'
                    result_icon = '✅' if is_successful else '❌'
                elif final_status == 'CANCELED':
                    display_status = 'CANCELED'
                    result_icon = '⏸️'
                else:
                    display_status = final_status
                    result_icon = '🔄'
                
                results.append({
                    'id': signal_id,
                    'signal_type': signal_type,
                    'symbol': symbol,
                    'side': side,
                    'timestamp': formatted_time,
                    'order_status': display_status,
                    'final_pnl': final_pnl,
                    'is_successful': is_successful,
                    'result_icon': result_icon
                })
                
            return results
            
    except Exception as e:
        logger.error(f"最近信號獲取錯誤: {str(e)}")
        return []
    
def get_empty_stats():
    """返回空統計數據"""
    return {
        'total_signals': 0,
        'total_orders': 0,
        'total_trades': 0,
        'successful_trades': 0,
        'failed_trades': 0,
        'win_rate': 0,
        'total_pnl': 0,
        'ml_features_count': 0,
        'ml_decisions_count': 0,
        'ml_progress': 0
    }

if __name__ == '__main__':
    # 確保資料夾存在
    os.makedirs('data', exist_ok=True)
    
    logger.info("="*60)
    logger.info("🚀 69交易機器人監控系統 v3.2 啟動")
    logger.info("📊 功能: 數據監控 + 智能同步 + 登入認證")
    logger.info("🔐 安全: Session認證 + CSRF保護")
    logger.info("🌐 訪問: http://localhost:5001")
    logger.info("👤 預設帳號: admin / trader")
    logger.info("="*60)
    
    # 啟動Flask應用 - 使用原來的5001端口
    app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)
