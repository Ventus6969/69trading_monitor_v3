#!/usr/bin/env python3
"""
69交易機器人監控系統 v3.2 - 完整版 with 圖表
包含數據顯示、同步監控、API接口、圖表可視化
"""
from flask import Flask, render_template, jsonify
from datetime import datetime
import logging
import os
import sqlite3
import json
import subprocess
import plotly.graph_objects as go
import plotly.express as px
from plotly.utils import PlotlyJSONEncoder

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'trading-monitor-v3-secret-key'

DB_PATH = "data/trading_signals.db"
SYNC_STATE_FILE = "data/sync_state.json"

@app.route('/')
def dashboard():
    """主儀表板頁面"""
    try:
        basic_stats = get_basic_stats_simple()
        recent_signals = get_recent_signals_simple(5)
        
        return render_template('dashboard.html', 
                             basic_stats=basic_stats,
                             recent_signals=recent_signals,
                             db_status="connected",
                             db_path=DB_PATH,
                             db_exists=os.path.exists(DB_PATH),
                             last_updated=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                             
    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}")
        return render_template('dashboard.html', 
                             basic_stats=get_empty_stats(),
                             recent_signals=[],
                             db_status="error",
                             db_path=DB_PATH,
                             db_exists=os.path.exists(DB_PATH),
                             last_updated=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                             error=str(e))

