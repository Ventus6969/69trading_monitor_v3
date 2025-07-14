#!/usr/bin/env python3
"""
監控主機數據庫初始化腳本
創建與交易主機完全相同的7表ML數據架構
=============================================================================
"""
import os
import sys
import sqlite3
import logging
from datetime import datetime

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/init_db.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def ensure_directories():
    """確保必要目錄存在"""
    directories = ['data', 'logs']
    for dir_name in directories:
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
            logger.info(f"創建目錄: {dir_name}")

def init_database():
    """初始化監控主機數據庫"""
    try:
        # 確保目錄存在
        ensure_directories()
        
        # 數據庫路徑
        db_path = "data/trading_signals.db"
        
        logger.info(f"開始初始化數據庫: {db_path}")
        
        # 如果數據庫已存在，備份
        if os.path.exists(db_path):
            backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.rename(db_path, backup_path)
            logger.info(f"現有數據庫已備份至: {backup_path}")
        
        # 創建新數據庫
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # 1. 創建 signals_received 表
            logger.info("創建 signals_received 表...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS signals_received (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    signal_type TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    open_price REAL,
                    close_price REAL,
                    prev_close REAL,
                    prev_open REAL,
                    atr_value REAL,
                    opposite INTEGER,
                    strategy_name TEXT,
                    quantity TEXT,
                    order_type TEXT,
                    margin_type TEXT,
                    precision INTEGER,
                    tp_multiplier REAL,
                    signal_data_json TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 2. 創建 orders_executed 表
            logger.info("創建 orders_executed 表...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS orders_executed (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_id INTEGER,
                    client_order_id TEXT UNIQUE NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    order_type TEXT,
                    quantity REAL,
                    price REAL,
                    leverage INTEGER,
                    execution_timestamp REAL,
                    execution_delay_ms INTEGER,
                    binance_order_id TEXT,
                    status TEXT DEFAULT 'NEW',
                    is_add_position BOOLEAN DEFAULT 0,
                    tp_client_id TEXT,
                    sl_client_id TEXT,
                    tp_price REAL,
                    sl_price REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (signal_id) REFERENCES signals_received (id)
                )
            ''')
            
            # 3. 創建 trading_results 表
            logger.info("創建 trading_results 表...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trading_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER,
                    client_order_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    final_pnl REAL,
                    pnl_percentage REAL,
                    holding_time_minutes INTEGER,
                    exit_method TEXT,
                    max_drawdown REAL,
                    max_profit REAL,
                    entry_price REAL,
                    exit_price REAL,
                    total_quantity REAL,
                    result_timestamp REAL,
                    is_successful BOOLEAN,
                    trade_quality_score REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (order_id) REFERENCES orders_executed (id)
                )
            ''')
            
            # 4. 創建 daily_stats 表
            logger.info("創建 daily_stats 表...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT UNIQUE NOT NULL,
                    total_signals INTEGER DEFAULT 0,
                    total_orders INTEGER DEFAULT 0,
                    successful_trades INTEGER DEFAULT 0,
                    failed_trades INTEGER DEFAULT 0,
                    win_rate REAL DEFAULT 0,
                    total_pnl REAL DEFAULT 0,
                    best_trade REAL DEFAULT 0,
                    worst_trade REAL DEFAULT 0,
                    avg_holding_time REAL DEFAULT 0,
                    signal_type_stats TEXT,
                    symbol_stats TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 5. 創建 ml_features_v2 表 (36個特徵)
            logger.info("創建 ml_features_v2 表...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ml_features_v2 (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    signal_id INTEGER,
                    
                    -- 信號品質核心特徵 (15個)
                    strategy_win_rate_recent REAL DEFAULT 0.0,
                    strategy_win_rate_overall REAL DEFAULT 0.0,
                    strategy_market_fitness REAL DEFAULT 0.0,
                    volatility_match_score REAL DEFAULT 0.0,
                    time_slot_match_score REAL DEFAULT 0.0,
                    symbol_match_score REAL DEFAULT 0.0,
                    price_momentum_strength REAL DEFAULT 0.0,
                    atr_relative_position REAL DEFAULT 0.0,
                    risk_reward_ratio REAL DEFAULT 0.0,
                    execution_difficulty REAL DEFAULT 0.0,
                    consecutive_win_streak INTEGER DEFAULT 0,
                    consecutive_loss_streak INTEGER DEFAULT 0,
                    system_overall_performance REAL DEFAULT 0.0,
                    signal_confidence_score REAL DEFAULT 0.0,
                    market_condition_fitness REAL DEFAULT 0.0,
                    
                    -- 價格關係特徵 (12個)
                    price_deviation_percent REAL DEFAULT 0.0,
                    price_deviation_abs REAL DEFAULT 0.0,
                    atr_normalized_deviation REAL DEFAULT 0.0,
                    candle_direction INTEGER DEFAULT 0,
                    candle_body_size REAL DEFAULT 0.0,
                    candle_wick_ratio REAL DEFAULT 0.0,
                    price_position_in_range REAL DEFAULT 0.0,
                    upward_adjustment_space REAL DEFAULT 0.0,
                    downward_adjustment_space REAL DEFAULT 0.0,
                    historical_best_adjustment REAL DEFAULT 0.0,
                    price_reachability_score REAL DEFAULT 0.0,
                    entry_price_quality_score REAL DEFAULT 0.0,
                    
                    -- 市場環境特徵 (9個)
                    hour_of_day INTEGER DEFAULT 0,
                    trading_session INTEGER DEFAULT 0,
                    weekend_factor INTEGER DEFAULT 0,
                    symbol_category INTEGER DEFAULT 0,
                    current_positions INTEGER DEFAULT 0,
                    margin_ratio REAL DEFAULT 0.0,
                    atr_normalized REAL DEFAULT 0.0,
                    volatility_regime INTEGER DEFAULT 0,
                    market_trend_strength REAL DEFAULT 0.0,
                    
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (signal_id) REFERENCES signals_received (id)
                )
            ''')
            
            # 6. 創建 ml_signal_quality 表
            logger.info("創建 ml_signal_quality 表...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ml_signal_quality (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    signal_id INTEGER,
                    decision_method TEXT DEFAULT 'RULE_BASED',
                    recommendation TEXT,
                    confidence_score REAL,
                    execution_probability REAL,
                    reason TEXT,
                    reasoning_details TEXT,
                    model_version TEXT DEFAULT 'v1.0',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (signal_id) REFERENCES signals_received (id)
                )
            ''')
            
            # 7. 創建 ml_price_optimization 表
            logger.info("創建 ml_price_optimization 表...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ml_price_optimization (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    signal_id INTEGER,
                    original_price REAL,
                    optimized_price REAL,
                    price_adjustment_percent REAL,
                    optimization_reason TEXT,
                    expected_improvement REAL,
                    confidence_level REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (signal_id) REFERENCES signals_received (id)
                )
            ''')
            
            # 創建索引
            logger.info("創建數據庫索引...")
            indexes = [
                'CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signals_received(timestamp)',
                'CREATE INDEX IF NOT EXISTS idx_signals_type_symbol ON signals_received(signal_type, symbol)',
                'CREATE INDEX IF NOT EXISTS idx_orders_client_id ON orders_executed(client_order_id)',
                'CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders_executed(symbol)',
                'CREATE INDEX IF NOT EXISTS idx_results_timestamp ON trading_results(result_timestamp)',
                'CREATE INDEX IF NOT EXISTS idx_daily_stats_date ON daily_stats(date)',
                'CREATE INDEX IF NOT EXISTS idx_ml_features_signal_id ON ml_features_v2(signal_id)',
                'CREATE INDEX IF NOT EXISTS idx_ml_features_session_id ON ml_features_v2(session_id)',
                'CREATE INDEX IF NOT EXISTS idx_ml_quality_signal_id ON ml_signal_quality(signal_id)',
                'CREATE INDEX IF NOT EXISTS idx_ml_price_signal_id ON ml_price_optimization(signal_id)',
            ]
            
            for index_sql in indexes:
                cursor.execute(index_sql)
            
            # 提交所有更改
            conn.commit()
            logger.info("所有表格和索引創建完成")
            
        # 驗證表格創建
        verify_tables(db_path)
        
        logger.info("✅ 監控主機數據庫初始化完成")
        return True
        
    except Exception as e:
        logger.error(f"❌ 數據庫初始化失敗: {str(e)}")
        return False

def verify_tables(db_path):
    """驗證表格是否正確創建"""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # 檢查所有表格
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            expected_tables = [
                'signals_received', 'orders_executed', 'trading_results', 
                'daily_stats', 'ml_features_v2', 'ml_signal_quality', 
                'ml_price_optimization'
            ]
            
            logger.info("=== 數據庫表格驗證 ===")
            for table in expected_tables:
                if table in tables:
                    # 檢查表格結構
                    cursor.execute(f"PRAGMA table_info({table})")
                    columns = cursor.fetchall()
                    logger.info(f"✅ {table} - {len(columns)} 欄位")
                else:
                    logger.error(f"❌ {table} - 表格缺失")
            
            # 檢查ML特徵表的欄位數
            cursor.execute("PRAGMA table_info(ml_features_v2)")
            ml_columns = cursor.fetchall()
            feature_columns = [col for col in ml_columns if col[1] not in ['id', 'session_id', 'signal_id', 'created_at']]
            logger.info(f"📊 ML特徵表包含 {len(feature_columns)} 個特徵欄位")
            
        return True
        
    except Exception as e:
        logger.error(f"表格驗證失敗: {str(e)}")
        return False

def main():
    """主函數"""
    logger.info("=== 監控主機數據庫初始化開始 ===")
    
    try:
        success = init_database()
        if success:
            logger.info("=== 數據庫初始化成功完成 ===")
            print("\n✅ 監控主機數據庫初始化完成")
            print("📊 7表ML數據架構已建立")
            print("🎯 可以進行下一步：測試ML模組")
        else:
            logger.error("=== 數據庫初始化失敗 ===")
            print("\n❌ 數據庫初始化失敗")
            print("📝 請檢查 logs/init_db.log 獲取詳細信息")
            
    except Exception as e:
        logger.error(f"主函數執行錯誤: {str(e)}")
        print(f"\n❌ 執行錯誤: {str(e)}")

if __name__ == "__main__":
    main()
