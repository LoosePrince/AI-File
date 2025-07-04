#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志系统使用示例

演示如何在项目中使用日志功能
"""

import time
from config_manager import ConfigManager
from logger import setup_logging, get_logger, log_exception, log_performance


def demo_basic_logging():
    """演示基本日志记录功能"""
    logger = get_logger('demo_basic')
    
    logger.debug("这是一条调试信息")
    logger.info("这是一条信息日志")
    logger.warning("这是一条警告信息")
    logger.error("这是一条错误信息")
    logger.critical("这是一条严重错误信息")


def demo_exception_logging():
    """演示异常日志记录"""
    logger = get_logger('demo_exception')
    
    try:
        # 故意制造一个异常
        result = 10 / 0
    except Exception as e:
        # 使用日志系统记录异常
        log_exception(e, "除零运算错误")
        
        # 或者直接使用logger记录
        logger.error("计算过程中发生错误", exc_info=True)


def demo_performance_logging():
    """演示性能日志记录"""
    logger = get_logger('demo_performance')
    
    # 模拟一个耗时操作
    start_time = time.time()
    time.sleep(1)  # 模拟处理时间
    duration = time.time() - start_time
    
    # 记录性能信息
    log_performance("数据处理", duration, "处理了100条记录")


def demo_api_logging():
    """演示API调用日志记录"""
    from logger import _logger_manager
    
    # 模拟API调用记录
    _logger_manager.log_api_call(
        'demo_api',
        'POST',
        'https://api.example.com/v1/chat',
        status_code=200,
        duration=1.5
    )
    
    # 模拟API错误记录
    _logger_manager.log_api_call(
        'demo_api',
        'POST',
        'https://api.example.com/v1/chat',
        error="连接超时"
    )


def demo_file_operation_logging():
    """演示文件操作日志记录"""
    from logger import _logger_manager
    
    # 模拟文件操作记录
    _logger_manager.log_file_operation(
        'demo_file_ops',
        'copy',
        '/path/to/source.txt',
        '/path/to/destination.txt',
        'SUCCESS'
    )
    
    _logger_manager.log_file_operation(
        'demo_file_ops',
        'move',
        '/path/to/file.txt',
        '/path/to/new_location.txt',
        'ERROR',
        '权限不足'
    )


def demo_structured_logging():
    """演示结构化日志记录"""
    logger = get_logger('demo_structured')
    
    # 记录用户操作
    logger.info("USER_ACTION - 用户登录", extra={
        'user_id': '12345',
        'ip_address': '192.168.1.100',
        'user_agent': 'DocStream Navigator 2.0'
    })
    
    # 记录系统状态
    logger.info("SYSTEM_STATUS - 内存使用率: 75%")
    
    # 记录业务流程
    logger.info("PROCESS_FLOW - 开始文件分析流程")
    logger.info("PROCESS_FLOW - AI模型调用完成")
    logger.info("PROCESS_FLOW - 文件分类完成")


def demo_custom_logger():
    """演示自定义日志器"""
    # 为特定模块创建日志器
    ai_logger = get_logger('ai_module')
    file_logger = get_logger('file_processor')
    ui_logger = get_logger('ui_manager')
    
    ai_logger.info("正在调用AI模型进行图像分析")
    file_logger.info("开始批量处理文件")
    ui_logger.info("用户界面更新完成")


def main():
    """主演示函数"""
    print("="*50)
    print("日志系统使用演示")
    print("="*50)
    
    # 初始化配置管理器和日志系统
    config_manager = ConfigManager("../config.ini")
    log_config = config_manager.get_logging_config()
    
    # 设置日志系统
    setup_logging(log_config)
    
    main_logger = get_logger('main_demo')
    main_logger.info("开始日志系统演示")
    
    print("\n1. 基本日志记录演示...")
    demo_basic_logging()
    
    print("\n2. 异常日志记录演示...")
    demo_exception_logging()
    
    print("\n3. 性能日志记录演示...")
    demo_performance_logging()
    
    print("\n4. API调用日志记录演示...")
    demo_api_logging()
    
    print("\n5. 文件操作日志记录演示...")
    demo_file_operation_logging()
    
    print("\n6. 结构化日志记录演示...")
    demo_structured_logging()
    
    print("\n7. 自定义日志器演示...")
    demo_custom_logger()
    
    main_logger.info("日志系统演示完成")
    print("\n演示完成！请查看logs目录下的日志文件。")


if __name__ == "__main__":
    main() 