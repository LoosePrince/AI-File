import webview
import os
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from threading import Thread

from .config_manager import ConfigManager
from .logger import get_logger
from .file_selector import get_file_selector, FileDisplayManager
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
        self.progress_manager = initialize_progress_manager(thread_count, self.config_manager)
        
        # 注册进度回调
        self.progress_manager.add_progress_callback(self._on_progress_update)
        self.progress_manager.add_status_callback(self._on_status_change)
        
        # 文件选择和显示管理器
        self.file_selector = get_file_selector()
        self.file_display = FileDisplayManager()
        
        # 当前任务跟踪
        self.current_tasks: Dict[str, str] = {}  # task_type -> task_id
        
        # 当前选择的文件列表
        self.selected_files: List[Dict[str, Any]] = []
        
        # 存储待确认的分类结果 task_id -> results
        self._pending_classifications: Dict[str, Dict[str, Any]] = {}
        
        self.logger.info("UI管理器初始化完成")
    
    def create_window(self) -> None:
        """创建主窗口"""
        try:
            # 检查WebView是否可用
            import webview
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
            
        except ImportError as e:
            self.logger.warning(f"WebView不可用: {e}")
            self.window = None
        except Exception as e:
            self.logger.warning(f"创建窗口失败: {e}")
            self.window = None
    
    def start(self) -> None:
        """启动UI"""
        try:
            if not self.window:
                self.logger.warning("窗口未创建，尝试启动控制台模式...")
                self._run_console_mode()
                return
            
            self.logger.info("启动WebView界面...")
            
            # 启动webview
            webview.start(
                debug=False,  # 生产环境设为False
                private_mode=False,
                storage_path=os.path.join(os.path.expanduser("~"), ".docstream")
            )
            
            self.logger.info("WebView界面已关闭")
            
        except Exception as e:
            self.logger.error(f"WebView启动失败: {e}")
            self.logger.info("回退到控制台模式...")
            self._run_console_mode()
    
    def _run_console_mode(self):
        """运行控制台模式"""
        print("\n" + "="*50)
        print("文脉通控制台模式")
        print("="*50)
        
        while True:
            print("\n请选择操作:")
            print("1. 整理文件")
            print("2. 重命名文件")
            print("3. 退出")
            
            choice = input("请输入选项 (1-3): ").strip()
            
            if choice == '1':
                self._console_organize_files()
            elif choice == '2':
                self._console_rename_files()
            elif choice == '3':
                print("感谢使用文脉通！")
                break
            else:
                print("无效选项，请重新选择")
    
    def _console_organize_files(self):
        """控制台模式：整理文件"""
        print("\n" + "-"*30)
        print("文件整理模式")
        print("-"*30)
        
        # 选择文件夹
        folder_result = self.select_folder()
        
        if not folder_result.get('success'):
            print(f"选择文件夹失败: {folder_result.get('message', '未知错误')}")
            return
        
        folder_path = folder_result['folder']
        print(f"已选择文件夹: {folder_path}")
        
        # 询问是否递归扫描
        recursive_input = input("是否递归扫描子文件夹? (y/N): ").strip().lower()
        recursive = recursive_input in ['y', 'yes', '是']
        
        # 扫描文件夹
        print("正在扫描文件夹...")
        scan_result = self.scan_folder_for_files(folder_path, recursive)
        
        if not scan_result.get('success'):
            print(f"扫描失败: {scan_result.get('message', '未知错误')}")
            return
        
        files = scan_result['files']
        if not files:
            print("文件夹中没有找到可处理的文件")
            return
        
        # 显示文件列表
        print(f"\n找到 {len(files)} 个文件:")
        print("-"*50)
        for i, file_info in enumerate(files[:20]):  # 只显示前20个
            size_mb = file_info.get('size', 0) / (1024 * 1024)
            print(f"{i+1:3d}. {file_info['name']:<30} ({size_mb:.2f} MB) [{file_info.get('type', 'unknown').upper()}]")
        
        if len(files) > 20:
            print(f"... 还有 {len(files) - 20} 个文件")
        
        print("-"*50)
        print(f"总计: {len(files)} 个文件")
        print(f"总大小: {sum(f.get('size', 0) for f in files) / (1024 * 1024):.2f} MB")
        
        # 询问是否开始处理
        start_input = input("\n是否开始AI分析和整理? (y/N): ").strip().lower()
        if start_input in ['y', 'yes', '是']:
            file_paths = [f['path'] for f in files]
            print("正在启动AI分析...")
            self.start_processing(file_paths)
        else:
            print("已取消处理")
    
    def _console_rename_files(self):
        """控制台模式：重命名文件"""
        print("\n" + "-"*30)
        print("文件重命名模式")
        print("-"*30)
        
        print("1. 选择单个文件进行重命名")
        print("2. 选择文件夹批量重命名")
        choice = input("请选择 (1-2): ").strip()
        
        if choice == '1':
            # 选择文件
            files_result = self.select_files()
            if files_result.get('success') and files_result.get('files'):
                files = files_result['files']
                print(f"已选择 {len(files)} 个文件")
                # 这里可以添加重命名逻辑
                print("重命名功能正在开发中...")
            else:
                print("未选择任何文件")
                
        elif choice == '2':
            # 选择文件夹
            folder_result = self.select_folder()
            if folder_result.get('success'):
                folder_path = folder_result['folder']
                print(f"已选择文件夹: {folder_path}")
                
                # 扫描文件
                scan_result = self.scan_folder_for_files(folder_path, False)
                if scan_result.get('success'):
                    files = scan_result['files']
                    print(f"找到 {len(files)} 个可重命名的文件")
                    # 这里可以添加批量重命名逻辑
                    print("批量重命名功能正在开发中...")
                else:
                    print(f"扫描失败: {scan_result.get('message', '未知错误')}")
            else:
                print("未选择文件夹")
        else:
            print("无效选项")

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
            self.logger.info("启动文件选择对话框")
            
            # 使用新的文件选择器
            files = self.file_selector.select_files(
                title="选择要整理的文件",
                multiple=True
            )
            
            self.logger.debug(f"文件选择器返回类型: {type(files)}, 内容: {files}")
            
            if files:
                # 获取文件信息
                self.selected_files = []
                
                # 确保files是一个列表
                if not isinstance(files, list):
                    files = [files]
                
                for i, file_path in enumerate(files):
                    try:
                        # 类型检查和清理
                        if isinstance(file_path, list):
                            # 如果是嵌套列表，取第一个元素
                            if file_path:
                                file_path = file_path[0]
                            else:
                                continue
                        
                        # 确保是字符串
                        if not isinstance(file_path, (str, os.PathLike)):
                            self.logger.warning(f"文件路径类型错误: {type(file_path)}, 值: {file_path}")
                            continue
                        
                        # 转换为字符串
                        file_path = str(file_path).strip()
                        if not file_path:
                            continue
                        
                        self.logger.debug(f"处理文件路径 {i}: {file_path}")
                        
                        file_info = self.file_selector.get_file_info(file_path)
                        if 'error' not in file_info:
                            self.selected_files.append(file_info)
                        else:
                            self.logger.warning(f"获取文件信息失败: {file_info['error']}")
                            
                    except Exception as file_error:
                        self.logger.error(f"处理文件路径 {i} 时出错: {file_error}", exc_info=True)
                        continue
                
                self.logger.info(f"成功选择 {len(self.selected_files)} 个文件")
                
                return {
                    'success': True,
                    'files': [info['path'] for info in self.selected_files],  # 返回处理后的路径列表
                    'count': len(self.selected_files),
                    'message': f'成功选择 {len(self.selected_files)} 个文件'
                }
            
            return {
                'success': False,
                'files': [],
                'count': 0,
                'message': '未选择任何文件'
            }
            
        except Exception as e:
            error_msg = f"选择文件失败: {e}"
            self.logger.error(error_msg, exc_info=True)
            print(error_msg)
            return {
                'success': False,
                'files': [],
                'count': 0,
                'message': error_msg
            }
    
    def select_folder(self):
        """选择文件夹对话框"""
        try:
            self.logger.info("启动文件夹选择对话框")
            
            # 使用新的文件选择器
            folder_result = self.file_selector.select_folder(title="选择要整理的文件夹")
            
            self.logger.debug(f"文件夹选择结果类型: {type(folder_result)}, 内容: {folder_result}")
            
            if folder_result and folder_result.get('success') and folder_result.get('folder'):
                folder_path = folder_result['folder']
                
                # 确保文件夹路径是字符串
                if isinstance(folder_path, list):
                    if folder_path:
                        folder_path = folder_path[0]
                    else:
                        return {
                            'success': False,
                            'folder': None,
                            'message': '文件夹路径列表为空'
                        }
                
                if not isinstance(folder_path, (str, os.PathLike)):
                    return {
                        'success': False,
                        'folder': None,
                        'message': f'文件夹路径类型错误: {type(folder_path)}'
                    }
                
                folder_path = str(folder_path).strip()
                if not folder_path:
                    return {
                        'success': False,
                        'folder': None,
                        'message': '文件夹路径为空'
                    }
                
                self.logger.info(f"成功选择文件夹: {folder_path}")
                return {
                    'success': True,
                    'folder': folder_path,
                    'message': f'成功选择文件夹: {folder_path}'
                }
            
            return {
                'success': False,
                'folder': None,
                'message': folder_result.get('message', '未选择文件夹') if folder_result else '未选择文件夹'
            }
            
        except Exception as e:
            error_msg = f"选择文件夹失败: {e}"
            self.logger.error(error_msg, exc_info=True)
            print(error_msg)
            return {
                'success': False,
                'folder': None,
                'message': error_msg
            }
    
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
            
            # 辅助函数：安全获取文件名
            def safe_get_filename(file_path):
                if isinstance(file_path, str):
                    return os.path.basename(file_path), file_path
                elif isinstance(file_path, (list, tuple)) and len(file_path) > 0:
                    # 如果是列表，取第一个元素
                    first_item = file_path[0]
                    if isinstance(first_item, str):
                        return os.path.basename(first_item), first_item
                    else:
                        return str(first_item), str(first_item)
                else:
                    return str(file_path), str(file_path)
            
            # 构建文件列表 - 已完成的文件
            if hasattr(progress, 'processed_files') and progress.processed_files:
                for file_path in progress.processed_files:
                    name, path = safe_get_filename(file_path)
                    progress_data['files'].append({
                        'name': name,
                        'status': 'completed',
                        'path': path
                    })
            
            # 构建文件列表 - 待处理的文件
            if hasattr(progress, 'pending_files') and progress.pending_files:
                for file_path in progress.pending_files:
                    name, path = safe_get_filename(file_path)
                    progress_data['files'].append({
                        'name': name,
                        'status': 'pending',
                        'path': path
                    })
            
            # 构建文件列表 - 失败的文件
            if hasattr(progress, 'failed_files') and progress.failed_files:
                for failed_file in progress.failed_files:
                    if isinstance(failed_file, dict) and 'file' in failed_file:
                        name, path = safe_get_filename(failed_file['file'])
                        progress_data['files'].append({
                            'name': name,
                            'status': 'failed',
                            'path': path,
                            'error': failed_file.get('error', '未知错误')
                        })
                    else:
                        # 兼容其他格式
                        name, path = safe_get_filename(failed_file)
                        progress_data['files'].append({
                            'name': name,
                            'status': 'failed',
                            'path': path,
                            'error': '处理失败'
                        })
            
            # 如果有分类结果，附加到 progress_data
            if hasattr(progress, 'details') and 'classification_results' in progress.details:
                progress_data['classification_results'] = True
            
            # 向前端发送进度更新
            self._send_progress_update(progress_data)
            
            # 如果包含分类结果且尚未通知前端
            if hasattr(progress, 'details') and 'classification_results' in progress.details:
                if task_id not in self._pending_classifications:
                    self._pending_classifications[task_id] = progress.details['classification_results']
                    js_payload = json.dumps({
                        'task_id': task_id,
                        'results': self._pending_classifications[task_id]
                    })
                    webview.windows[0].evaluate_js(f"window.onClassificationReady({js_payload})")
            
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
    
    # ==================== 文件显示和管理 API ====================
    
    def get_selected_files(self):
        """获取当前选择的文件列表"""
        try:
            return {
                'success': True,
                'files': self.selected_files,
                'count': len(self.selected_files)
            }
        except Exception as e:
            return {
                'success': False,
                'message': str(e)
            }
    
    def scan_folder_for_files(self, folder_path: str, recursive: bool = False):
        """扫描文件夹获取文件列表"""
        try:
            self.logger.info(f"扫描文件夹: {folder_path}, 递归: {recursive}")
            
            # 使用文件选择器扫描文件夹
            scan_result = self.file_selector.scan_folder(
                folder_path, 
                recursive=recursive
            )
            
            if 'error' in scan_result:
                return {
                    'success': False,
                    'message': scan_result['error']
                }
            
            # 更新选择的文件列表
            self.selected_files = scan_result['files']
            
            self.logger.info(f"扫描完成，找到 {len(self.selected_files)} 个文件")
            
            return {
                'success': True,
                'folder': scan_result['folder'],
                'files': scan_result['files'],
                'folders': scan_result['folders'],
                'total_files': scan_result['total_files'],
                'total_folders': scan_result['total_folders']
            }
            
        except Exception as e:
            error_msg = f"扫描文件夹失败: {e}"
            self.logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }
    
    def generate_file_list_html(self, show_checkboxes: bool = True):
        """生成文件列表的HTML"""
        try:
            html = self.file_display.create_file_list_html(
                self.selected_files,
                show_checkboxes=show_checkboxes
            )
            
            return {
                'success': True,
                'html': html,
                'file_count': len(self.selected_files)
            }
            
        except Exception as e:
            error_msg = f"生成文件列表HTML失败: {e}"
            self.logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }
    
    def remove_file_from_list(self, file_index: int):
        """从文件列表中移除文件"""
        try:
            if 0 <= file_index < len(self.selected_files):
                removed_file = self.selected_files.pop(file_index)
                self.logger.info(f"移除文件: {removed_file.get('name', 'unknown')}")
                
                return {
                    'success': True,
                    'message': f"已移除文件: {removed_file.get('name', 'unknown')}",
                    'remaining_count': len(self.selected_files)
                }
            else:
                return {
                    'success': False,
                    'message': '文件索引无效'
                }
                
        except Exception as e:
            error_msg = f"移除文件失败: {e}"
            self.logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }
    
    def clear_file_list(self):
        """清空文件列表"""
        try:
            count = len(self.selected_files)
            self.selected_files.clear()
            
            self.logger.info(f"清空文件列表，共移除 {count} 个文件")
            
            return {
                'success': True,
                'message': f"已清空 {count} 个文件"
            }
            
        except Exception as e:
            error_msg = f"清空文件列表失败: {e}"
            self.logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }
    
    # ==================== 文件重命名 API ====================
    
    def get_rename_dialog_html(self, file_index: int, suggestions: List[str] = None):
        """获取重命名对话框HTML"""
        try:
            if not (0 <= file_index < len(self.selected_files)):
                return {
                    'success': False,
                    'message': '文件索引无效'
                }
            
            file_info = self.selected_files[file_index]
            
            html = self.file_display.create_rename_dialog_html(
                file_info,
                suggestions=suggestions
            )
            
            return {
                'success': True,
                'html': html,
                'file_info': file_info
            }
            
        except Exception as e:
            error_msg = f"生成重命名对话框失败: {e}"
            self.logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }
    
    def generate_ai_filename_suggestions(self, file_index: int):
        """生成AI文件名建议"""
        try:
            if not (0 <= file_index < len(self.selected_files)):
                return {
                    'success': False,
                    'message': '文件索引无效'
                }
            
            file_info = self.selected_files[file_index]
            file_path = file_info['path']
            
            # 这里可以集成AI客户端来生成建议
            # 目前返回一些示例建议
            base_name = Path(file_path).stem
            suggestions = [
                f"{base_name}_智能重命名1",
                f"{base_name}_智能重命名2", 
                f"{base_name}_智能重命名3"
            ]
            
            self.logger.info(f"为文件 {file_info['name']} 生成AI建议")
            
            return {
                'success': True,
                'suggestions': suggestions,
                'file_info': file_info
            }
            
        except Exception as e:
            error_msg = f"生成AI建议失败: {e}"
            self.logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }
    
    def rename_file(self, file_index: int, new_name: str):
        """重命名文件"""
        try:
            if not (0 <= file_index < len(self.selected_files)):
                return {
                    'success': False,
                    'message': '文件索引无效'
                }
            
            file_info = self.selected_files[file_index]
            old_path = Path(file_info['path'])
            
            # 构建新的文件路径
            new_path = old_path.parent / f"{new_name}{old_path.suffix}"
            
            # 检查目标文件是否已存在
            if new_path.exists():
                return {
                    'success': False,
                    'message': f"目标文件已存在: {new_path.name}"
                }
            
            # 执行重命名
            old_path.rename(new_path)
            
            # 更新文件信息
            file_info['name'] = new_path.name
            file_info['path'] = str(new_path)
            
            self.logger.info(f"文件重命名成功: {old_path.name} -> {new_path.name}")
            
            return {
                'success': True,
                'message': f"重命名成功: {new_path.name}",
                'new_name': new_path.name,
                'new_path': str(new_path)
            }
            
        except Exception as e:
            error_msg = f"重命名文件失败: {e}"
            self.logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }
    
    def preview_file(self, file_path: str):
        """预览文件"""
        try:
            path = Path(file_path)
            
            if not path.exists():
                return {
                    'success': False,
                    'message': '文件不存在'
                }
            
            # 获取文件信息
            file_info = self.file_selector.get_file_info(file_path)
            
            # 根据文件类型生成预览信息
            preview_info = {
                'name': file_info['name'],
                'path': file_info['path'],
                'size': file_info['size_human'],
                'type': file_info['type'],
                'extension': file_info['extension']
            }
            
            # 对于图片文件，可以添加缩略图路径
            if file_info['type'] == 'images':
                preview_info['thumbnail'] = file_path  # 前端可以直接显示
            
            # 对于文本文件，可以读取部分内容
            elif file_info['type'] in ['documents', 'code', 'data']:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        preview_info['content_preview'] = f.read(500)  # 前500字符
                except:
                    preview_info['content_preview'] = "无法预览内容"
            
            return {
                'success': True,
                'preview': preview_info
            }
            
        except Exception as e:
            error_msg = f"预览文件失败: {e}"
            self.logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }

    # ==================== 分类结果确认 ====================

    def get_classification_results(self, task_id: str):
        """前端请求获取分类结果"""
        results = self._pending_classifications.get(task_id)
        if results is None:
            return {'success': False, 'message': '未找到分类结果'}
        return {'success': True, 'results': results}

    def confirm_organize(self, task_id: str, target_dir: str = None):
        """前端确认整理，创建整理任务"""
        try:
            from .classification_engine import ClassificationEngine
            if task_id not in self._pending_classifications:
                return {'success': False, 'message': '没有待确认的分类结果'}

            classification_results = self._pending_classifications.pop(task_id)

            if not target_dir:
                # 默认同级 organized 目录
                any_path = next(iter(classification_results))
                target_dir = str(Path(any_path).resolve().parent / 'organized')

            engine = ClassificationEngine(self.config_manager)
            organize_summary = engine.organize_files(classification_results, target_dir)

            return {'success': True, 'summary': organize_summary}
        except Exception as e:
            self.logger.error(f"确认整理失败: {e}", exc_info=True)
            return {'success': False, 'message': str(e)}