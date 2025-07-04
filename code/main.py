#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文脉通 (DocStream Navigator) - 重构版
一款基于人工智能技术的智能文件整理工具

主程序入口文件
"""

import sys
import os
import traceback
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from src.config_manager import ConfigManager
    from src.ui_manager import UIManager
    from src.logger import setup_logging, get_logger
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保所有依赖已正确安装")
    sys.exit(1)

class DocStreamApp:
    """文脉通主应用程序类"""
    
    def __init__(self):
        """初始化应用程序"""
        self.app_name = "文脉通 (DocStream Navigator)"
        self.version = "2.0.0"
        
        # 获取配置文件路径
        self.config_path = os.path.join(os.path.dirname(__file__), "config.ini")
        
        # 初始化组件
        self.config_manager = None
        self.ui_manager = None
        self.logger = None
        
    def initialize(self) -> bool:
        """
        初始化应用程序组件
        
        Returns:
            初始化是否成功
        """
        try:
            print(f"正在启动 {self.app_name} v{self.version}...")
            
            # 初始化配置管理器
            print("初始化配置管理器...")
            self.config_manager = ConfigManager(self.config_path)
            
            # 设置日志系统
            print("初始化日志系统...")
            log_config = self.config_manager.get_logging_config()
            setup_logging(log_config)
            self.logger = get_logger('main')
            self.logger.info(f"{self.app_name} v{self.version} 正在启动")
            
            # 验证配置
            self.logger.info("验证API配置...")
            is_valid, error_msg = self.config_manager.validate_api_config()
            if not is_valid:
                self.logger.warning(f"API配置验证失败: {error_msg}")
                print(f"配置验证失败: {error_msg}")
                print("请在设置页面配置正确的API信息")
            else:
                self.logger.info("API配置验证通过")
            
            # 初始化UI管理器
            self.logger.info("初始化UI管理器...")
            self.ui_manager = UIManager(self.config_manager)
            
            self.logger.info("应用程序初始化完成")
            print("应用程序初始化完成")
            return True
            
        except Exception as e:
            error_msg = f"初始化失败: {e}"
            print(error_msg)
            if self.logger:
                self.logger.error(error_msg, exc_info=True)
            traceback.print_exc()
            return False
    
    def run(self) -> None:
        """运行应用程序"""
        try:
            if not self.initialize():
                error_msg = "应用程序初始化失败，无法启动"
                print(error_msg)
                if self.logger:
                    self.logger.error(error_msg)
                return
            
            self.logger.info("启动用户界面...")
            print("启动用户界面...")
            
            # 创建并启动UI
            self.ui_manager.create_window()
            self.ui_manager.start()
            
        except KeyboardInterrupt:
            interrupt_msg = "用户中断，正在退出..."
            print(f"\n{interrupt_msg}")
            if self.logger:
                self.logger.info(interrupt_msg)
        except Exception as e:
            error_msg = f"运行时错误: {e}"
            print(error_msg)
            if self.logger:
                self.logger.error(error_msg, exc_info=True)
            traceback.print_exc()
        finally:
            self.cleanup()
    
    def cleanup(self) -> None:
        """清理资源"""
        try:
            cleanup_msg = "清理应用程序资源..."
            print(cleanup_msg)
            if self.logger:
                self.logger.info(cleanup_msg)
            
            # 停止进度管理器
            if self.ui_manager:
                if hasattr(self.ui_manager, 'progress_manager') and self.ui_manager.progress_manager:
                    if self.logger:
                        self.logger.info("停止进度管理器...")
                    self.ui_manager.progress_manager.stop()
            
            # 保存配置
            if self.config_manager:
                if self.logger:
                    self.logger.info("保存配置文件...")
                self.config_manager.save_config()
            
            success_msg = "资源清理完成"
            print(success_msg)
            if self.logger:
                self.logger.info(success_msg)
            
        except Exception as e:
            error_msg = f"清理资源时发生错误: {e}"
            print(error_msg)
            if self.logger:
                self.logger.error(error_msg, exc_info=True)

def check_dependencies() -> bool:
    """
    检查依赖包是否安装
    
    Returns:
        依赖是否满足
    """
    required_packages = [
        'webview',
        'configparser'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("缺少以下依赖包:")
        for package in missing_packages:
            print(f"  - {package}")
        print("\n请运行以下命令安装依赖:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    return True

def main():
    """主函数"""
    try:
        print("="*50)
        print("文脉通 (DocStream Navigator) v2.0.0")
        print("一款基于人工智能技术的智能文件整理工具")
        print("="*50)
        
        # 检查Python版本
        if sys.version_info < (3, 8):
            print("错误: 需要Python 3.8或更高版本")
            print(f"当前版本: Python {sys.version}")
            sys.exit(1)
        
        # 检查依赖
        if not check_dependencies():
            sys.exit(1)
        
        # 创建并运行应用程序
        app = DocStreamApp()
        app.run()
        
    except Exception as e:
        print(f"程序启动失败: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
