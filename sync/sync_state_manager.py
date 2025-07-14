"""
同步狀態管理器
追蹤各表的最後同步時間戳，實現增量同步
"""
import json
import os
from datetime import datetime
from typing import Dict, Optional

class SyncStateManager:
    """同步狀態管理器"""
    
    def __init__(self, state_file: str = "data/sync_state.json"):
        self.state_file = state_file
        self.state_data = self._load_state()
    
    def _load_state(self) -> Dict:
        """載入同步狀態"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"載入同步狀態失敗: {e}")
                return self._get_default_state()
        return self._get_default_state()
    
    def _get_default_state(self) -> Dict:
        """獲取默認同步狀態"""
        return {
            "last_sync_time": None,
            "table_sync_state": {
                "signals_received": {"last_id": 0, "last_timestamp": 0},
                "orders_executed": {"last_id": 0, "last_timestamp": 0},
                "trading_results": {"last_id": 0, "last_timestamp": 0},
                "ml_features_v2": {"last_id": 0, "last_timestamp": 0},
                "ml_signal_quality": {"last_id": 0, "last_timestamp": 0},
                "daily_stats": {"last_date": "1970-01-01"}
            },
            "sync_statistics": {
                "total_syncs": 0,
                "successful_syncs": 0,
                "failed_syncs": 0,
                "last_sync_duration": 0,
                "data_transferred_mb": 0
            }
        }
    
    def get_last_sync_info(self, table_name: str) -> Dict:
        """獲取表的最後同步信息"""
        return self.state_data.get("table_sync_state", {}).get(table_name, {})
    
    def update_table_sync_state(self, table_name: str, last_id: int, last_timestamp: float):
        """更新表的同步狀態"""
        if "table_sync_state" not in self.state_data:
            self.state_data["table_sync_state"] = {}
        
        self.state_data["table_sync_state"][table_name] = {
            "last_id": last_id,
            "last_timestamp": last_timestamp,
            "last_sync": datetime.now().isoformat()
        }
        self._save_state()
    
    def _save_state(self):
        """保存同步狀態"""
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump(self.state_data, f, indent=2)
        except Exception as e:
            print(f"保存同步狀態失敗: {e}")
    
    def get_sync_statistics(self) -> Dict:
        """獲取同步統計"""
        return self.state_data.get("sync_statistics", {})

# 創建全局實例
sync_state_manager = SyncStateManager()
