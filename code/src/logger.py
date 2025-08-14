#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志系统模块

提供完整的日志功能，包括：
- 多级别日志 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- 文件输出和控制台输出
- 日志轮转和文件大小控制
- 自定义格式化
- 配置化管理
"""

import logging
import logging.handlers
import os
import sys
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta


class Logger:
    """日志管理器类"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化日志管理器"""
        if self._initialized:
            return
        
        self.loggers: Dict[str, logging.Logger] = {}
        self.log_dir = None
        self.config = {}
        self._initialized = True
    
    def setup(self, config: Dict[str, Any] = None) -> None:
        """
        设置日志系统
        
        Args:
            config: 日志配置字典
        """
        # 默认配置
        default_config = {
            'log_level': 'INFO',
            'log_to_file': 'true',
            'log_to_console': 'true',
            'log_file_size': '10',  # MB
            'log_file_count': '5',
            'log_format': 'detailed',
            'log_dir': 'logs'
        }
        
        # 合并配置
        self.config = {**default_config, **(config or {})}
        
        # 创建日志目录
        self._setup_log_directory()
        
        # 配置根日志器
        self._setup_root_logger()
    
    def _setup_log_directory(self) -> None:
        """创建日志目录"""
        # 确定基础日志目录路径
        if os.path.isabs(self.config['log_dir']):
            base_log_dir = Path(self.config['log_dir'])
        else:
            # 相对于项目根目录
            project_root = Path(__file__).parent.parent.parent
            base_log_dir = project_root / self.config['log_dir']
        
        # 创建基于启动时间的子目录
        startup_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.log_dir = base_log_dir / startup_time
        
        # 创建目录
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建一个符号链接指向最新的日志目录（Windows上可能需要管理员权限）
        latest_link = base_log_dir / "latest"
        try:
            # 如果已存在，先删除
            if latest_link.exists() or latest_link.is_symlink():
                latest_link.unlink()
            # 创建新的符号链接
            latest_link.symlink_to(startup_time, target_is_directory=True)
        except (OSError, NotImplementedError):
            # Windows上没有管理员权限或不支持符号链接时，创建一个文本文件记录最新日志目录
            try:
                with open(base_log_dir / "latest.txt", 'w', encoding='utf-8') as f:
                    f.write(f"{startup_time}\n{self.log_dir}")
            except Exception:
                pass  # 忽略写入失败

        # 将历史会话日志目录打包为 zip，避免松散文件夹堆积
        try:
            self._archive_old_sessions(base_log_dir, current_dir=self.log_dir)
        except Exception:
            # 打包失败不影响主流程
            pass
    
    def _setup_root_logger(self) -> None:
        """配置根日志器"""
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, self.config['log_level'].upper()))
        
        # 清除现有处理器
        root_logger.handlers.clear()
        
        # 添加处理器
        if self.config['log_to_console'].lower() == 'true':
            self._add_console_handler(root_logger)
        
        if self.config['log_to_file'].lower() == 'true':
            self._add_file_handler(root_logger, 'app.log')
    
    def _get_formatter(self, handler_type: str = 'file') -> logging.Formatter:
        """
        获取日志格式化器
        
        Args:
            handler_type: 处理器类型 ('file' 或 'console')
            
        Returns:
            格式化器对象
        """
        format_style = self.config.get('log_format', 'detailed')
        
        if format_style == 'simple':
            if handler_type == 'console':
                fmt = '%(asctime)s - %(levelname)s - %(message)s'
            else:
                fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        elif format_style == 'detailed':
            if handler_type == 'console':
                fmt = '%(asctime)s - %(name)s[%(process)d] - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
            else:
                fmt = '%(asctime)s - %(name)s[%(process)d] - %(levelname)s - %(pathname)s:%(funcName)s:%(lineno)d - %(message)s'
        else:
            # 默认格式
            fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        return logging.Formatter(
            fmt=fmt,
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    def _add_console_handler(self, logger: logging.Logger) -> None:
        """添加控制台处理器"""
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(self._get_formatter('console'))
        
        # 设置控制台日志级别（通常比文件日志级别高）
        console_level = self.config.get('console_log_level', self.config['log_level'])
        console_handler.setLevel(getattr(logging, console_level.upper()))
        
        logger.addHandler(console_handler)
    
    def _add_file_handler(self, logger: logging.Logger, filename: str) -> None:
        """添加文件处理器"""
        log_file = self.log_dir / filename
        
        # 使用轮转文件处理器
        max_bytes = int(self.config['log_file_size']) * 1024 * 1024  # MB to bytes
        backup_count = int(self.config['log_file_count'])
        
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8',
            delay=True  # 延迟创建物理日志文件，避免生成空文件
        )
        
        file_handler.setFormatter(self._get_formatter('file'))
        logger.addHandler(file_handler)

    def _archive_old_sessions(self, base_dir: Path, current_dir: Path) -> None:
        """将非当前会话的历史日志目录打包为 zip 并删除原目录"""
        for entry in base_dir.iterdir():
            # 跳过当前目录、链接、文本标记文件
            if entry == current_dir or entry.name == "latest" or entry.name.endswith('.txt'):
                continue
            # 仅处理时间戳格式的目录
            if entry.is_dir():
                try:
                    datetime.strptime(entry.name, "%Y-%m-%d_%H-%M-%S")
                except ValueError:
                    continue
                # 目标 zip 路径
                zip_path = base_dir / f"{entry.name}.zip"
                if not zip_path.exists():
                    # 创建 zip 压缩包（保持目录名作为 zip 内根目录）
                    shutil.make_archive(
                        base_name=str(base_dir / entry.name),
                        format='zip',
                        root_dir=str(base_dir),
                        base_dir=entry.name,
                    )
                # 删除原始目录
                try:
                    shutil.rmtree(entry)
                except Exception:
                    pass
    
    def get_logger(self, name: str) -> logging.Logger:
        """
        获取或创建指定名称的日志器
        
        Args:
            name: 日志器名称
            
        Returns:
            日志器对象
        """
        if name not in self.loggers:
            logger = logging.getLogger(name)
            
            # 为特定模块创建专用日志文件
            if self.config.get('log_to_file', 'true').lower() == 'true':
                # 清理名称以用作文件名
                safe_name = name.replace('.', '_').replace('/', '_').replace('\\', '_')
                self._add_file_handler(logger, f'{safe_name}.log')
            
            self.loggers[name] = logger
        
        return self.loggers[name]
    
    def log_exception(self, logger_name: str, exception: Exception, context: str = "") -> None:
        """
        记录异常信息
        
        Args:
            logger_name: 日志器名称
            exception: 异常对象
            context: 上下文信息
        """
        logger = self.get_logger(logger_name)
        
        if context:
            logger.error(f"{context}: {type(exception).__name__}: {str(exception)}", exc_info=True)
        else:
            logger.error(f"{type(exception).__name__}: {str(exception)}", exc_info=True)
    
    def log_performance(self, logger_name: str, operation: str, duration: float, details: str = "") -> None:
        """
        记录性能信息
        
        Args:
            logger_name: 日志器名称
            operation: 操作名称
            duration: 耗时（秒）
            details: 详细信息
        """
        logger = self.get_logger(logger_name)
        
        if details:
            logger.info(f"PERFORMANCE - {operation}: {duration:.3f}s - {details}")
        else:
            logger.info(f"PERFORMANCE - {operation}: {duration:.3f}s")
    
    def log_api_call(self, logger_name: str, method: str, url: str, status_code: int = None, 
                     duration: float = None, error: str = None) -> None:
        """
        记录API调用信息
        
        Args:
            logger_name: 日志器名称
            method: HTTP方法
            url: API地址
            status_code: 状态码
            duration: 耗时
            error: 错误信息
        """
        logger = self.get_logger(logger_name)
        
        if error:
            logger.error(f"API_CALL - {method} {url} - ERROR: {error}")
        else:
            duration_str = f" - {duration:.3f}s" if duration else ""
            status_str = f" - {status_code}" if status_code else ""
            logger.info(f"API_CALL - {method} {url}{status_str}{duration_str}")
    
    def log_file_operation(self, logger_name: str, operation: str, source: str, 
                          target: str = None, status: str = "SUCCESS", error: str = None) -> None:
        """
        记录文件操作信息
        
        Args:
            logger_name: 日志器名称
            operation: 操作类型 (copy, move, delete, create, etc.)
            source: 源文件路径
            target: 目标文件路径
            status: 操作状态
            error: 错误信息
        """
        logger = self.get_logger(logger_name)
        
        target_str = f" -> {target}" if target else ""
        
        if status == "SUCCESS":
            logger.info(f"FILE_OP - {operation.upper()}: {source}{target_str}")
        elif status == "WARNING":
            logger.warning(f"FILE_OP - {operation.upper()}: {source}{target_str} - {error or 'Warning'}")
        else:  # ERROR or other failure status
            logger.error(f"FILE_OP - {operation.upper()}: {source}{target_str} - {error or 'Failed'}")
    
    def get_log_files(self, include_history: bool = True) -> list:
        """
        获取所有日志文件列表
        
        Args:
            include_history: 是否包含历史日志文件夹中的文件
        
        Returns:
            日志文件路径列表
        """
        log_files: List[str] = []
        
        # 当前日志目录的文件
        if self.log_dir and self.log_dir.exists():
            log_files.extend([str(f) for f in self.log_dir.glob('*.log*')])
        
        # 历史日志文件夹的文件
        if include_history and self.log_dir:
            base_dir = self.log_dir.parent
            if base_dir.exists():
                # 附加历史 zip 包
                for zip_file in base_dir.glob('*.zip'):
                    # 名称符合历史会话时间戳
                    name = zip_file.stem
                    try:
                        datetime.strptime(name, "%Y-%m-%d_%H-%M-%S")
                        log_files.append(str(zip_file))
                    except ValueError:
                        continue
        
        return sorted(log_files)
    
    def clear_logs(self, keep_current: bool = True, keep_days: int = 7) -> None:
        """
        清理日志文件
        
        Args:
            keep_current: 是否保留当前会话的日志文件
            keep_days: 保留多少天的历史日志（0表示删除所有历史日志）
        """
        if not self.log_dir:
            return
        
        base_dir = self.log_dir.parent
        if not base_dir.exists():
            return
        
        current_time = datetime.now()
        
        # 清理历史 zip 包与遗留目录
        for entry in base_dir.iterdir():
            # 跳过当前会话目录与标记文件
            if entry == self.log_dir or entry.name == 'latest' or entry.name.endswith('.txt'):
                continue
            try:
                if entry.is_file() and entry.suffix.lower() == '.zip':
                    # 名称形如 2025-01-01_12-00-00.zip
                    session_name = entry.stem
                    dir_time = datetime.strptime(session_name, "%Y-%m-%d_%H-%M-%S")
                    days_diff = (current_time - dir_time).days
                    if keep_days == 0 or days_diff > keep_days:
                        entry.unlink()
                        print(f"已删除历史日志压缩包: {entry.name}")
                elif entry.is_dir():
                    # 遗留未压缩历史目录
                    dir_time = datetime.strptime(entry.name, "%Y-%m-%d_%H-%M-%S")
                    days_diff = (current_time - dir_time).days
                    if keep_days == 0 or days_diff > keep_days:
                        shutil.rmtree(entry)
                        print(f"已删除历史日志目录: {entry.name}")
            except ValueError:
                continue
            except Exception as e:
                print(f"删除历史日志失败 {entry.name}: {e}")
        
        # 清理当前日志目录
        if not keep_current and self.log_dir.exists():
            for log_file in self.log_dir.glob('*.log*'):
                try:
                    log_file.unlink()
                except Exception as e:
                    print(f"删除日志文件失败 {log_file}: {e}")
        elif self.log_dir.exists():
            # 只清理备份日志文件，保留主日志文件
            for log_file in self.log_dir.glob('*.log*'):
                if '.' in log_file.stem and log_file.stem.split('.')[-1].isdigit():
                    try:
                        log_file.unlink()
                    except Exception as e:
                        print(f"删除备份日志文件失败 {log_file}: {e}")
    
    def get_current_log_dir(self) -> str:
        """
        获取当前日志目录路径
        
        Returns:
            当前日志目录的绝对路径
        """
        return str(self.log_dir) if self.log_dir else ""
    
    def get_log_directories(self) -> list:
        """
        获取所有历史日志目录列表
        
        Returns:
            按时间排序的日志目录列表（最新的在前）
        """
        if not self.log_dir:
            return []
        
        base_dir = self.log_dir.parent
        if not base_dir.exists():
            return []
        
        log_dirs = []
        for subdir in base_dir.iterdir():
            if (subdir.is_dir() and 
                subdir.name != "latest" and
                not subdir.name.endswith('.txt')):
                try:
                    # 验证是否是时间戳格式的目录
                    datetime.strptime(subdir.name, "%Y-%m-%d_%H-%M-%S")
                    log_dirs.append({
                        'name': subdir.name,
                        'path': str(subdir),
                        'is_current': subdir == self.log_dir,
                        'created_time': subdir.stat().st_ctime
                    })
                except ValueError:
                    continue
        
        # 按创建时间排序，最新的在前
        return sorted(log_dirs, key=lambda x: x['created_time'], reverse=True)
    
    def get_log_statistics(self) -> dict:
        """
        获取日志统计信息
        
        Returns:
            包含日志统计信息的字典
        """
        stats = {
            'current_session': {
                'directory': self.get_current_log_dir(),
                'files': 0,
                'total_size': 0
            },
            'all_sessions': {
                'directories': 0,
                'files': 0,
                'total_size': 0
            }
        }
        
        # 统计当前会话日志
        if self.log_dir and self.log_dir.exists():
            for log_file in self.log_dir.glob('*.log*'):
                if log_file.is_file():
                    stats['current_session']['files'] += 1
                    stats['current_session']['total_size'] += log_file.stat().st_size
        
        # 统计所有历史日志
        log_dirs = self.get_log_directories()
        stats['all_sessions']['directories'] = len(log_dirs)
        
        for dir_info in log_dirs:
            dir_path = Path(dir_info['path'])
            for log_file in dir_path.glob('*.log*'):
                if log_file.is_file():
                    stats['all_sessions']['files'] += 1
                    stats['all_sessions']['total_size'] += log_file.stat().st_size
        
        # 转换文件大小为可读格式
        def format_size(size_bytes):
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size_bytes < 1024:
                    return f"{size_bytes:.1f} {unit}"
                size_bytes /= 1024
            return f"{size_bytes:.1f} TB"
        
        stats['current_session']['size_formatted'] = format_size(stats['current_session']['total_size'])
        stats['all_sessions']['size_formatted'] = format_size(stats['all_sessions']['total_size'])
        
        return stats


