#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件操作模块

提供安全的文件操作功能，支持：
- 文件复制和移动操作
- 批量文件处理
- 操作撤销功能
- 进度跟踪和错误处理
- 目录结构创建
- 文件冲突处理
"""

import os
import shutil
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple, Callable
from datetime import datetime
from enum import Enum
import threading
import queue
import time

# 本地模块
from .logger import get_logger
from .config_manager import ConfigManager
from .progress_manager import ProgressManager


class OperationType(Enum):
    """操作类型枚举"""
    COPY = "copy"
    MOVE = "move"
    CREATE_DIR = "create_dir"
    DELETE = "delete"


class ConflictResolution(Enum):
    """文件冲突解决策略"""
    SKIP = "skip"              # 跳过已存在的文件
    OVERWRITE = "overwrite"    # 覆盖已存在的文件
    RENAME = "rename"          # 重命名新文件
    ASK_USER = "ask_user"      # 询问用户决定


class FileOperation:
    """单个文件操作记录"""
    
    def __init__(self, operation_type: OperationType, source: Path, 
                 destination: Path = None, backup_path: Path = None):
        self.operation_type = operation_type
        self.source = Path(source)
        self.destination = Path(destination) if destination else None
        self.backup_path = Path(backup_path) if backup_path else None
        self.timestamp = datetime.now()
        self.success = False
        self.error_message = ""
        self.file_size = 0
        
        # 记录原始文件大小
        try:
            if self.source.exists() and self.source.is_file():
                self.file_size = self.source.stat().st_size
        except Exception:
            pass
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'operation_type': self.operation_type.value,
            'source': str(self.source),
            'destination': str(self.destination) if self.destination else None,
            'backup_path': str(self.backup_path) if self.backup_path else None,
            'timestamp': self.timestamp.isoformat(),
            'success': self.success,
            'error_message': self.error_message,
            'file_size': self.file_size
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FileOperation':
        """从字典创建对象"""
        op = cls(
            OperationType(data['operation_type']),
            data['source'],
            data.get('destination'),
            data.get('backup_path')
        )
        op.timestamp = datetime.fromisoformat(data['timestamp'])
        op.success = data['success']
        op.error_message = data['error_message']
        op.file_size = data['file_size']
        return op


class OperationBatch:
    """操作批次记录"""
    
    def __init__(self, batch_id: str, description: str = ""):
        self.batch_id = batch_id
        self.description = description
        self.operations: List[FileOperation] = []
        self.start_time = datetime.now()
        self.end_time = None
        self.success_count = 0
        self.error_count = 0
        self.total_size = 0
    
    def add_operation(self, operation: FileOperation):
        """添加操作到批次"""
        self.operations.append(operation)
        if operation.success:
            self.success_count += 1
            self.total_size += operation.file_size
        else:
            self.error_count += 1
    
    def finish(self):
        """完成批次"""
        self.end_time = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'batch_id': self.batch_id,
            'description': self.description,
            'operations': [op.to_dict() for op in self.operations],
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'success_count': self.success_count,
            'error_count': self.error_count,
            'total_size': self.total_size
        }


class FileOperationManager:
    """文件操作管理器"""
    
    def __init__(self, config_manager: ConfigManager = None, 
                 progress_manager: ProgressManager = None):
        """
        初始化文件操作管理器
        
        Args:
            config_manager: 配置管理器实例
            progress_manager: 进度管理器实例
        """
        self.config_manager = config_manager or ConfigManager()
        self.progress_manager = progress_manager or ProgressManager()
        self.logger = get_logger('file_operations')
        
        # 操作历史
        self.operation_batches: List[OperationBatch] = []
        self.current_batch: Optional[OperationBatch] = None
        
        # 撤销相关
        self.backup_dir = Path("backups")
        self.backup_dir.mkdir(exist_ok=True)
        
        # 冲突解决策略
        self.conflict_resolution = ConflictResolution.RENAME
        
        # 线程控制
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        
        self.logger.info("文件操作管理器初始化完成")
    
    def set_conflict_resolution(self, strategy: ConflictResolution):
        """设置冲突解决策略"""
        self.conflict_resolution = strategy
        self.logger.info(f"设置冲突解决策略为: {strategy.value}")
    
    def start_batch(self, description: str = "") -> str:
        """
        开始新的操作批次
        
        Args:
            description: 批次描述
            
        Returns:
            批次ID
        """
        batch_id = f"batch_{int(time.time())}"
        self.current_batch = OperationBatch(batch_id, description)
        
        self.logger.info(f"开始操作批次: {batch_id} - {description}")
        return batch_id
    
    def finish_batch(self):
        """完成当前批次"""
        if self.current_batch:
            self.current_batch.finish()
            self.operation_batches.append(self.current_batch)
            
            self.logger.info(f"完成操作批次: {self.current_batch.batch_id}, "
                           f"成功: {self.current_batch.success_count}, "
                           f"失败: {self.current_batch.error_count}")
            
            self.current_batch = None
    
    def copy_file(self, source: Union[str, Path], destination: Union[str, Path]) -> bool:
        """
        复制单个文件
        
        Args:
            source: 源文件路径
            destination: 目标文件路径
            
        Returns:
            操作是否成功
        """
        return self._perform_file_operation(OperationType.COPY, source, destination)
    
    def move_file(self, source: Union[str, Path], destination: Union[str, Path]) -> bool:
        """
        移动单个文件
        
        Args:
            source: 源文件路径
            destination: 目标文件路径
            
        Returns:
            操作是否成功
        """
        return self._perform_file_operation(OperationType.MOVE, source, destination)
    
    def create_directory(self, directory_path: Union[str, Path]) -> bool:
        """
        创建目录
        
        Args:
            directory_path: 目录路径
            
        Returns:
            操作是否成功
        """
        operation = FileOperation(OperationType.CREATE_DIR, directory_path)
        
        try:
            directory_path = Path(directory_path)
            
            if directory_path.exists():
                operation.success = True
                self.logger.debug(f"目录已存在: {directory_path}")
            else:
                directory_path.mkdir(parents=True, exist_ok=True)
                operation.success = True
                self.logger.info(f"创建目录成功: {directory_path}")
            
        except Exception as e:
            operation.error_message = str(e)
            self.logger.error(f"创建目录失败 {directory_path}: {e}")
        
        if self.current_batch:
            self.current_batch.add_operation(operation)
        
        return operation.success
    
    def _perform_file_operation(self, operation_type: OperationType, 
                               source: Union[str, Path], 
                               destination: Union[str, Path]) -> bool:
        """执行文件操作"""
        source = Path(source)
        destination = Path(destination)
        
        operation = FileOperation(operation_type, source, destination)
        
        try:
            # 检查源文件
            if not source.exists():
                raise FileNotFoundError(f"源文件不存在: {source}")
            
            # 确保目标目录存在
            destination.parent.mkdir(parents=True, exist_ok=True)
            
            # 处理文件冲突
            final_destination = self._resolve_conflict(destination)
            if final_destination != destination:
                operation.destination = final_destination
            
            # 执行操作
            if operation_type == OperationType.COPY:
                self._copy_with_backup(source, final_destination, operation)
            elif operation_type == OperationType.MOVE:
                self._move_with_backup(source, final_destination, operation)
            
            operation.success = True
            self.logger.info(f"{operation_type.value.upper()}成功: {source} -> {final_destination}")
            
        except Exception as e:
            operation.error_message = str(e)
            self.logger.error(f"{operation_type.value.upper()}失败 {source} -> {destination}: {e}")
        
        if self.current_batch:
            self.current_batch.add_operation(operation)
        
        return operation.success
    
    def _resolve_conflict(self, destination: Path) -> Path:
        """解决文件冲突"""
        if not destination.exists():
            return destination
        
        if self.conflict_resolution == ConflictResolution.SKIP:
            raise FileExistsError(f"文件已存在，跳过: {destination}")
        
        elif self.conflict_resolution == ConflictResolution.OVERWRITE:
            return destination
        
        elif self.conflict_resolution == ConflictResolution.RENAME:
            return self._get_unique_filename(destination)
        
        else:  # ASK_USER
            # 这里可以实现用户交互逻辑
            # 暂时使用重命名策略
            return self._get_unique_filename(destination)
    
    def _get_unique_filename(self, path: Path) -> Path:
        """生成唯一的文件名"""
        counter = 1
        original_path = path
        
        while path.exists():
            stem = original_path.stem
            suffix = original_path.suffix
            parent = original_path.parent
            
            new_name = f"{stem}_{counter}{suffix}"
            path = parent / new_name
            counter += 1
        
        return path
    
    def _copy_with_backup(self, source: Path, destination: Path, operation: FileOperation):
        """带备份的复制操作"""
        # 如果目标文件存在，创建备份
        if destination.exists():
            backup_path = self._create_backup(destination)
            operation.backup_path = backup_path
        
        # 执行复制
        shutil.copy2(source, destination)
    
    def _move_with_backup(self, source: Path, destination: Path, operation: FileOperation):
        """带备份的移动操作"""
        # 如果目标文件存在，创建备份
        if destination.exists():
            backup_path = self._create_backup(destination)
            operation.backup_path = backup_path
        
        # 执行移动
        shutil.move(str(source), str(destination))
    
    def _create_backup(self, file_path: Path) -> Path:
        """创建文件备份"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{file_path.stem}_{timestamp}{file_path.suffix}"
        backup_path = self.backup_dir / backup_filename
        
        # 确保备份目录存在
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 创建备份
        shutil.copy2(file_path, backup_path)
        
        self.logger.debug(f"创建备份: {file_path} -> {backup_path}")
        return backup_path
    
    def batch_operate_files(self, file_operations: List[Tuple[str, Path, Path]], 
                           operation_type: OperationType,
                           progress_callback: Callable = None) -> Dict[str, Any]:
        """
        批量操作文件
        
        Args:
            file_operations: 文件操作列表 [(file_id, source, destination), ...]
            operation_type: 操作类型
            progress_callback: 进度回调函数
            
        Returns:
            操作结果统计
        """
        total_files = len(file_operations)
        success_count = 0
        error_count = 0
        
        batch_id = self.start_batch(f"批量{operation_type.value}")
        
        self.logger.info(f"开始批量{operation_type.value}操作，共 {total_files} 个文件")
        
        try:
            for i, (file_id, source, destination) in enumerate(file_operations):
                if self.stop_event.is_set():
                    self.logger.info("操作被用户停止")
                    break
                
                # 检查暂停
                if self.pause_event.is_set():
                    self.logger.info("操作被暂停")
                    self.pause_event.wait()  # 等待恢复
                
                try:
                    # 更新进度
                    if progress_callback:
                        progress_callback(i + 1, total_files, str(source))
                    
                    # 执行操作
                    if operation_type == OperationType.COPY:
                        success = self.copy_file(source, destination)
                    elif operation_type == OperationType.MOVE:
                        success = self.move_file(source, destination)
                    else:
                        continue
                    
                    if success:
                        success_count += 1
                    else:
                        error_count += 1
                        
                except Exception as e:
                    error_count += 1
                    self.logger.error(f"批量操作文件失败 {source}: {e}")
        
        finally:
            self.finish_batch()
        
        result = {
            'batch_id': batch_id,
            'total_files': total_files,
            'success_count': success_count,
            'error_count': error_count,
            'operation_type': operation_type.value
        }
        
        self.logger.info(f"批量{operation_type.value}完成: "
                        f"总计 {total_files}, 成功 {success_count}, 失败 {error_count}")
        
        return result
    
    def organize_files_by_classification(self, classification_results: Dict[str, Dict[str, Any]], 
                                       base_directory: Union[str, Path],
                                       operation_mode: str = None) -> Dict[str, Any]:
        """
        根据分类结果整理文件
        
        Args:
            classification_results: 分类结果字典
            base_directory: 目标根目录
            operation_mode: 操作模式 ('copy' 或 'move')
            
        Returns:
            整理结果统计
        """
        if operation_mode is None:
            operation_mode = self.config_manager.get_config('Settings', 'file_operation', 'copy')
        
        operation_type = OperationType.COPY if operation_mode == 'copy' else OperationType.MOVE
        base_directory = Path(base_directory)
        
        # 创建文件操作列表
        file_operations = []
        
        for file_path, classification in classification_results.items():
            source = Path(file_path)
            
            if not source.exists():
                continue
            
            # 构建目标路径
            category = classification.get('category', 'Unknown')
            subcategory = classification.get('subcategory', '')
            
            if subcategory:
                target_dir = base_directory / category / subcategory
            else:
                target_dir = base_directory / category
            
            destination = target_dir / source.name
            
            file_operations.append((file_path, source, destination))
        
        # 批量执行操作
        return self.batch_operate_files(file_operations, operation_type)
    
    def undo_last_batch(self) -> bool:
        """撤销最后一个操作批次"""
        if not self.operation_batches:
            self.logger.warning("没有可撤销的操作")
            return False
        
        last_batch = self.operation_batches[-1]
        return self.undo_batch(last_batch.batch_id)
    
    def undo_batch(self, batch_id: str) -> bool:
        """
        撤销指定批次的操作
        
        Args:
            batch_id: 批次ID
            
        Returns:
            撤销是否成功
        """
        # 查找批次
        batch = None
        for b in self.operation_batches:
            if b.batch_id == batch_id:
                batch = b
                break
        
        if not batch:
            self.logger.error(f"找不到批次: {batch_id}")
            return False
        
        self.logger.info(f"开始撤销批次: {batch_id}")
        
        undo_batch_id = self.start_batch(f"撤销批次_{batch_id}")
        success_count = 0
        error_count = 0
        
        try:
            # 按相反顺序撤销操作
            for operation in reversed(batch.operations):
                if not operation.success:
                    continue  # 跳过失败的操作
                
                try:
                    if operation.operation_type == OperationType.COPY:
                        # 复制操作的撤销：删除目标文件
                        if operation.destination and operation.destination.exists():
                            operation.destination.unlink()
                            self.logger.debug(f"删除复制的文件: {operation.destination}")
                    
                    elif operation.operation_type == OperationType.MOVE:
                        # 移动操作的撤销：移动回原位置
                        if operation.destination and operation.destination.exists():
                            shutil.move(str(operation.destination), str(operation.source))
                            self.logger.debug(f"撤销移动: {operation.destination} -> {operation.source}")
                    
                    elif operation.operation_type == OperationType.CREATE_DIR:
                        # 目录创建的撤销：删除空目录
                        if operation.source.exists() and operation.source.is_dir():
                            try:
                                operation.source.rmdir()  # 只删除空目录
                                self.logger.debug(f"删除空目录: {operation.source}")
                            except OSError:
                                # 目录不为空，不删除
                                pass
                    
                    # 恢复备份文件
                    if operation.backup_path and operation.backup_path.exists():
                        shutil.move(str(operation.backup_path), str(operation.destination))
                        self.logger.debug(f"恢复备份: {operation.backup_path} -> {operation.destination}")
                    
                    success_count += 1
                    
                except Exception as e:
                    error_count += 1
                    self.logger.error(f"撤销操作失败 {operation.source}: {e}")
        
        finally:
            self.finish_batch()
        
        self.logger.info(f"撤销批次完成: {batch_id}, 成功 {success_count}, 失败 {error_count}")
        return error_count == 0
    
    def get_operation_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取操作历史
        
        Args:
            limit: 返回的最大批次数
            
        Returns:
            操作历史列表
        """
        recent_batches = self.operation_batches[-limit:] if limit > 0 else self.operation_batches
        return [batch.to_dict() for batch in reversed(recent_batches)]
    
    def save_operation_history(self, file_path: Union[str, Path]):
        """保存操作历史到文件"""
        file_path = Path(file_path)
        
        try:
            history_data = {
                'version': '1.0',
                'export_time': datetime.now().isoformat(),
                'batches': [batch.to_dict() for batch in self.operation_batches]
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"操作历史已保存到: {file_path}")
            
        except Exception as e:
            self.logger.error(f"保存操作历史失败: {e}")
            raise
    
    def load_operation_history(self, file_path: Union[str, Path]):
        """从文件加载操作历史"""
        file_path = Path(file_path)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                history_data = json.load(f)
            
            # 清空现有历史
            self.operation_batches.clear()
            
            # 加载批次
            for batch_data in history_data.get('batches', []):
                batch = OperationBatch(batch_data['batch_id'], batch_data['description'])
                batch.start_time = datetime.fromisoformat(batch_data['start_time'])
                if batch_data['end_time']:
                    batch.end_time = datetime.fromisoformat(batch_data['end_time'])
                batch.success_count = batch_data['success_count']
                batch.error_count = batch_data['error_count']
                batch.total_size = batch_data['total_size']
                
                # 加载操作
                for op_data in batch_data['operations']:
                    operation = FileOperation.from_dict(op_data)
                    batch.operations.append(operation)
                
                self.operation_batches.append(batch)
            
            self.logger.info(f"操作历史已从文件加载: {file_path}")
            
        except Exception as e:
            self.logger.error(f"加载操作历史失败: {e}")
            raise
    
    def cleanup_backups(self, max_age_days: int = 30):
        """
        清理旧的备份文件
        
        Args:
            max_age_days: 保留备份的最大天数
        """
        if not self.backup_dir.exists():
            return
        
        cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)
        deleted_count = 0
        
        try:
            for backup_file in self.backup_dir.rglob('*'):
                if backup_file.is_file():
                    if backup_file.stat().st_mtime < cutoff_time:
                        backup_file.unlink()
                        deleted_count += 1
            
            self.logger.info(f"清理完成，删除了 {deleted_count} 个旧备份文件")
            
        except Exception as e:
            self.logger.error(f"清理备份文件失败: {e}")
    
    def stop_operations(self):
        """停止正在进行的操作"""
        self.stop_event.set()
        self.logger.info("文件操作已停止")
    
    def pause_operations(self):
        """暂停操作"""
        self.pause_event.set()
        self.logger.info("文件操作已暂停")
    
    def resume_operations(self):
        """恢复操作"""
        self.pause_event.clear()
        self.logger.info("文件操作已恢复")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取操作统计信息"""
        total_batches = len(self.operation_batches)
        total_operations = sum(len(batch.operations) for batch in self.operation_batches)
        total_success = sum(batch.success_count for batch in self.operation_batches)
        total_errors = sum(batch.error_count for batch in self.operation_batches)
        total_size = sum(batch.total_size for batch in self.operation_batches)
        
        return {
            'total_batches': total_batches,
            'total_operations': total_operations,
            'total_success': total_success,
            'total_errors': total_errors,
            'total_size_bytes': total_size,
            'total_size_human': self._format_file_size(total_size),
            'success_rate': (total_success / total_operations * 100) if total_operations > 0 else 0
        }
    
    def _format_file_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        size = float(size_bytes)
        
        while size >= 1024.0 and i < len(size_names) - 1:
            size /= 1024.0
            i += 1
        
        return f"{size:.1f} {size_names[i]}"