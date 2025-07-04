import webview
import os
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from threading import Thread
import tkinter as tk
from tkinter import filedialog

from .config_manager import ConfigManager
from .logger import get_logger
from .progress_manager import (
    get_progress_manager, initialize_progress_manager, 
    TaskStatus, TaskPriority, FileProcessingHandler
)

class UIManager:
    """UI管理器，负责创建和管理用户界面"""
    
    def __init__(self, config_manager: ConfigManager):
        """
        初始化UI管理器
        
        Args:
            config_manager: 配置管理器实例
        """
        self.config_manager = config_manager
        self.window = None
        self.is_maximized = False
        self.logger = get_logger('ui_manager')
        
        # 获取UI资源路径
        self.ui_path = Path(__file__).parent / "ui"
        self.index_path = self.ui_path / "index.html"
        
        # 初始化进度管理器
        thread_count = int(config_manager.get_config('Settings', 'thread_count', 4))
        self.progress_manager = initialize_progress_manager(thread_count)
        
        # 注册进度回调
        self.progress_manager.add_progress_callback(self._on_progress_update)
        self.progress_manager.add_status_callback(self._on_status_change)
        
        # 当前任务跟踪
        self.current_tasks: Dict[str, str] = {}  # task_type -> task_id
        
        self.logger.info("UI管理器初始化完成")
    
    def create_window(self) -> None:
        """创建主窗口"""
        self.logger.info("创建主窗口...")
        
        if not self.index_path.exists():
            error_msg = f"UI文件不存在: {self.index_path}"
            self.logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        # 创建webview窗口
        self.window = webview.create_window(
            title="文脉通 - DocStream Navigator",
            url=str(self.index_path),
            width=1200,
            height=800,
            min_size=(800, 600),
            resizable=True,
            maximized=False,
            on_top=False,
            js_api=self
        )
        
        self.logger.info("主窗口创建完成")
    
    def start(self) -> None:
        """启动UI"""
        if not self.window:
            error_msg = "窗口未创建，请先调用create_window()"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        self.logger.info("启动WebView界面...")
        
        # 启动webview
        webview.start(
            debug=False,  # 生产环境设为False
            private_mode=False,
            storage_path=os.path.join(os.path.expanduser("~"), ".docstream")
        )
        
        self.logger.info("WebView界面已关闭")

    # ==================== API接口方法 ====================
    # 这些方法会被前端JavaScript调用
    
    def get_config(self):
        """获取配置信息"""
        try:
            self.logger.debug("获取配置信息")
            config = self.config_manager.get_all_config()
            self.logger.debug(f"成功获取配置: {len(config)} 个节")
            return config
        except Exception as e:
            error_msg = f"获取配置失败: {e}"
            self.logger.error(error_msg, exc_info=True)
            print(error_msg)
            return {}
    
    def save_config(self, config):
        """
        保存配置信息
        
        Args:
            config: 配置字典
            
        Returns:
            保存结果
        """
        try:
            self.logger.info("保存配置信息...")
            
            # 更新API配置
            if 'API' in config:
                self.logger.debug(f"更新API配置: {list(config['API'].keys())}")
                for key, value in config['API'].items():
                    if value is not None and str(value).strip() != '':
                        self.config_manager.set_config('API', key, value)
            
            # 更新Settings配置
            if 'Settings' in config:
                self.logger.debug(f"更新Settings配置: {list(config['Settings'].keys())}")
                for key, value in config['Settings'].items():
                    if value is not None and str(value).strip() != '':
                        self.config_manager.set_config('Settings', key, value)
            
            # 更新Logging配置（如果存在）
            if 'Logging' in config:
                self.logger.debug(f"更新Logging配置: {list(config['Logging'].keys())}")
                for key, value in config['Logging'].items():
                    if value is not None and str(value).strip() != '':
                        self.config_manager.set_config('Logging', key, value)
            
            # 保存到文件
            self.config_manager.save_config()
            
            self.logger.info("配置保存成功")
            return {
                'success': True,
                'message': '配置保存成功'
            }
            
        except Exception as e:
            error_msg = f"保存配置失败: {e}"
            self.logger.error(error_msg, exc_info=True)
            print(error_msg)
            return {
                'success': False,
                'message': error_msg
            }
    
    def validate_api_config(self):
        """验证API配置"""
        try:
            is_valid, error_msg = self.config_manager.validate_api_config()
            return {
                'valid': is_valid,
                'message': error_msg
            }
        except Exception as e:
            return {
                'valid': False,
                'message': f"验证失败: {e}"
            }
    
    def select_files(self):
        """选择文件对话框"""
        try:
            # 创建临时Tkinter窗口用于文件对话框
            root = tk.Tk()
            root.withdraw()  # 隐藏主窗口
            root.attributes('-topmost', True)  # 置顶显示
            
            # 打开文件选择对话框
            files = filedialog.askopenfilenames(
                title="选择要整理的文件",
                filetypes=[
                    ("所有支持的文件", "*.jpg *.jpeg *.png *.gif *.bmp *.tiff *.mp4 *.avi *.mov *.wmv *.flv *.pdf *.doc *.docx *.xls *.xlsx *.ppt *.pptx *.txt *.zip *.rar *.7z"),
                    ("图像文件", "*.jpg *.jpeg *.png *.gif *.bmp *.tiff"),
                    ("视频文件", "*.mp4 *.avi *.mov *.wmv *.flv *.mkv"),
                    ("文档文件", "*.pdf *.doc *.docx *.xls *.xlsx *.ppt *.pptx *.txt"),
                    ("压缩文件", "*.zip *.rar *.7z *.tar *.gz"),
                    ("所有文件", "*.*")
                ]
            )
            
            root.destroy()
            return list(files) if files else []
            
        except Exception as e:
            print(f"选择文件失败: {e}")
            return []
    
    def select_folder(self):
        """选择文件夹对话框"""
        try:
            # 创建临时Tkinter窗口用于文件夹对话框
            root = tk.Tk()
            root.withdraw()  # 隐藏主窗口
            root.attributes('-topmost', True)  # 置顶显示
            
            # 打开文件夹选择对话框
            folder = filedialog.askdirectory(
                title="选择要整理的文件夹"
            )
            
            root.destroy()
            return folder if folder else None
            
        except Exception as e:
            print(f"选择文件夹失败: {e}")
            return None
    
    def start_processing(self, files):
        """开始处理文件"""
        try:
            # 检查是否有活跃的文件处理任务
            if 'file_processing' in self.current_tasks:
                task_id = self.current_tasks['file_processing']
                task = self.progress_manager.get_task(task_id)
                if task and task.status in [TaskStatus.RUNNING, TaskStatus.PAUSED]:
                    return {
                        'success': False,
                        'message': '已有文件处理任务在进行中'
                    }
            
            # 提交新的文件处理任务
            task_id = self.progress_manager.submit_task(
                task_type='file_processing',
                name='文件智能整理',
                description=f'处理 {len(files)} 个文件/文件夹',
                priority=TaskPriority.NORMAL,
                files=files
            )
            
            self.current_tasks['file_processing'] = task_id
            
            self.logger.info(f"文件处理任务已提交: {task_id}")
            return {
                'success': True,
                'message': '处理已启动',
                'task_id': task_id
            }
            
        except Exception as e:
            error_msg = f"启动文件处理失败: {e}"
            self.logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }
    
    def pause_processing(self):
        """暂停处理"""
        try:
            if 'file_processing' not in self.current_tasks:
                return {
                    'success': False,
                    'message': '没有正在执行的任务'
                }
            
            task_id = self.current_tasks['file_processing']
            if self.progress_manager.pause_task(task_id):
                self.logger.info(f"任务已暂停: {task_id}")
                return {
                    'success': True,
                    'message': '任务已暂停'
                }
            else:
                return {
                    'success': False,
                    'message': '暂停任务失败'
                }
        except Exception as e:
            error_msg = f"暂停任务失败: {e}"
            self.logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }
    
    def cancel_processing(self):
        """取消处理"""
        try:
            if 'file_processing' not in self.current_tasks:
                return {
                    'success': False,
                    'message': '没有正在执行的任务'
                }
            
            task_id = self.current_tasks['file_processing']
            if self.progress_manager.cancel_task(task_id):
                del self.current_tasks['file_processing']
                self.logger.info(f"任务已取消: {task_id}")
                return {
                    'success': True,
                    'message': '处理已取消'
                }
            else:
                return {
                    'success': False,
                    'message': '取消任务失败'
                }
        except Exception as e:
            error_msg = f"取消处理失败: {e}"
            self.logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }
    
    def minimize_window(self):
        """最小化窗口"""
        try:
            if self.window and len(webview.windows) > 0:
                webview.windows[0].minimize()
                return {'success': True}
            return {'success': False}
        except Exception as e:
            print(f"最小化窗口失败: {e}")
            return {'success': False, 'message': str(e)}
    
    def toggle_maximize(self):
        """切换最大化/还原窗口"""
        try:
            if self.window and len(webview.windows) > 0:
                if self.is_maximized:
                    webview.windows[0].restore()
                    self.is_maximized = False
                else:
                    webview.windows[0].maximize()
                    self.is_maximized = True
                return {'success': True}
            return {'success': False}
        except Exception as e:
            print(f"切换最大化失败: {e}")
            return {'success': False, 'message': str(e)}
    
    def close_window(self):
        """关闭窗口"""
        try:
            if self.window and len(webview.windows) > 0:
                webview.windows[0].destroy()
                return {'success': True}
            return {'success': False}
        except Exception as e:
            print(f"关闭窗口失败: {e}")
            return {'success': False, 'message': str(e)}
    
    def get_app_info(self):
        """获取应用程序信息"""
        return {
            'name': '文脉通 (DocStream Navigator)',
            'version': '2.0.0',
            'description': '一款基于人工智能技术的智能文件整理工具',
            'author': 'ai-file.xzt.plus',
            'license': 'Apache 2.0'
        }
    
    def get_log_files(self):
        """获取日志文件列表"""
        try:
            from .logger import _logger_manager
            files = _logger_manager.get_log_files()
            self.logger.debug(f"获取到 {len(files)} 个日志文件")
            return {
                'success': True,
                'files': files
            }
        except Exception as e:
            error_msg = f"获取日志文件失败: {e}"
            self.logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }
    
    def clear_logs(self, keep_current=True):
        """清理日志文件"""
        try:
            from .logger import _logger_manager
            _logger_manager.clear_logs(keep_current)
            self.logger.info(f"日志文件清理完成 (保留当前文件: {keep_current})")
            return {
                'success': True,
                'message': '日志清理完成'
            }
        except Exception as e:
            error_msg = f"清理日志文件失败: {e}"
            self.logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }
    
    def resume_processing(self):
        """恢复处理"""
        try:
            if 'file_processing' not in self.current_tasks:
                return {
                    'success': False,
                    'message': '没有可恢复的任务'
                }
            
            task_id = self.current_tasks['file_processing']
            if self.progress_manager.resume_task(task_id):
                self.logger.info(f"任务已恢复: {task_id}")
                return {
                    'success': True,
                    'message': '任务已恢复'
                }
            else:
                return {
                    'success': False,
                    'message': '恢复任务失败'
                }
        except Exception as e:
            error_msg = f"恢复任务失败: {e}"
            self.logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }
    
    def get_task_status(self, task_id: str = None):
        """获取任务状态"""
        try:
            if task_id is None:
                # 获取当前文件处理任务状态
                if 'file_processing' in self.current_tasks:
                    task_id = self.current_tasks['file_processing']
                else:
                    return {
                        'success': False,
                        'message': '没有活跃的任务'
                    }
            
            task = self.progress_manager.get_task(task_id)
            if task:
                return {
                    'success': True,
                    'task': {
                        'id': task.task_id,
                        'name': task.name,
                        'status': task.status.value,
                        'progress': {
                            'percentage': task.progress.percentage,
                            'current_step': task.progress.current_step,
                            'processed_files': len(task.progress.processed_files),
                            'failed_files': len(task.progress.failed_files),
                            'total_files': len(task.progress.processed_files) + len(task.progress.pending_files)
                        }
                    }
                }
            else:
                return {
                    'success': False,
                    'message': '任务不存在'
                }
        except Exception as e:
            error_msg = f"获取任务状态失败: {e}"
            self.logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }
    
    def get_progress_statistics(self):
        """获取进度统计信息"""
        try:
            stats = self.progress_manager.get_statistics()
            return {
                'success': True,
                'statistics': stats
            }
        except Exception as e:
            error_msg = f"获取统计信息失败: {e}"
            self.logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }

    # ==================== 内部方法 ====================
    
    def _on_progress_update(self, task_id: str, progress):
        """
        进度更新回调
        
        Args:
            task_id: 任务ID
            progress: 进度对象
        """
        try:
            # 转换为前端格式
            progress_data = {
                'task_id': task_id,
                'percentage': progress.percentage,
                'text': progress.current_step or f'处理中... ({progress.completed_steps}/{progress.total_steps})',
                'completed': progress.percentage >= 100,
                'files': []
            }
            
            # 构建文件列表
            for file_path in progress.processed_files:
                progress_data['files'].append({
                    'name': os.path.basename(file_path),
                    'status': 'completed',
                    'path': file_path
                })
            
            for file_path in progress.pending_files:
                progress_data['files'].append({
                    'name': os.path.basename(file_path),
                    'status': 'pending',
                    'path': file_path
                })
            
            for failed_file in progress.failed_files:
                progress_data['files'].append({
                    'name': os.path.basename(failed_file['file']),
                    'status': 'failed',
                    'path': failed_file['file'],
                    'error': failed_file['error']
                })
            
            # 向前端发送进度更新
            self._send_progress_update(progress_data)
            
        except Exception as e:
            self.logger.error(f"处理进度更新回调失败: {e}", exc_info=True)
    
    def _on_status_change(self, task_id: str, status):
        """
        状态变更回调
        
        Args:
            task_id: 任务ID
            status: 新状态
        """
        try:
            self.logger.debug(f"任务状态变更: {task_id} -> {status.value}")
            
            # 发送状态通知
            if status == TaskStatus.COMPLETED:
                self._send_notification("文件处理完成", "success")
                if 'file_processing' in self.current_tasks and self.current_tasks['file_processing'] == task_id:
                    del self.current_tasks['file_processing']
            elif status == TaskStatus.FAILED:
                task = self.progress_manager.get_task(task_id)
                error_msg = task.error_message if task else "未知错误"
                self._send_notification(f"文件处理失败: {error_msg}", "error")
                if 'file_processing' in self.current_tasks and self.current_tasks['file_processing'] == task_id:
                    del self.current_tasks['file_processing']
            elif status == TaskStatus.CANCELLED:
                self._send_notification("文件处理已取消", "warning")
                if 'file_processing' in self.current_tasks and self.current_tasks['file_processing'] == task_id:
                    del self.current_tasks['file_processing']
            elif status == TaskStatus.PAUSED:
                self._send_notification("文件处理已暂停", "warning")
            elif status == TaskStatus.RUNNING:
                self._send_notification("文件处理已开始", "info")
            
        except Exception as e:
            self.logger.error(f"处理状态变更回调失败: {e}", exc_info=True)
    
    def _send_progress_update(self, progress):
        """
        向前端发送进度更新
        
        Args:
            progress: 进度信息
        """
        try:
            if self.window and len(webview.windows) > 0:
                # 调用前端JavaScript函数
                webview.windows[0].evaluate_js(f"window.updateProgress({json.dumps(progress)})")
        except Exception as e:
            print(f"发送进度更新失败: {e}")
    
    def _send_notification(self, message, type="info"):
        """
        向前端发送通知
        
        Args:
            message: 通知消息
            type: 通知类型 (info, success, warning, error)
        """
        try:
            if self.window and len(webview.windows) > 0:
                # 调用前端JavaScript函数
                webview.windows[0].evaluate_js(f"window.showNotification('{message}', '{type}')")
        except Exception as e:
            print(f"发送通知失败: {e}") 