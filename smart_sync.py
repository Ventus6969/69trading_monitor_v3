#!/usr/bin/env python3
"""
智能數據同步系統 v3.2
"""
import os
import subprocess
import sqlite3
import logging
from datetime import datetime
import json

# 設置日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 🔥 修正：更新正確的交易主機路徑
REMOTE_HOST = "15.168.60.229"
REMOTE_USER = "ec2-user"
REMOTE_DB_PATH = "/home/ec2-user/69trading-clean/data/trading_signals.db"  # 修正路徑
LOCAL_DB_PATH = "data/trading_signals.db"
SSH_KEY_PATH = os.path.expanduser("~/.ssh/trading_monitor")
SYNC_STATE_FILE = "data/sync_state.json"

def check_remote_db_exists():
    """檢查遠程數據庫是否存在"""
    try:
        cmd = [
            'ssh', '-i', SSH_KEY_PATH,
            '-o', 'ConnectTimeout=5',
            '-o', 'StrictHostKeyChecking=no',
            f'{REMOTE_USER}@{REMOTE_HOST}',
            f'test -f {REMOTE_DB_PATH} && echo "EXISTS" || echo "NOT_EXISTS"'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return "EXISTS" in result.stdout
        return False
        
    except Exception as e:
        logger.error(f"檢查遠程數據庫失敗: {str(e)}")
        return False

def get_remote_db_info():
    """獲取遠程數據庫信息"""
    try:
        cmd = [
            'ssh', '-i', SSH_KEY_PATH,
            '-o', 'ConnectTimeout=5',
            '-o', 'StrictHostKeyChecking=no',
            f'{REMOTE_USER}@{REMOTE_HOST}',
            f'if [ -f {REMOTE_DB_PATH} ]; then stat -c"%s %Y" {REMOTE_DB_PATH}; else echo "0 0"; fi'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            size, mtime = result.stdout.strip().split()
            return int(size), int(mtime)
        return 0, 0
        
    except Exception as e:
        logger.error(f"獲取遠程數據庫信息失敗: {str(e)}")
        return 0, 0

def sync_database():
    """同步數據庫"""
    try:
        # 確保本地目錄存在
        os.makedirs(os.path.dirname(LOCAL_DB_PATH), exist_ok=True)
        
        # 檢查遠程數據庫
        if not check_remote_db_exists():
            return {'status': 'error', 'message': f'遠程數據庫不存在: {REMOTE_DB_PATH}'}
        
        # 獲取遠程信息
        remote_size, remote_mtime = get_remote_db_info()
        logger.info(f"遠程數據庫: {remote_size} bytes, 修改時間: {datetime.fromtimestamp(remote_mtime)}")
        
        # 檢查是否需要同步
        need_sync = True
        sync_reason = "初始同步"
        
        if os.path.exists(SYNC_STATE_FILE):
            with open(SYNC_STATE_FILE, 'r') as f:
                sync_state = json.load(f)
                
            last_size = sync_state.get('last_size', 0)
            last_mtime = sync_state.get('last_mtime', 0)
            
            if remote_size == last_size and remote_mtime == last_mtime:
                need_sync = False
                sync_reason = "數據無變化"
        
        if not need_sync:
            logger.info(f"🔍 {sync_reason}，跳過同步")
            return {'status': 'skipped', 'message': sync_reason}
        
        # 執行同步
        logger.info(f"🔄 開始同步: {sync_reason}")
        
        sync_cmd = [
            'scp', '-i', SSH_KEY_PATH,
            '-o', 'ConnectTimeout=10',
            '-o', 'StrictHostKeyChecking=no',
            f'{REMOTE_USER}@{REMOTE_HOST}:{REMOTE_DB_PATH}',
            LOCAL_DB_PATH
        ]
        
        result = subprocess.run(sync_cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            # 更新同步狀態
            sync_state = {
                'last_sync_time': datetime.now().isoformat(),
                'last_size': remote_size,
                'last_mtime': remote_mtime,
                'sync_count': sync_state.get('sync_count', 0) + 1 if os.path.exists(SYNC_STATE_FILE) else 1
            }
            
            with open(SYNC_STATE_FILE, 'w') as f:
                json.dump(sync_state, f, indent=2)
            
            # 驗證同步結果
            local_size = os.path.getsize(LOCAL_DB_PATH)
            logger.info(f"✅ 同步成功: {local_size} bytes")
            
            # 快速檢查數據
            record_count = check_database_records()
            
            return {
                'status': 'success',
                'message': f'同步成功，數據庫大小: {local_size} bytes，記錄數: {record_count}',
                'records': record_count,
                'size_bytes': local_size
            }
        else:
            logger.error(f"❌ SCP同步失敗: {result.stderr}")
            return {'status': 'error', 'message': f'同步失敗: {result.stderr}'}
            
    except Exception as e:
        logger.error(f"同步過程出錯: {str(e)}")
        return {'status': 'error', 'message': str(e)}

def check_database_records():
    """檢查數據庫記錄數"""
    try:
        if not os.path.exists(LOCAL_DB_PATH):
            return 0
            
        with sqlite3.connect(LOCAL_DB_PATH) as conn:
            cursor = conn.cursor()
            
            # 檢查主要表的記錄數
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            total_records = 0
            for table in ['signals_received', 'orders_executed', 'trading_results']:
                if table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    total_records += count
                    logger.info(f"  {table}: {count} 筆記錄")
            
            return total_records
            
    except Exception as e:
        logger.error(f"檢查數據庫記錄失敗: {str(e)}")
        return 0

def main():
    """主程式"""
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--status':
            # 顯示同步狀態
            if os.path.exists(SYNC_STATE_FILE):
                with open(SYNC_STATE_FILE, 'r') as f:
                    sync_state = json.load(f)
                print(f"📊 最後同步: {sync_state.get('last_sync_time', '無')}")
                print(f"📊 同步次數: {sync_state.get('sync_count', 0)}")
            else:
                print("📊 尚未進行過同步")
            
            # 檢查遠程狀態
            if check_remote_db_exists():
                remote_size, remote_mtime = get_remote_db_info()
                print(f"🌐 遠程數據庫: {remote_size} bytes")
            else:
                print("🌐 遠程數據庫: 不存在或無法訪問")
            return
            
        elif sys.argv[1] == '--force':
            # 強制同步
            if os.path.exists(SYNC_STATE_FILE):
                os.remove(SYNC_STATE_FILE)
            print("🔄 強制同步模式")
    
    # 執行同步
    result = sync_database()
    print(f"📊 同步結果: {result['message']}")
    
    if result['status'] == 'success':
        print(f"✅ 同步完成，共 {result.get('records', 0)} 筆記錄")

if __name__ == '__main__':
    main()
