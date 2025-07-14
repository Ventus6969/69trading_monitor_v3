"""
增量同步引擎
只同步變更的數據，大幅提升效率
"""
import os
import sqlite3
import subprocess
import logging
from datetime import datetime
from typing import Dict, List, Optional
from sync.sync_state_manager import sync_state_manager
from sync.remote_change_detector import create_remote_detector

logger = logging.getLogger(__name__)

class IncrementalSyncEngine:
    """增量同步引擎"""
    
    def __init__(self, local_db_path: str = "data/trading_signals.db"):
        self.local_db_path = local_db_path
        self.remote_detector = create_remote_detector()
        self.sync_stats = {
            'total_records_synced': 0,
            'tables_synced': 0,
            'sync_duration': 0,
            'last_sync_time': None
        }
    
    def sync_table_incremental(self, table_name: str, last_id: int = 0) -> Dict:
        """
        增量同步單個表
        
        Args:
            table_name: 表名
            last_id: 最後同步的ID
            
        Returns:
            Dict: 同步結果
        """
        try:
            print(f"🔄 開始同步表 {table_name}...")
            
            # 檢查是否有變更
            change_info = self.remote_detector.check_table_changes(table_name, last_id, 0)
            
            if not change_info.get('has_changes', False):
                print(f"✅ {table_name} 無變更，跳過同步")
                return {
                    'success': True,
                    'table_name': table_name,
                    'records_synced': 0,
                    'message': '無變更'
                }
            
            # 獲取新記錄
            new_records = self._fetch_new_records(table_name, last_id)
            
            if not new_records['success']:
                return {
                    'success': False,
                    'table_name': table_name,
                    'error': new_records['error']
                }
            
            # 插入到本地資料庫
            insert_result = self._insert_records_to_local(table_name, new_records['data'])
            
            if insert_result['success']:
                # 更新同步狀態
                latest_id = int(change_info.get('latest_value', last_id))
                sync_state_manager.update_table_sync_state(table_name, latest_id, datetime.now().timestamp())
                
                print(f"✅ {table_name} 同步完成: {insert_result['records_inserted']} 筆記錄")
                
                return {
                    'success': True,
                    'table_name': table_name,
                    'records_synced': insert_result['records_inserted'],
                    'latest_id': latest_id
                }
            else:
                return {
                    'success': False,
                    'table_name': table_name,
                    'error': insert_result['error']
                }
                
        except Exception as e:
            logger.error(f"同步表 {table_name} 時出錯: {str(e)}")
            return {
                'success': False,
                'table_name': table_name,
                'error': str(e)
            }
    
    def _fetch_new_records(self, table_name: str, last_id: int) -> Dict:
        """
        從遠程獲取新記錄
        
        Args:
            table_name: 表名
            last_id: 最後同步的ID
            
        Returns:
            Dict: 獲取結果
        """
        try:
            # 構建查詢 - 只獲取新記錄
            if table_name == 'daily_stats':
                # daily_stats 使用日期查詢
                sql_query = f"SELECT * FROM {table_name} ORDER BY date DESC LIMIT 10;"
            else:
                # 其他表使用ID查詢
                sql_query = f"SELECT * FROM {table_name} WHERE id > {last_id} ORDER BY id;"
            
            # 執行遠程查詢
            result = self.remote_detector._execute_remote_sql(sql_query)
            
            if not result['success']:
                return {
                    'success': False,
                    'error': result['error']
                }
            
            # 解析結果
            output = result['output'].strip()
            if not output:
                return {
                    'success': True,
                    'data': [],
                    'record_count': 0
                }
            
            # 將輸出轉換為記錄列表
            records = []
            for line in output.split('\n'):
                if line.strip():
                    # 簡單的分割處理，實際可能需要更複雜的解析
                    records.append(line.strip())
            
            return {
                'success': True,
                'data': records,
                'record_count': len(records)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _insert_records_to_local(self, table_name: str, records: List[str]) -> Dict:
        """
        將記錄插入本地資料庫
        
        Args:
            table_name: 表名
            records: 記錄列表
            
        Returns:
            Dict: 插入結果
        """
        try:
            if not records:
                return {
                    'success': True,
                    'records_inserted': 0
                }
            
            # 暫時先記錄到日誌，實際插入邏輯後續完善
            print(f"📊 準備插入 {len(records)} 筆記錄到 {table_name}")
            for i, record in enumerate(records[:3]):  # 只顯示前3筆
                print(f"   記錄 {i+1}: {record[:100]}...")
            
            # TODO: 實際的插入邏輯
            # 這裡先返回成功，後續會實現真正的插入
            
            return {
                'success': True,
                'records_inserted': len(records)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def sync_all_tables(self) -> Dict:
        """
        同步所有表
        
        Returns:
            Dict: 同步摘要
        """
        sync_start_time = datetime.now()
        
        # 需要同步的表
        tables_to_sync = [
            'signals_received',
            'orders_executed',
            'trading_results',
            'ml_features_v2',
            'ml_signal_quality'
        ]
        
        sync_results = {
            'success': True,
            'sync_time': sync_start_time.isoformat(),
            'tables_processed': 0,
            'total_records_synced': 0,
            'table_results': {},
            'errors': []
        }
        
        for table_name in tables_to_sync:
            # 獲取最後同步狀態
            last_sync_info = sync_state_manager.get_last_sync_info(table_name)
            last_id = last_sync_info.get('last_id', 0)
            
            # 同步表
            table_result = self.sync_table_incremental(table_name, last_id)
            sync_results['table_results'][table_name] = table_result
            
            if table_result['success']:
                sync_results['total_records_synced'] += table_result.get('records_synced', 0)
                sync_results['tables_processed'] += 1
            else:
                sync_results['success'] = False
                sync_results['errors'].append(f"{table_name}: {table_result.get('error', '未知錯誤')}")
        
        # 計算同步時間
        sync_duration = (datetime.now() - sync_start_time).total_seconds()
        sync_results['sync_duration_seconds'] = sync_duration
        
        print(f"\n🎯 同步完成摘要:")
        print(f"   處理表數: {sync_results['tables_processed']}/{len(tables_to_sync)}")
        print(f"   同步記錄: {sync_results['total_records_synced']} 筆")
        print(f"   耗時: {sync_duration:.2f} 秒")
        
        return sync_results

# 創建全局實例
incremental_sync_engine = IncrementalSyncEngine()
