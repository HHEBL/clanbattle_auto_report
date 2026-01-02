"""
助战更换任务管理模块
用于管理需要用户确认的助战更换任务
"""
import time
from typing import Optional, Dict


class SupportTask:
    """助战更换任务"""
    def __init__(self, target_qq: int, chara_id: int, chara_name: str, scene: str, group_id: int, operator_qq: int):
        self.target_qq = target_qq  # 目标用户QQ号
        self.chara_id = chara_id  # 角色ID
        self.chara_name = chara_name  # 角色名称
        self.scene = scene  # 场景（地下城/公会战等）
        self.group_id = group_id  # 群号
        self.operator_qq = operator_qq  # 操作者QQ号
        self.timestamp = int(time.time())  # 创建时间戳
    
    def is_expired(self, timeout: int = 180) -> bool:
        """检查任务是否过期（默认3分钟）"""
        return int(time.time()) - self.timestamp > timeout
    
    def get_remaining_time(self, timeout: int = 180) -> int:
        """获取剩余时间（秒）"""
        elapsed = int(time.time()) - self.timestamp
        return max(0, timeout - elapsed)


class TaskManager:
    """任务管理器"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.tasks: Dict[int, SupportTask] = {}  # key: target_qq
        return cls._instance
    
    def add_task(self, target_qq: int, chara_id: int, chara_name: str, scene: str, group_id: int, operator_qq: int) -> SupportTask:
        """添加一个新任务"""
        task = SupportTask(target_qq, chara_id, chara_name, scene, group_id, operator_qq)
        self.tasks[target_qq] = task
        return task
    
    def get_task(self, target_qq: int) -> Optional[SupportTask]:
        """获取指定用户的任务"""
        return self.tasks.get(target_qq)
    
    def remove_task(self, target_qq: int) -> bool:
        """删除任务"""
        if target_qq in self.tasks:
            del self.tasks[target_qq]
            return True
        return False
    
    def clear_expired_tasks(self, timeout: int = 180):
        """清理过期任务"""
        expired_keys = [qq for qq, task in self.tasks.items() if task.is_expired(timeout)]
        for qq in expired_keys:
            del self.tasks[qq]
        return len(expired_keys)


# 全局任务管理器实例
task_manager = TaskManager()
