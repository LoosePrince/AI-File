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
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime


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
        # 确定日志目录路径
        if os.path.isabs(self.config['log_dir']):
            self.log_dir = Path(self.config['log_dir'])
        else:
            # 相对于项目根目录
            project_root = Path(__file__).parent.parent.parent
            self.log_dir = project_root / self.config['log_dir']
        
        # 创建目录
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
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
            encoding='utf-8'
        )
        
        file_handler.setFormatter(self._get_formatter('file'))
        logger.addHandler(file_handler)
    
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
    
    def get_log_files(self) -> list:
        """
        获取所有日志文件列表
        
        Returns:
            日志文件路径列表
        """
        if not self.log_dir or not self.log_dir.exists():
            return []
        
        return [str(f) for f in self.log_dir.glob('*.log*')]
    
    def clear_logs(self, keep_current: bool = True) -> None:
        """
        清理日志文件
        
        Args:
            keep_current: 是否保留当前日志文件
        """
        if not self.log_dir or not self.log_dir.exists():
            return
        
        for log_file in self.log_dir.glob('*.log*'):
            if keep_current and not log_file.name.endswith('.1'):
                # 保留主日志文件，删除备份文件
                if '.' in log_file.stem and log_file.stem.split('.')[-1].isdigit():
                    log_file.unlink()
            else:
                log_file.unlink()


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