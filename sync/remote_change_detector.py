"""
遠程變更檢測器
檢測交易主機的數據變更，支援增量同步
"""
import subprocess
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class RemoteChangeDetector:
    """遠程變更檢測器"""
    
    def __init__(self, remote_host: str, remote_user: str, ssh_key_path: str, remote_db_path: str):
        self.remote_host = remote_host
        self.remote_user = remote_user
        self.ssh_key_path = ssh_key_path
        self.remote_db_path = remote_db_path
    
    def check_table_changes(self, table_name: str, last_id: int = 0, last_timestamp: float = 0) -> Dict:
        """
        檢查特定表的變更 - 修復版本
        """
        try:
            # 先檢查表是否存在
            table_check_sql = f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';"
            table_check_result = self._execute_remote_sql(table_check_sql)
            
            if not table_check_result['success']:
                return {
                    'has_changes': False,
                    'new_count': 0,
                    'error': f'無法檢查表 {table_name}: {table_check_result.get("error")}'
                }
            
            # 檢查表是否存在
            if not table_check_result['output'].strip():
                return {
                    'has_changes': False,
                    'new_count': 0,
                    'error': f'表 {table_name} 不存在'
                }
            
            # 根據表類型構建不同的查詢
            if table_name == 'daily_stats':
                # daily_stats 使用日期比較
                last_date = datetime.fromtimestamp(last_timestamp).strftime('%Y-%m-%d') if last_timestamp > 0 else '1970-01-01'
                sql_query = f"SELECT COUNT(*) FROM {table_name} WHERE date > '{last_date}';"
            else:
                # 其他表使用ID比較
                sql_query = f"SELECT COUNT(*) FROM {table_name} WHERE id > {last_id};"
            
            # 執行計數查詢
            result = self._execute_remote_sql(sql_query)
            
            if result['success']:
                count_str = result['output'].strip()
                try:
                    new_count = int(count_str)
                    
                    # 如果有新記錄，獲取最新值
                    latest_value = None
                    if new_count > 0:
                        if table_name == 'daily_stats':
                            latest_sql = f"SELECT MAX(date) FROM {table_name};"
                        else:
                            latest_sql = f"SELECT MAX(id) FROM {table_name};"
                        
                        latest_result = self._execute_remote_sql(latest_sql)
                        if latest_result['success']:
                            latest_value = latest_result['output'].strip()
                    
                    return {
                        'has_changes': new_count > 0,
                        'new_count': new_count,
                        'latest_value': latest_value,
                        'table_name': table_name,
                        'check_time': datetime.now().isoformat()
                    }
                except ValueError:
                    return {
                        'has_changes': False,
                        'new_count': 0,
                        'error': f'無法解析計數結果: {count_str}'
                    }
            
            return {
                'has_changes': False,
                'new_count': 0,
                'error': result.get('error', '查詢失敗')
            }
            
        except Exception as e:
            logger.error(f"檢查表 {table_name} 變更時出錯: {str(e)}")
            return {
                'has_changes': False,
                'new_count': 0,
                'error': str(e)
            }
    
    def _execute_remote_sql(self, sql_query: str) -> Dict:
        """
        執行遠程SQL查詢 - 調試版本
        """
        try:
            # 構建SSH命令 - 簡化輸出格式
            ssh_command = [
                'ssh',
                '-i', self.ssh_key_path,
                '-o', 'ConnectTimeout=10',
                '-o', 'StrictHostKeyChecking=no',
                f'{self.remote_user}@{self.remote_host}',
                f'sqlite3 {self.remote_db_path} "{sql_query}"'  # 移除 -header -column
            ]
            
            # 執行命令
            result = subprocess.run(
                ssh_command,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'output': result.stdout,
                    'command': sql_query  # 記錄SQL查詢
                }
            else:
                return {
                    'success': False,
                    'error': result.stderr,
                    'returncode': result.returncode,
                    'command': sql_query
                }
                
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'SSH命令超時',
                'command': sql_query
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'command': sql_query
            }
    
    def check_all_tables_changes(self, last_sync_states: Dict) -> Dict:
        """
        檢查所有表的變更
        
        Args:
            last_sync_states: 各表的最後同步狀態
            
        Returns:
            Dict: 所有表的變更摘要
        """
        tables_to_check = [
            'signals_received',
            'orders_executed', 
            'trading_results',
            'ml_features_v2',
            'ml_signal_quality',
            'daily_stats'
        ]
        
        changes_summary = {
            'has_any_changes': False,
            'total_new_records': 0,
            'table_changes': {},
            'check_time': datetime.now().isoformat()
        }
        
        for table_name in tables_to_check:
            table_state = last_sync_states.get(table_name, {})
            last_id = table_state.get('last_id', 0)
            last_timestamp = table_state.get('last_timestamp', 0)
            
            change_info = self.check_table_changes(table_name, last_id, last_timestamp)
            changes_summary['table_changes'][table_name] = change_info
            
            if change_info.get('has_changes', False):
                changes_summary['has_any_changes'] = True
                changes_summary['total_new_records'] += change_info.get('new_count', 0)
        
        return changes_summary

# 創建配置實例
def create_remote_detector():
    """創建遠程檢測器實例"""
    return RemoteChangeDetector(
        remote_host="15.168.60.229",
        remote_user="ec2-user", 
        ssh_key_path="/home/ec2-user/.ssh/trading_monitor",
        remote_db_path="/home/ec2-user/69trading-clean/data/trading_signals.db"
    )