@app.route('/api/health')
def health():
    """健康檢查API"""
    return jsonify({
        'status': 'healthy',
        'version': 'v3.2',
        'database_exists': os.path.exists(DB_PATH),
        'database_path': DB_PATH,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/stats')
def api_stats():
    """統計數據API"""
    try:
        stats = get_basic_stats_simple()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/sync')
def manual_sync():
    """手動同步數據API"""
    try:
        result = subprocess.run(['python', 'smart_sync.py'], 
                              capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            return jsonify({'status': 'success', 'message': '同步成功'})
        else:
            return jsonify({'status': 'error', 'message': f'同步失敗: {result.stderr}'})
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/sync-status')
def sync_status():
    """同步狀態API"""
    try:
        if os.path.exists(SYNC_STATE_FILE):
            with open(SYNC_STATE_FILE, 'r') as f:
                sync_state = json.load(f)
            
            return jsonify({
                'status': 'available',
                'last_sync_time': sync_state.get('last_sync_time'),
                'sync_count': sync_state.get('sync_count', 0),
                'last_size': sync_state.get('last_size', 0),
                'database_size_kb': round(os.path.getsize(DB_PATH) / 1024, 1) if os.path.exists(DB_PATH) else 0
            })
        else:
            return jsonify({
                'status': 'no_sync_yet',
                'message': '尚未進行過同步'
            })
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/chart/win-rate-trend')
def win_rate_trend_chart():
    """勝率趨勢圖API"""
    try:
        chart_data = get_win_rate_trend_data()
        return jsonify(chart_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/chart/strategy-performance')
def strategy_performance_chart():
    """策略表現對比圖API"""
    try:
        chart_data = get_strategy_performance_data()
        return jsonify(chart_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/chart/pnl-distribution')
def pnl_distribution_chart():
    """盈虧分布圖API"""
    try:
        chart_data = get_pnl_distribution_data()
        return jsonify(chart_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/charts')
def charts_page():
    """圖表頁面"""
    return render_template('charts.html')

@app.route('/api/detailed-records')
def detailed_records():
    """詳細交易記錄API"""
    try:
        records = get_detailed_trading_records()
        return jsonify(records)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_basic_stats_simple():
    """直接使用SQL獲取統計數據"""
    if not os.path.exists(DB_PATH):
        return get_empty_stats()
        
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # 檢查表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            logger.info(f"數據庫表: {tables}")
            
            stats = {}
            
            # 基本統計
            if 'signals_received' in tables:
                cursor.execute('SELECT COUNT(*) FROM signals_received')
                stats['total_signals'] = cursor.fetchone()[0]
                
                cursor.execute('SELECT MAX(timestamp) FROM signals_received')
                last_signal = cursor.fetchone()[0]
                if last_signal:
                    stats['last_signal_time'] = datetime.fromtimestamp(last_signal).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    stats['last_signal_time'] = '無'
            else:
                stats['total_signals'] = 0
                stats['last_signal_time'] = '無'
            
            if 'orders_executed' in tables:
                cursor.execute('SELECT COUNT(*) FROM orders_executed')
                stats['total_orders'] = cursor.fetchone()[0]
            else:
                stats['total_orders'] = 0
            
            if 'trading_results' in tables:
                cursor.execute('SELECT COUNT(*) FROM trading_results')
                stats['total_results'] = cursor.fetchone()[0]
                
                # 計算勝率和盈虧
                cursor.execute('SELECT COUNT(*) FROM trading_results WHERE is_successful = 1')
                successful = cursor.fetchone()[0]
                
                cursor.execute('SELECT SUM(final_pnl) FROM trading_results')
                total_pnl = cursor.fetchone()[0] or 0
                
                if stats['total_results'] > 0:
                    stats['overall_win_rate'] = round((successful / stats['total_results']) * 100, 1)
                else:
                    stats['overall_win_rate'] = 0
                    
                stats['total_pnl'] = round(total_pnl, 4)
            else:
                stats['total_results'] = 0
                stats['overall_win_rate'] = 0
                stats['total_pnl'] = 0
            
            # ML表統計
            if 'ml_features_v2' in tables:
                cursor.execute('SELECT COUNT(*) FROM ml_features_v2')
                stats['total_ml_features'] = cursor.fetchone()[0]
            else:
                stats['total_ml_features'] = 0
                
            if 'ml_signal_quality' in tables:
                cursor.execute('SELECT COUNT(*) FROM ml_signal_quality')
                stats['total_ml_predictions'] = cursor.fetchone()[0]
            else:
                stats['total_ml_predictions'] = 0
            
            # 執行率
            if stats['total_orders'] > 0 and stats['total_results'] > 0:
                stats['execution_rate'] = round((stats['total_results'] / stats['total_orders']) * 100, 1)
            else:
                stats['execution_rate'] = 0
            
            # 數據庫大小
            stats['database_size_kb'] = round(os.path.getsize(DB_PATH) / 1024, 1)
            
            logger.info(f"統計結果: {stats}")
            return stats
            
    except Exception as e:
        logger.error(f"獲取統計數據錯誤: {str(e)}")
        return get_empty_stats()

def get_recent_signals_simple(limit=5):
    """直接使用SQL獲取最近信號"""
    if not os.path.exists(DB_PATH):
        return []
        
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT timestamp, symbol, side, signal_type, opposite 
                FROM signals_received 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (limit,))
            
            results = []
            for row in cursor.fetchall():
                timestamp, symbol, side, signal_type, opposite = row
                results.append({
                    'timestamp': datetime.fromtimestamp(timestamp).strftime('%m-%d %H:%M'),
                    'symbol': symbol,
                    'side': side,
                    'signal_type': signal_type or 'N/A',
                    'opposite': opposite or 0
                })
                
            return results
            
    except Exception as e:
        logger.error(f"獲取最近信號錯誤: {str(e)}")
        return []

def get_empty_stats():
    """返回空統計數據"""
    return {
        'total_signals': 0,
        'total_orders': 0, 
        'total_results': 0,
        'total_ml_features': 0,
        'total_ml_predictions': 0,
        'overall_win_rate': 0,
        'total_pnl': 0,
        'execution_rate': 0,
        'last_signal_time': '無',
        'database_size_kb': 0
    }

def get_win_rate_trend_data():
    """獲取勝率趨勢數據"""
    if not os.path.exists(DB_PATH):
        return {'data': [], 'layout': {}}
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # 按日期統計勝率
            cursor.execute('''
                SELECT 
                    DATE(datetime(r.result_timestamp, 'unixepoch')) as trade_date,
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN r.is_successful = 1 THEN 1 ELSE 0 END) as successful_trades
                FROM trading_results r
                GROUP BY trade_date
                ORDER BY trade_date
            ''')
            
            rows = cursor.fetchall()
            
            if not rows:
                return {'data': [], 'layout': {'title': '勝率趨勢 - 暫無數據'}}
            
            dates = []
            win_rates = []
            trade_counts = []
            
            for row in rows:
                trade_date, total_trades, successful_trades = row
                win_rate = (successful_trades / total_trades * 100) if total_trades > 0 else 0
                
                dates.append(trade_date)
                win_rates.append(round(win_rate, 1))
                trade_counts.append(total_trades)
            
            # 創建Plotly圖表
            fig = go.Figure()
            
            # 添加勝率線
            fig.add_trace(go.Scatter(
                x=dates,
                y=win_rates,
                mode='lines+markers',
                name='勝率 (%)',
                line=dict(color='#28a745', width=3),
                marker=dict(size=8)
            ))
            
            # 添加交易次數（右Y軸）
            fig.add_trace(go.Bar(
                x=dates,
                y=trade_counts,
                name='交易次數',
                yaxis='y2',
                opacity=0.3,
                marker_color='#007bff'
            ))
            
            # 設置佈局
            fig.update_layout(
                title='每日勝率趨勢',
                xaxis_title='日期',
                yaxis=dict(title='勝率 (%)', side='left'),
                yaxis2=dict(title='交易次數', side='right', overlaying='y'),
                hovermode='x unified',
                template='plotly_white',
                height=400
            )
            
            return json.loads(fig.to_json())
            
    except Exception as e:
        logger.error(f"獲取勝率趨勢數據錯誤: {str(e)}")
        return {'data': [], 'layout': {'title': f'數據載入錯誤: {str(e)}'}}

def get_strategy_performance_data():
    """獲取策略表現數據"""
    if not os.path.exists(DB_PATH):
        return {'data': [], 'layout': {}}
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # 按策略統計表現
            cursor.execute('''
                SELECT 
                    s.signal_type,
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN r.is_successful = 1 THEN 1 ELSE 0 END) as successful_trades,
                    SUM(r.final_pnl) as total_pnl,
                    AVG(r.final_pnl) as avg_pnl
                FROM trading_results r
                JOIN orders_executed o ON r.order_id = o.id
                JOIN signals_received s ON o.signal_id = s.id
                GROUP BY s.signal_type
                ORDER BY total_trades DESC
            ''')
            
            rows = cursor.fetchall()
            
            if not rows:
                return {'data': [], 'layout': {'title': '策略表現 - 暫無數據'}}
            
            strategies = []
            win_rates = []
            total_pnls = []
            trade_counts = []
            
            for row in rows:
                signal_type, total_trades, successful_trades, total_pnl, avg_pnl = row
                win_rate = (successful_trades / total_trades * 100) if total_trades > 0 else 0
                
                strategies.append(signal_type or 'Unknown')
                win_rates.append(round(win_rate, 1))
                total_pnls.append(round(total_pnl or 0, 2))
                trade_counts.append(total_trades)
            
            # 創建雙軸圖表
            fig = go.Figure()
            
            # 勝率柱狀圖
            fig.add_trace(go.Bar(
                x=strategies,
                y=win_rates,
                name='勝率 (%)',
                marker_color='#28a745',
                yaxis='y'
            ))
            
            # 總盈虧線圖
            fig.add_trace(go.Scatter(
                x=strategies,
                y=total_pnls,
                mode='lines+markers',
                name='總盈虧 (USDT)',
                line=dict(color='#dc3545', width=3),
                marker=dict(size=10),
                yaxis='y2'
            ))
            
            # 設置佈局
            fig.update_layout(
                title='策略表現對比',
                xaxis_title='策略類型',
                yaxis=dict(title='勝率 (%)', side='left'),
                yaxis2=dict(title='總盈虧 (USDT)', side='right', overlaying='y'),
                template='plotly_white',
                height=400,
                hovermode='x unified'
            )
            
            return json.loads(fig.to_json())
            
    except Exception as e:
        logger.error(f"獲取策略表現數據錯誤: {str(e)}")
        return {'data': [], 'layout': {'title': f'數據載入錯誤: {str(e)}'}}

def get_pnl_distribution_data():
    """獲取盈虧分布數據"""
    if not os.path.exists(DB_PATH):
        return {'data': [], 'layout': {}}
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # 獲取所有交易的盈虧數據
            cursor.execute('''
                SELECT 
                    r.final_pnl,
                    r.is_successful,
                    s.signal_type,
                    r.symbol
                FROM trading_results r
                JOIN orders_executed o ON r.order_id = o.id
                JOIN signals_received s ON o.signal_id = s.id
                ORDER BY r.final_pnl
            ''')
            
            rows = cursor.fetchall()
            
            if not rows:
                return {'data': [], 'layout': {'title': '盈虧分布 - 暫無數據'}}
            
            pnls = []
            colors = []
            hover_texts = []
            
            for row in rows:
                final_pnl, is_successful, signal_type, symbol = row
                pnls.append(final_pnl)
                colors.append('#28a745' if is_successful else '#dc3545')
                hover_texts.append(f'{symbol}<br>{signal_type}<br>盈虧: {final_pnl:.2f} USDT')
            
            # 創建散點圖
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=list(range(len(pnls))),
                y=pnls,
                mode='markers',
                marker=dict(
                    color=colors,
                    size=10,
                    opacity=0.7
                ),
                text=hover_texts,
                hovertemplate='%{text}<extra></extra>',
                name='交易結果'
            ))
            
            # 添加零線
            fig.add_hline(y=0, line_dash="dash", line_color="gray", annotation_text="損益平衡線")
            
            # 設置佈局
            fig.update_layout(
                title='交易盈虧分布',
                xaxis_title='交易序號',
                yaxis_title='盈虧 (USDT)',
                template='plotly_white',
                height=400,
                showlegend=False
            )
            
            return json.loads(fig.to_json())
            
    except Exception as e:
        logger.error(f"獲取盈虧分布數據錯誤: {str(e)}")
        return {'data': [], 'layout': {'title': f'數據載入錯誤: {str(e)}'}}

def get_detailed_trading_records():
    """獲取詳細交易記錄"""
    if not os.path.exists(DB_PATH):
        return []
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    datetime(s.timestamp, 'unixepoch') as signal_time,
                    s.signal_type,
                    s.symbol,
                    s.side,
                    s.opposite,
                    o.price as entry_price,
                    o.quantity,
                    o.status as order_status,
                    r.final_pnl,
                    r.pnl_percentage,
                    r.exit_method,
                    r.holding_time_minutes,
                    r.is_successful
                FROM signals_received s
                LEFT JOIN orders_executed o ON s.id = o.signal_id
                LEFT JOIN trading_results r ON o.id = r.order_id
                ORDER BY s.timestamp DESC
            ''')
            
            results = []
            for row in cursor.fetchall():
                signal_time, signal_type, symbol, side, opposite, entry_price, quantity, order_status, final_pnl, pnl_percentage, exit_method, holding_time_minutes, is_successful = row
                
                results.append({
                    'signal_time': signal_time,
                    'signal_type': signal_type or 'N/A',
                    'symbol': symbol,
                    'side': side,
                    'opposite': opposite or 0,
                    'entry_price': entry_price or 0,
                    'quantity': quantity or 0,
                    'order_status': order_status or 'N/A',
                    'final_pnl': final_pnl or 0,
                    'pnl_percentage': pnl_percentage or 0,
                    'exit_method': exit_method or 'N/A',
                    'holding_time_minutes': holding_time_minutes or 0,
                    'is_successful': is_successful
                })
                
            return results
            
    except Exception as e:
        logger.error(f"獲取詳細交易記錄錯誤: {str(e)}")
        return []

if __name__ == '__main__':
    logger.info("69交易機器人監控系統 v3.2 啟動（完整版）")
    logger.info(f"數據庫路徑: {DB_PATH}")
    logger.info(f"數據庫存在: {os.path.exists(DB_PATH)}")
    app.run(host='0.0.0.0', port=5001, debug=True)
