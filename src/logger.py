import os
import logging
import datetime

class Logger:
    def __init__(self, log_dir='log'):
        os.makedirs(log_dir, exist_ok=True)  # 创建日志目录
        log_file = os.path.join(log_dir, 'app.log')
        error_log_file = os.path.join(log_dir, 'log_error.log')  # 错误日志文件
        
        # 设置日志格式
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        # 创建文件处理器 - 常规日志
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        
        # 创建文件处理器 - 错误日志
        error_handler = logging.FileHandler(error_log_file, encoding='utf-8')
        error_handler.setFormatter(formatter)
        error_handler.setLevel(logging.ERROR)  # 只处理错误级别及以上的日志
        
        # 获取根日志记录器
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
        
        # 清除现有的处理器
        logger.handlers = []
        
        # 在错误日志文件中添加分隔线
        with open(error_log_file, 'a', encoding='utf-8') as f:
            f.write(f"\n------------\n{datetime.datetime.now()} - 新会话开始\n------------\n")
        
        # 添加处理器
        logger.addHandler(file_handler)
        logger.addHandler(error_handler)
        
    def log_info(self, message):
        logging.info(message)
        
    def log_error(self, message):
        logging.error(message)
        
    def log_warning(self, message):
        logging.warning(message) 