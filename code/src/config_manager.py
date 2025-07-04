import configparser
import os
from typing import Dict, Any, Optional

class ConfigManager:
    """配置文件管理器，负责读取和修改config.ini配置"""
    
    def __init__(self, config_path: str = "config.ini"):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径
        """
        # 确保使用绝对路径
        self.config_path = os.path.abspath(config_path)
        self.config = configparser.ConfigParser()
        self.load_config()
    
    def load_config(self) -> None:
        """加载配置文件"""
        if os.path.exists(self.config_path):
            self.config.read(self.config_path, encoding='utf-8')
        else:
            # 如果配置文件不存在，创建默认配置
            self.create_default_config()
    
    def create_default_config(self) -> None:
        """创建默认配置文件"""
        self.config['API'] = {
            'api_key': '',
            'api_url': 'https://api.siliconflow.cn/v1',
            'api_type': 'OpenAI API'
        }
        
        self.config['Settings'] = {
            'language': 'CN',
            'file_operation': 'copy',
            'image_analysis_model': 'Pro/Qwen/Qwen2-VL-7B-Instruct',
            'file_analysis_model': 'Pro/deepseek-ai/DeepSeek-R1-Distill-Qwen-7B',
            'decision_model': 'deepseek-ai/DeepSeek-R1-Distill-Qwen-32B',
            'enable_video_analysis': 'true',
            'video_analysis_model': 'Pro/Qwen/Qwen2-VL-7B-Instruct',
            'thread_count': '8',
            'subfolder_mode': 'whole'
        }
        
        self.config['Logging'] = {
            'log_level': 'INFO',
            'log_to_file': 'true',
            'log_to_console': 'true',
            'console_log_level': 'WARNING',
            'log_file_size': '10',
            'log_file_count': '5',
            'log_format': 'detailed',
            'log_dir': 'logs'
        }
        
        self.save_config()
    
    def get_config(self, section: str, key: str, fallback: Any = None) -> str:
        """
        获取配置项
        
        Args:
            section: 配置节名
            key: 配置键名
            fallback: 默认值
            
        Returns:
            配置值
        """
        return self.config.get(section, key, fallback=str(fallback) if fallback is not None else '')
    
    def set_config(self, section: str, key: str, value: Any) -> None:
        """
        设置配置项
        
        Args:
            section: 配置节名
            key: 配置键名
            value: 配置值
        """
        if section not in self.config:
            self.config.add_section(section)
        
        self.config.set(section, key, str(value))
    
    def get_all_config(self) -> Dict[str, Dict[str, str]]:
        """
        获取所有配置
        
        Returns:
            包含所有配置的字典
        """
        result = {}
        for section_name in self.config.sections():
            result[section_name] = dict(self.config.items(section_name))
        return result
    
    def update_config(self, section: str, config_dict: Dict[str, Any]) -> None:
        """
        批量更新配置
        
        Args:
            section: 配置节名
            config_dict: 配置字典
        """
        if section not in self.config:
            self.config.add_section(section)
            
        for key, value in config_dict.items():
            self.config.set(section, key, str(value))
    
    def save_config(self) -> None:
        """保存配置到文件"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                self.config.write(f)
        except Exception as e:
            raise Exception(f"保存配置文件失败: {e}")
    
    def validate_api_config(self) -> tuple[bool, str]:
        """
        验证API配置
        
        Returns:
            验证结果元组 (是否有效, 错误信息)
        """
        api_key = self.get_config('API', 'api_key')
        api_url = self.get_config('API', 'api_url')
        
        if not api_key:
            return False, "API密钥不能为空"
        
        if not api_url:
            return False, "API地址不能为空"
        
        # 简单的URL格式验证
        if not (api_url.startswith('http://') or api_url.startswith('https://')):
            return False, "API地址格式不正确"
        
        return True, ""
    
    def get_api_config(self) -> Dict[str, str]:
        """获取API相关配置"""
        return {
            'api_key': self.get_config('API', 'api_key'),
            'api_url': self.get_config('API', 'api_url'),
            'api_type': self.get_config('API', 'api_type')
        }
    
    def get_settings_config(self) -> Dict[str, str]:
        """获取设置相关配置"""
        return {
            'language': self.get_config('Settings', 'language'),
            'file_operation': self.get_config('Settings', 'file_operation'),
            'image_analysis_model': self.get_config('Settings', 'image_analysis_model'),
            'file_analysis_model': self.get_config('Settings', 'file_analysis_model'),
            'decision_model': self.get_config('Settings', 'decision_model'),
            'enable_video_analysis': self.get_config('Settings', 'enable_video_analysis'),
            'video_analysis_model': self.get_config('Settings', 'video_analysis_model'),
            'thread_count': self.get_config('Settings', 'thread_count'),
            'subfolder_mode': self.get_config('Settings', 'subfolder_mode')
        }
    
    def get_logging_config(self) -> Dict[str, str]:
        """获取日志相关配置"""
        return {
            'log_level': self.get_config('Logging', 'log_level'),
            'log_to_file': self.get_config('Logging', 'log_to_file'),
            'log_to_console': self.get_config('Logging', 'log_to_console'),
            'console_log_level': self.get_config('Logging', 'console_log_level'),
            'log_file_size': self.get_config('Logging', 'log_file_size'),
            'log_file_count': self.get_config('Logging', 'log_file_count'),
            'log_format': self.get_config('Logging', 'log_format'),
            'log_dir': self.get_config('Logging', 'log_dir')
        } 