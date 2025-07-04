#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
进度管理系统使用示例

演示如何使用进度管理系统的各种功能
"""

import time
import os
from config_manager import ConfigManager
from logger import setup_logging, get_logger
from progress_manager import (
    initialize_progress_manager, get_progress_manager,
    TaskPriority, TaskStatus, TaskHandler, Task, TaskProgress
)


class ExampleTaskHandler(TaskHandler):
    """示例任务处理器"""
    
    def __init__(self):
        self.is_paused = False
        self.is_cancelled = False
        self.logger = get_logger('example_task_handler')
    
    def execute(self, task: Task, progress_callback) -> bool:
        """执行示例任务"""
        items = task.progress.details.get('items', [])
        if not items:
            return False
        
        task.progress.total_steps = len(items)
        task.progress.pending_files = items.copy()
        
        for i, item in enumerate(items):
            # 检查是否被取消或暂停
            if self.is_cancelled:
                self.logger.info(f"任务被取消: {task.name}")
                return False
            
            while self.is_paused and not self.is_cancelled:
                time.sleep(0.1)
            
            if self.is_cancelled:
                return False
            
            # 模拟处理
            try:
                self._process_item(item, task, progress_callback)
                
                # 更新进度
                task.progress.completed_steps = i + 1
                task.progress.percentage = (i + 1) / len(items) * 100
                task.progress.current_step = f"处理项目: {item}"
                task.progress.processed_files.append(item)
                
                if item in task.progress.pending_files:
                    task.progress.pending_files.remove(item)
                
                progress_callback(task.progress)
                
            except Exception as e:
                self.logger.error(f"处理项目失败: {item} - {e}")
                task.progress.failed_files.append({
                    'file': item,
                    'error': str(e)
                })
        
        return True
    
    def _process_item(self, item: str, task: Task, progress_callback) -> None:
        """处理单个项目（模拟）"""
        # 模拟处理时间
        time.sleep(0.3)
        self.logger.debug(f"处理项目: {item}")
    
    def can_pause(self) -> bool:
        return True
    
    def pause(self) -> bool:
        self.is_paused = True
        self.logger.info("示例任务已暂停")
        return True
    
    def resume(self) -> bool:
        self.is_paused = False
        self.logger.info("示例任务已恢复")
        return True
    
    def cancel(self) -> bool:
        self.is_cancelled = True
        self.is_paused = False
        self.logger.info("示例任务已取消")
        return True


def demo_basic_progress_management():
    """演示基本进度管理功能"""
    print("\n1. 基本进度管理演示")
    print("-" * 30)
    
    progress_manager = get_progress_manager()
    logger = get_logger('demo_basic')
    
    # 提交一个简单任务
    task_id = progress_manager.submit_task(
        task_type='example_task',
        name='简单处理任务',
        description='处理5个示例项目',
        priority=TaskPriority.NORMAL,
        items=['项目A', '项目B', '项目C', '项目D', '项目E']
    )
    
    logger.info(f"提交任务: {task_id}")
    
    # 等待任务完成
    while True:
        task = progress_manager.get_task(task_id)
        if task and task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            break
        time.sleep(0.5)
    
    print(f"任务完成: {task.status.value}")


def demo_task_control():
    """演示任务控制功能（暂停、恢复、取消）"""
    print("\n2. 任务控制演示")
    print("-" * 30)
    
    progress_manager = get_progress_manager()
    logger = get_logger('demo_control')
    
    # 提交一个长时间运行的任务
    task_id = progress_manager.submit_task(
        task_type='example_task',
        name='长时间任务',
        description='处理10个项目',
        priority=TaskPriority.HIGH,
        items=[f'长项目{i}' for i in range(1, 11)]
    )
    
    logger.info(f"提交长时间任务: {task_id}")
    
    # 等待任务开始
    time.sleep(0.5)
    
    # 暂停任务
    print("暂停任务...")
    progress_manager.pause_task(task_id)
    time.sleep(2)
    
    # 恢复任务
    print("恢复任务...")
    progress_manager.resume_task(task_id)
    time.sleep(1)
    
    # 取消任务
    print("取消任务...")
    progress_manager.cancel_task(task_id)
    
    # 等待任务状态更新
    time.sleep(0.5)
    task = progress_manager.get_task(task_id)
    print(f"任务状态: {task.status.value}")


def demo_multiple_tasks():
    """演示多任务并发处理"""
    print("\n3. 多任务并发演示")
    print("-" * 30)
    
    progress_manager = get_progress_manager()
    logger = get_logger('demo_multiple')
    
    # 提交多个不同优先级的任务
    task_ids = []
    
    # 低优先级任务
    task_id1 = progress_manager.submit_task(
        task_type='example_task',
        name='低优先级任务',
        description='处理3个项目',
        priority=TaskPriority.LOW,
        items=['低优先级A', '低优先级B', '低优先级C']
    )
    task_ids.append(task_id1)
    
    # 高优先级任务
    task_id2 = progress_manager.submit_task(
        task_type='example_task',
        name='高优先级任务',
        description='处理2个项目',
        priority=TaskPriority.HIGH,
        items=['高优先级A', '高优先级B']
    )
    task_ids.append(task_id2)
    
    # 普通优先级任务
    task_id3 = progress_manager.submit_task(
        task_type='example_task',
        name='普通优先级任务',
        description='处理4个项目',
        priority=TaskPriority.NORMAL,
        items=['普通A', '普通B', '普通C', '普通D']
    )
    task_ids.append(task_id3)
    
    logger.info(f"提交了 {len(task_ids)} 个任务")
    
    # 等待所有任务完成
    while True:
        active_tasks = progress_manager.get_active_tasks()
        pending_tasks = [t for t in progress_manager.get_all_tasks() 
                        if t.task_id in task_ids and t.status == TaskStatus.PENDING]
        
        if not active_tasks and not pending_tasks:
            break
        
        time.sleep(0.5)
    
    # 显示任务完成情况
    for task_id in task_ids:
        task = progress_manager.get_task(task_id)
        print(f"任务 '{task.name}': {task.status.value}")


def demo_progress_callbacks():
    """演示进度回调功能"""
    print("\n4. 进度回调演示")
    print("-" * 30)
    
    progress_manager = get_progress_manager()
    logger = get_logger('demo_callbacks')
    
    def progress_callback(task_id: str, progress: TaskProgress):
        """进度回调函数"""
        print(f"进度更新 [{task_id[:8]}]: {progress.percentage:.1f}% - {progress.current_step}")
    
    def status_callback(task_id: str, status: TaskStatus):
        """状态回调函数"""
        print(f"状态变更 [{task_id[:8]}]: {status.value}")
    
    # 注册回调
    progress_manager.add_progress_callback(progress_callback)
    progress_manager.add_status_callback(status_callback)
    
    # 提交任务
    task_id = progress_manager.submit_task(
        task_type='example_task',
        name='回调演示任务',
        description='处理项目并显示回调信息',
        priority=TaskPriority.NORMAL,
        items=['回调项目A', '回调项目B', '回调项目C']
    )
    
    # 等待任务完成
    while True:
        task = progress_manager.get_task(task_id)
        if task and task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            break
        time.sleep(0.5)


def demo_statistics():
    """演示统计信息功能"""
    print("\n5. 统计信息演示")
    print("-" * 30)
    
    progress_manager = get_progress_manager()
    
    # 获取统计信息
    stats = progress_manager.get_statistics()
    
    print("进度管理器统计信息:")
    print(f"  总任务数: {stats['total_tasks']}")
    print(f"  已完成: {stats['completed_tasks']}")
    print(f"  失败: {stats['failed_tasks']}")
    print(f"  已取消: {stats['cancelled_tasks']}")
    print(f"  运行中: {stats['running_tasks']}")
    print(f"  等待中: {stats['pending_tasks']}")
    print(f"  已暂停: {stats['paused_tasks']}")
    print(f"  活跃工作线程: {stats['active_workers']}")


def main():
    """主演示函数"""
    print("="*50)
    print("进度管理系统使用演示")
    print("="*50)
    
    # 初始化系统
    config_manager = ConfigManager("../config.ini")
    log_config = config_manager.get_logging_config()
    setup_logging(log_config)
    
    main_logger = get_logger('main_demo')
    main_logger.info("开始进度管理系统演示")
    
    # 初始化进度管理器
    progress_manager = initialize_progress_manager(max_workers=2)
    
    # 注册示例任务处理器
    progress_manager.register_handler('example_task', ExampleTaskHandler())
    
    try:
        # 运行演示
        demo_basic_progress_management()
        demo_task_control()
        demo_multiple_tasks()
        demo_progress_callbacks()
        demo_statistics()
        
    finally:
        # 停止进度管理器
        progress_manager.stop()
        main_logger.info("进度管理系统演示完成")
    
    print("\n" + "="*50)
    print("演示完成！")


if __name__ == "__main__":
    main() 