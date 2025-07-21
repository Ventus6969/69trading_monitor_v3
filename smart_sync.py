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

def sync_from_remote():
    """
    🔥 主要同步函數 - v3.2.1 修復版本 (時間戳容忍度調整)
    從遠程同步數據庫到本地
    """
    try:
        # 確保本地目錄存在
        os.makedirs(os.path.dirname(LOCAL_DB_PATH), exist_ok=True)
        
        # 檢查遠程數據庫
        if not check_remote_db_exists():
            return {
                'success': False, 
                'message': f'遠程數據庫不存在: {REMOTE_DB_PATH}',
                'error': 'Remote database not found'
            }
        
        # 獲取遠程信息
        remote_size, remote_mtime = get_remote_db_info()
        logger.info(f"遠程數據庫: {remote_size} bytes, 修改時間: {datetime.fromtimestamp(remote_mtime)}")
        
        # 🔥 修復：調整同步判斷邏輯，增加容忍度
        need_sync = True
        sync_reason = "初始同步"
        
        if os.path.exists(SYNC_STATE_FILE):
            try:
                with open(SYNC_STATE_FILE, 'r') as f:
                    sync_state = json.load(f)
                    
                last_size = sync_state.get('last_size', 0)
                last_mtime = sync_state.get('last_mtime', 0)
                
                # 🔥 新增：設定容忍度
                size_tolerance = 2048      # 2KB大小容忍度
                time_tolerance = 600       # 10分鐘時間容忍度 (600秒)
                
                size_diff = abs(remote_size - last_size)
                time_diff = abs(remote_mtime - last_mtime)
                
                logger.info(f"🔍 同步檢查:")
                logger.info(f"   大小差異: {size_diff} bytes (容忍度: {size_tolerance} bytes)")
                logger.info(f"   時間差異: {time_diff} 秒 (容忍度: {time_tolerance} 秒)")
                
                # 🔥 修復：使用容忍度判斷是否需要同步
                if size_diff <= size_tolerance and time_diff <= time_tolerance:
                    need_sync = False
                    sync_reason = "數據無顯著變化"
                    logger.info(f"✅ {sync_reason}，跳過同步")
                else:
                    if size_diff > size_tolerance:
                        sync_reason = f"檔案大小變化: {size_diff} bytes"
                    else:
                        sync_reason = f"修改時間變化: {time_diff} 秒"
                    logger.info(f"🔄 需要同步: {sync_reason}")
                    
            except Exception as e:
                logger.warning(f"讀取同步狀態失敗: {str(e)}")
                sync_reason = "狀態文件錯誤，強制同步"
        
        if not need_sync:
            return {
                'success': True,
                'message': sync_reason,
                'sync_performed': False
            }
        
        # 執行同步
        logger.info(f"🔄 開始同步: {sync_reason}")
        
        # 備份現有數據庫（如果存在）
        if os.path.exists(LOCAL_DB_PATH):
            backup_path = f"{LOCAL_DB_PATH}.backup.{int(datetime.now().timestamp())}"
            try:
                import shutil
                shutil.copy2(LOCAL_DB_PATH, backup_path)
                logger.info(f"📦 已備份現有數據庫: {backup_path}")
            except Exception as e:
                logger.warning(f"備份失敗: {str(e)}")
        
        # 執行SCP同步
        sync_cmd = [
            'scp', '-i', SSH_KEY_PATH,
            '-o', 'ConnectTimeout=10',
            '-o', 'StrictHostKeyChecking=no',
            f'{REMOTE_USER}@{REMOTE_HOST}:{REMOTE_DB_PATH}',
            LOCAL_DB_PATH
        ]
        
        logger.info("📡 執行SCP同步...")
        result = subprocess.run(sync_cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            # 🔥 更新同步狀態
            sync_state = {
                'last_sync_time': datetime.now().isoformat(),
                'last_size': remote_size,
                'last_mtime': remote_mtime,
                'sync_count': sync_state.get('sync_count', 0) + 1 if 'sync_state' in locals() else 1,
                'sync_reason': sync_reason,
                'version': 'v3.2.1'  # 版本標記
            }
            
            with open(SYNC_STATE_FILE, 'w') as f:
                json.dump(sync_state, f, indent=2)
            
            # 驗證同步結果
            local_size = os.path.getsize(LOCAL_DB_PATH)
            logger.info(f"✅ 同步成功: {local_size} bytes")
            
            # 快速檢查數據
            record_count = check_database_records()
            
            return {
                'success': True,
                'message': f'同步成功，數據庫大小: {local_size} bytes，記錄數: {record_count}',
                'sync_performed': True,
                'records': record_count,
                'size_bytes': local_size,
                'sync_time': sync_state['last_sync_time'],
                'sync_reason': sync_reason
            }
        else:
            logger.error(f"❌ SCP同步失敗: {result.stderr}")
            return {
                'success': False,
                'message': f'同步失敗: {result.stderr}',
                'error': result.stderr
            }
            
    except subprocess.TimeoutExpired:
        logger.error("❌ 同步超時")
        return {
            'success': False,
            'message': '同步超時',
            'error': 'Sync timeout'
        }
    except Exception as e:
        logger.error(f"同步過程出錯: {str(e)}")
        return {
            'success': False,
            'message': f'同步異常: {str(e)}',
            'error': str(e)
        }

def sync_database():
    """同步數據庫 - 向後相容函數"""
    result = sync_from_remote()
    
    # 轉換為舊格式
    if result['success']:
        return {
            'status': 'success' if result.get('sync_performed', True) else 'skipped',
            'message': result['message'],
            'records': result.get('records', 0)
        }
    else:
        return {
            'status': 'error',
            'message': result['message']
        }

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

def get_sync_status():
    """獲取同步狀態"""
    try:
        if os.path.exists(SYNC_STATE_FILE):
            with open(SYNC_STATE_FILE, 'r') as f:
                sync_state = json.load(f)
                
            return {
                'last_sync_time': sync_state.get('last_sync_time', '無'),
                'sync_count': sync_state.get('sync_count', 0),
                'last_size': sync_state.get('last_size', 0),
                'status': 'ok'
            }
        else:
            return {
                'last_sync_time': '尚未同步',
                'sync_count': 0,
                'last_size': 0,
                'status': 'never_synced'
            }
    except Exception as e:
        return {
            'last_sync_time': '錯誤',
            'sync_count': 0,
            'last_size': 0,
            'status': 'error',
            'error': str(e)
        }

def main():
    """主程式"""
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--status':
            # 顯示同步狀態
            status = get_sync_status()
            print(f"📊 最後同步: {status['last_sync_time']}")
            print(f"📊 同步次數: {status['sync_count']}")
            print(f"📊 數據庫大小: {status['last_size']} bytes")
            
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
    result = sync_from_remote()
    print(f"📊 同步結果: {result['message']}")
    
    if result['success']:
        print(f"✅ 同步完成，共 {result.get('records', 0)} 筆記錄")

if __name__ == '__main__':
    main()
