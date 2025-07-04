#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
进度管理系统

提供完整的任务进度管理功能，包括：
- 任务队列管理
- 多线程处理进度跟踪
- 任务状态管理
- 进度通知系统
- 任务暂停/恢复/取消
"""

import threading
import queue
import time
import uuid
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime

from .logger import get_logger


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"       # 等待执行
    RUNNING = "running"       # 执行中
    PAUSED = "paused"         # 暂停
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"         # 失败
    CANCELLED = "cancelled"   # 已取消


class TaskPriority(Enum):
    """任务优先级枚举"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class TaskProgress:
    """任务进度信息"""
    task_id: str
    percentage: float = 0.0           # 完成百分比
    current_step: str = ""            # 当前步骤描述
    total_steps: int = 0              # 总步骤数
    completed_steps: int = 0          # 已完成步骤数
    processed_files: List[str] = field(default_factory=list)  # 已处理文件
    pending_files: List[str] = field(default_factory=list)    # 待处理文件
    failed_files: List[Dict] = field(default_factory=list)    # 失败文件
    start_time: Optional[datetime] = None      # 开始时间
    estimated_time: Optional[float] = None     # 预估剩余时间
    details: Dict[str, Any] = field(default_factory=dict)     # 额外详情


@dataclass
class Task:
    """任务定义"""
    task_id: str
    name: str
    description: str = ""
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    progress: TaskProgress = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: str = ""
    
    def __post_init__(self):
        if self.progress is None:
            self.progress = TaskProgress(task_id=self.task_id)


class TaskHandler(ABC):
    """任务处理器抽象基类"""
    
    @abstractmethod
    def execute(self, task: Task, progress_callback: Callable[[TaskProgress], None]) -> bool:
        """
        执行任务
        
        Args:
            task: 任务对象
            progress_callback: 进度回调函数
            
        Returns:
            执行是否成功
        """
        pass
    
    @abstractmethod
    def can_pause(self) -> bool:
        """是否支持暂停"""
        pass
    
    @abstractmethod
    def pause(self) -> bool:
        """暂停任务"""
        pass
    
    @abstractmethod
    def resume(self) -> bool:
        """恢复任务"""
        pass
    
    @abstractmethod
    def cancel(self) -> bool:
        """取消任务"""
        pass


