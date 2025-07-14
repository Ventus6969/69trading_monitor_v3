"""

智能同步命令
一鍵執行高效的增量同步
"""
import time
import json
from datetime import datetime
from typing import Dict
from sync.sync_state_manager import sync_state_manager
from sync.remote_change_detector import create_remote_detector
from sync.incremental_sync_engine import incremental_sync_engine

class SmartSyncCommand:
    """智能同步命令"""
    
    def __init__(self):
        self.detector = create_remote_detector()
        self.engine = incremental_sync_engine
        
    def execute_smart_sync(self, force_sync: bool = False) -> Dict:
        """
        執行智能同步
        
        Args:
            force_sync: 是否強制同步
            
        Returns:
            Dict: 同步結果
        """
        sync_start_time = datetime.now()
        
        print("🚀 開始智能同步...")
        print(f"⏰ 開始時間: {sync_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 第1步：檢查變更
        print("\n📊 第1步：檢查遠程變更...")
        if not force_sync:
            all_states = sync_state_manager.state_data.get("table_sync_state", {})
            changes_summary = self.detector.check_all_tables_changes(all_states)
            
            if not changes_summary.get('has_any_changes', False):
                print("✅ 無變更檢測到，跳過同步")
                return {
                    'success': True,
                    'sync_performed': False,
                    'reason': '無變更',
                    'check_time': sync_start_time.isoformat(),
                    'duration_seconds': (datetime.now() - sync_start_time).total_seconds()
                }
            
            print(f"📈 檢測到變更: {changes_summary['total_new_records']} 筆新記錄")
        else:
            print("🔄 強制同步模式")
        
        # 第2步：執行同步
        print("\n🔄 第2步：執行增量同步...")
        sync_result = self.engine.sync_all_tables()
        
        # 第3步：更新統計
        print("\n📊 第3步：更新同步統計...")
        self._update_sync_statistics(sync_result)
        
        # 第4步：生成報告
        sync_duration = (datetime.now() - sync_start_time).total_seconds()
        
        final_result = {
            'success': sync_result['success'],
            'sync_performed': True,
            'sync_time': sync_start_time.isoformat(),
            'duration_seconds': sync_duration,
            'tables_processed': sync_result['tables_processed'],
            'total_records_synced': sync_result['total_records_synced'],
            'table_results': sync_result['table_results'],
            'errors': sync_result.get('errors', [])
        }
        
        print(f"\n🎯 智能同步完成:")
        print(f"   ✅ 狀態: {'成功' if final_result['success'] else '失敗'}")
        print(f"   📊 同步記錄: {final_result['total_records_synced']} 筆")
        print(f"   ⏱️ 耗時: {sync_duration:.2f} 秒")
        print(f"   📅 完成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return final_result
    
    def _update_sync_statistics(self, sync_result: Dict):
        """更新同步統計"""
        try:
            current_stats = sync_state_manager.get_sync_statistics()
            
            # 更新統計
            current_stats['total_syncs'] = current_stats.get('total_syncs', 0) + 1
            if sync_result['success']:
                current_stats['successful_syncs'] = current_stats.get('successful_syncs', 0) + 1
            else:
                current_stats['failed_syncs'] = current_stats.get('failed_syncs', 0) + 1
            
            current_stats['last_sync_duration'] = sync_result.get('sync_duration_seconds', 0)
            current_stats['last_sync_time'] = datetime.now().isoformat()
            
            # 保存統計
            sync_state_manager.state_data['sync_statistics'] = current_stats
            sync_state_manager._save_state()
            
        except Exception as e:
            print(f"⚠️ 更新統計失敗: {str(e)}")
    
    def get_sync_status(self) -> Dict:
        """獲取同步狀態摘要"""
        stats = sync_state_manager.get_sync_statistics()
        
        return {
            'last_sync_time': stats.get('last_sync_time', '從未同步'),
            'total_syncs': stats.get('total_syncs', 0),
            'successful_syncs': stats.get('successful_syncs', 0),
            'failed_syncs': stats.get('failed_syncs', 0),
            'success_rate': f"{(stats.get('successful_syncs', 0) / max(stats.get('total_syncs', 1), 1)) * 100:.1f}%",
            'last_duration': f"{stats.get('last_sync_duration', 0):.2f}秒"
        }

# 創建全局實例
smart_sync_command = SmartSyncCommand()