# 全局日志管理器实例
_logger_manager = Logger()


def setup_logging(config: Dict[str, Any] = None) -> None:
    """
    设置全局日志系统
    
    Args:
        config: 日志配置字典
    """
    _logger_manager.setup(config)


def get_logger(name: str = None) -> logging.Logger:
    """
    获取日志器
    
    Args:
        name: 日志器名称，默认使用调用模块名
        
    Returns:
        日志器对象
    """
    if name is None:
        # 自动获取调用者模块名
        import inspect
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get('__name__', 'unknown')
    
    return _logger_manager.get_logger(name)


def log_exception(exception: Exception, context: str = "", logger_name: str = None) -> None:
    """
    记录异常信息的便捷函数
    
    Args:
        exception: 异常对象
        context: 上下文信息
        logger_name: 日志器名称
    """
    if logger_name is None:
        import inspect
        frame = inspect.currentframe().f_back
        logger_name = frame.f_globals.get('__name__', 'unknown')
    
    _logger_manager.log_exception(logger_name, exception, context)


def log_performance(operation: str, duration: float, details: str = "", logger_name: str = None) -> None:
    """
    记录性能信息的便捷函数
    
    Args:
        operation: 操作名称
        duration: 耗时（秒）
        details: 详细信息
        logger_name: 日志器名称
    """
    if logger_name is None:
        import inspect
        frame = inspect.currentframe().f_back
        logger_name = frame.f_globals.get('__name__', 'unknown')
    
    _logger_manager.log_performance(logger_name, operation, duration, details)


# 导出主要接口
__all__ = [
    'Logger',
    'setup_logging', 
    'get_logger',
    'log_exception',
    'log_performance'
] 