class ProgressManager:
    """进度管理器"""
    
    def __init__(self, max_workers: int = 4):
        """
        初始化进度管理器
        
        Args:
            max_workers: 最大工作线程数
        """
        self.max_workers = max_workers
        self.logger = get_logger('progress_manager')
        
        # 任务队列和存储
        self.task_queue = queue.PriorityQueue()
        self.tasks: Dict[str, Task] = {}
        self.task_handlers: Dict[str, TaskHandler] = {}
        
        # 线程管理
        self.workers: List[threading.Thread] = []
        self.active_tasks: Dict[str, str] = {}  # worker_id -> task_id
        self.is_running = False
        self.shutdown_event = threading.Event()
        
        # 回调函数
        self.progress_callbacks: List[Callable[[str, TaskProgress], None]] = []
        self.status_callbacks: List[Callable[[str, TaskStatus], None]] = []
        
        # 统计信息
        self.stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'cancelled_tasks': 0
        }
        
        self.logger.info(f"进度管理器初始化完成，最大工作线程数: {max_workers}")
    
    def start(self) -> None:
        """启动进度管理器"""
        if self.is_running:
            self.logger.warning("进度管理器已在运行")
            return
        
        self.is_running = True
        self.shutdown_event.clear()
        
        # 启动工作线程
        for i in range(self.max_workers):
            worker = threading.Thread(
                target=self._worker_thread,
                args=(f"worker-{i}",),
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
        
        self.logger.info(f"进度管理器已启动，工作线程数: {len(self.workers)}")
    
    def stop(self, timeout: float = 30.0) -> None:
        """停止进度管理器"""
        if not self.is_running:
            return
        
        self.logger.info("正在停止进度管理器...")
        self.is_running = False
        self.shutdown_event.set()
        
        # 等待所有线程结束
        for worker in self.workers:
            worker.join(timeout=timeout)
        
        self.workers.clear()
        self.active_tasks.clear()
        
        self.logger.info("进度管理器已停止")
    
    def register_handler(self, task_type: str, handler: TaskHandler) -> None:
        """
        注册任务处理器
        
        Args:
            task_type: 任务类型
            handler: 处理器实例
        """
        self.task_handlers[task_type] = handler
        self.logger.debug(f"注册任务处理器: {task_type}")
    
    def add_progress_callback(self, callback: Callable[[str, TaskProgress], None]) -> None:
        """添加进度回调函数"""
        self.progress_callbacks.append(callback)
    
    def add_status_callback(self, callback: Callable[[str, TaskStatus], None]) -> None:
        """添加状态变更回调函数"""
        self.status_callbacks.append(callback)
    
    def submit_task(self, task_type: str, name: str, description: str = "", 
                   priority: TaskPriority = TaskPriority.NORMAL, **kwargs) -> str:
        """
        提交任务
        
        Args:
            task_type: 任务类型
            name: 任务名称
            description: 任务描述
            priority: 任务优先级
            **kwargs: 任务额外参数
            
        Returns:
            任务ID
        """
        if task_type not in self.task_handlers:
            raise ValueError(f"未注册的任务类型: {task_type}")
        
        task_id = str(uuid.uuid4())
        task = Task(
            task_id=task_id,
            name=name,
            description=description,
            priority=priority
        )
        
        # 保存额外参数
        task.progress.details.update(kwargs)
        task.progress.details['task_type'] = task_type
        
        self.tasks[task_id] = task
        
        # 添加到队列（优先级队列，数值越大优先级越高）
        self.task_queue.put((priority.value * -1, time.time(), task_id))
        
        self.stats['total_tasks'] += 1
        self.logger.info(f"提交任务: {name} (ID: {task_id}, 类型: {task_type})")
        
        self._notify_status_change(task_id, TaskStatus.PENDING)
        return task_id
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务信息"""
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> List[Task]:
        """获取所有任务"""
        return list(self.tasks.values())
    
    def get_active_tasks(self) -> List[Task]:
        """获取活跃任务"""
        return [self.tasks[task_id] for task_id in self.active_tasks.values() 
                if task_id in self.tasks]
    
    def pause_task(self, task_id: str) -> bool:
        """暂停任务"""
        task = self.tasks.get(task_id)
        if not task or task.status != TaskStatus.RUNNING:
            return False
        
        task_type = task.progress.details.get('task_type')
        handler = self.task_handlers.get(task_type)
        
        if handler and handler.can_pause():
            if handler.pause():
                task.status = TaskStatus.PAUSED
                self._notify_status_change(task_id, TaskStatus.PAUSED)
                self.logger.info(f"任务已暂停: {task.name} (ID: {task_id})")
                return True
        
        return False
    
    def resume_task(self, task_id: str) -> bool:
        """恢复任务"""
        task = self.tasks.get(task_id)
        if not task or task.status != TaskStatus.PAUSED:
            return False
        
        task_type = task.progress.details.get('task_type')
        handler = self.task_handlers.get(task_type)
        
        if handler:
            if handler.resume():
                task.status = TaskStatus.RUNNING
                self._notify_status_change(task_id, TaskStatus.RUNNING)
                self.logger.info(f"任务已恢复: {task.name} (ID: {task_id})")
                return True
        
        return False
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            return False
        
        task_type = task.progress.details.get('task_type')
        handler = self.task_handlers.get(task_type)
        
        success = True
        if handler and task.status == TaskStatus.RUNNING:
            success = handler.cancel()
        
        if success:
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now()
            self.stats['cancelled_tasks'] += 1
            self._notify_status_change(task_id, TaskStatus.CANCELLED)
            self.logger.info(f"任务已取消: {task.name} (ID: {task_id})")
        
        return success
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        running_count = len([t for t in self.tasks.values() if t.status == TaskStatus.RUNNING])
        pending_count = len([t for t in self.tasks.values() if t.status == TaskStatus.PENDING])
        paused_count = len([t for t in self.tasks.values() if t.status == TaskStatus.PAUSED])
        
        return {
            **self.stats,
            'running_tasks': running_count,
            'pending_tasks': pending_count,
            'paused_tasks': paused_count,
            'active_workers': len(self.active_tasks)
        }
    
    def _worker_thread(self, worker_id: str) -> None:
        """工作线程主循环"""
        self.logger.debug(f"工作线程启动: {worker_id}")
        
        while self.is_running and not self.shutdown_event.is_set():
            try:
                # 从队列获取任务（超时1秒）
                _, _, task_id = self.task_queue.get(timeout=1.0)
                
                task = self.tasks.get(task_id)
                if not task or task.status != TaskStatus.PENDING:
                    continue
                
                # 执行任务
                self._execute_task(worker_id, task)
                
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"工作线程 {worker_id} 发生错误: {e}", exc_info=True)
        
        self.logger.debug(f"工作线程退出: {worker_id}")
    
    def _execute_task(self, worker_id: str, task: Task) -> None:
        """执行任务"""
        task_id = task.task_id
        task_type = task.progress.details.get('task_type')
        handler = self.task_handlers.get(task_type)
        
        if not handler:
            self.logger.error(f"未找到任务处理器: {task_type}")
            task.status = TaskStatus.FAILED
            task.error_message = f"未找到任务处理器: {task_type}"
            self._notify_status_change(task_id, TaskStatus.FAILED)
            return
        
        # 更新任务状态
        self.active_tasks[worker_id] = task_id
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        task.progress.start_time = task.started_at
        
        self.logger.info(f"开始执行任务: {task.name} (ID: {task_id}, 工作线程: {worker_id})")
        self._notify_status_change(task_id, TaskStatus.RUNNING)
        
        try:
            # 创建进度回调函数
            def progress_callback(progress: TaskProgress):
                self._notify_progress_change(task_id, progress)
            
            # 执行任务
            success = handler.execute(task, progress_callback)
            
            # 更新最终状态
            if success:
                task.status = TaskStatus.COMPLETED
                task.progress.percentage = 100.0
                task.progress.current_step = "已完成"
                self.stats['completed_tasks'] += 1
                self.logger.info(f"任务执行成功: {task.name} (ID: {task_id})")
            else:
                task.status = TaskStatus.FAILED
                self.stats['failed_tasks'] += 1
                self.logger.warning(f"任务执行失败: {task.name} (ID: {task_id})")
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            self.stats['failed_tasks'] += 1
            self.logger.error(f"任务执行异常: {task.name} (ID: {task_id}) - {e}", exc_info=True)
        
        finally:
            # 清理
            task.completed_at = datetime.now()
            if worker_id in self.active_tasks:
                del self.active_tasks[worker_id]
            
            self._notify_status_change(task_id, task.status)
            self._notify_progress_change(task_id, task.progress)
    
    def _notify_progress_change(self, task_id: str, progress: TaskProgress) -> None:
        """通知进度变更"""
        for callback in self.progress_callbacks:
            try:
                callback(task_id, progress)
            except Exception as e:
                self.logger.error(f"进度回调函数执行失败: {e}", exc_info=True)
    
    def _notify_status_change(self, task_id: str, status: TaskStatus) -> None:
        """通知状态变更"""
        for callback in self.status_callbacks:
            try:
                callback(task_id, status)
            except Exception as e:
                self.logger.error(f"状态回调函数执行失败: {e}", exc_info=True)


# 示例任务处理器
class FileProcessingHandler(TaskHandler):
    """文件处理任务处理器示例"""
    
    def __init__(self):
        self.is_paused = False
        self.is_cancelled = False
        self.logger = get_logger('file_processing_handler')
    
    def execute(self, task: Task, progress_callback: Callable[[TaskProgress], None]) -> bool:
        """执行文件处理任务"""
        files = task.progress.details.get('files', [])
        if not files:
            return False
        
        task.progress.total_steps = len(files)
        task.progress.pending_files = files.copy()
        
        for i, file_path in enumerate(files):
            # 检查是否被取消或暂停
            if self.is_cancelled:
                self.logger.info(f"任务被取消: {task.name}")
                return False
            
            while self.is_paused and not self.is_cancelled:
                time.sleep(0.1)
            
            if self.is_cancelled:
                return False
            
            # 模拟文件处理
            try:
                self._process_file(file_path, task, progress_callback)
                
                # 更新进度
                task.progress.completed_steps = i + 1
                task.progress.percentage = (i + 1) / len(files) * 100
                task.progress.current_step = f"处理文件: {file_path}"
                task.progress.processed_files.append(file_path)
                
                if file_path in task.progress.pending_files:
                    task.progress.pending_files.remove(file_path)
                
                progress_callback(task.progress)
                
            except Exception as e:
                self.logger.error(f"处理文件失败: {file_path} - {e}")
                task.progress.failed_files.append({
                    'file': file_path,
                    'error': str(e)
                })
        
        return True
    
    def _process_file(self, file_path: str, task: Task, progress_callback: Callable) -> None:
        """处理单个文件（模拟）"""
        # 模拟处理时间
        time.sleep(0.5)
        self.logger.debug(f"处理文件: {file_path}")
    
    def can_pause(self) -> bool:
        return True
    
    def pause(self) -> bool:
        self.is_paused = True
        self.logger.info("文件处理任务已暂停")
        return True
    
    def resume(self) -> bool:
        self.is_paused = False
        self.logger.info("文件处理任务已恢复")
        return True
    
    def cancel(self) -> bool:
        self.is_cancelled = True
        self.is_paused = False
        self.logger.info("文件处理任务已取消")
        return True


# 全局进度管理器实例
_progress_manager: Optional[ProgressManager] = None


def get_progress_manager() -> ProgressManager:
    """获取全局进度管理器实例"""
    global _progress_manager
    if _progress_manager is None:
        _progress_manager = ProgressManager()
    return _progress_manager


def initialize_progress_manager(max_workers: int = 4) -> ProgressManager:
    """
    初始化全局进度管理器
    
    Args:
        max_workers: 最大工作线程数
        
    Returns:
        进度管理器实例
    """
    global _progress_manager
    if _progress_manager is not None:
        _progress_manager.stop()
    
    _progress_manager = ProgressManager(max_workers)
    _progress_manager.start()
    
    # 注册默认处理器
    _progress_manager.register_handler('file_processing', FileProcessingHandler())
    
    return _progress_manager


# 导出主要接口
__all__ = [
    'TaskStatus',
    'TaskPriority', 
    'Task',
    'TaskProgress',
    'TaskHandler',
    'ProgressManager',
    'FileProcessingHandler',
    'get_progress_manager',
    'initialize_progress_manager'
] 