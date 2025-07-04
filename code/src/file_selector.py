#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件和文件夹选择器模块

当前仅支持两种方式：
1. Windows Win32 系统文件/文件夹选择器
2. 手动路径输入
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
import subprocess

# Windows特定
if sys.platform == 'win32':
    try:
        import win32gui
        import win32con
        import win32api
        from win32com.shell import shell, shellcon
        import pythoncom
        WIN32_AVAILABLE = True
    except ImportError:
        WIN32_AVAILABLE = False
else:
    WIN32_AVAILABLE = False

from .logger import get_logger

WEBVIEW_AVAILABLE = False  # WebView 支持已移除
TKINTER_AVAILABLE = False  # Tkinter 支持已移除

class FileSelector:
    """文件和文件夹选择器"""
    
    def __init__(self):
        self.logger = get_logger('file_selector')
        self.supported_extensions = {
            'images': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.svg'],
            'videos': ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv', '.webm', '.m4v'],
            'audio': ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a'],
            'documents': ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.rtf', '.odt'],
            'archives': ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz'],
            'code': ['.py', '.js', '.html', '.css', '.java', '.cpp', '.c', '.php', '.go', '.rs'],
            'data': ['.json', '.xml', '.csv', '.yaml', '.yml', '.ini', '.conf']
        }
        
        # 检测可用的选择方式
        self.available_methods = self._detect_available_methods()
        self.logger.info(f"可用的文件选择方式: {self.available_methods}")
    
    def _detect_available_methods(self) -> List[str]:
        """检测可用的文件选择方法"""
        methods = []
        
        # 仅保留系统原生选择器（Win32）和手动输入

        if os.name == 'nt':
            methods.append('win32')
            self.logger.debug("Win32 文件选择器可用")

        # 手动输入始终可用
        methods.append('manual')
        self.logger.debug("手动输入可用")

        self.logger.info(f"可用的文件选择方法: {methods}")
        return methods
    
    def select_files(self, title: str = "选择文件", 
                     file_types: Optional[List[Dict[str, str]]] = None,
                     multiple: bool = True) -> List[str]:
        """
        选择文件
        
        Args:
            title: 对话框标题
            file_types: 文件类型过滤器列表 [{'name': '描述', 'extensions': ['.ext1', '.ext2']}]
            multiple: 是否允许多选
            
        Returns:
            选择的文件路径列表
        """
        self.logger.info(f"开始文件选择: {title}")
        
        # 默认文件类型
        if not file_types:
            file_types = self._get_default_file_types()
        
        # 尝试不同的选择方式
        for method in self.available_methods:
            try:
                if method == 'win32':
                    return self._select_files_win32(title, file_types, multiple)
                elif method == 'manual':
                    return self._select_files_manual(title, multiple)
            except Exception as e:
                self.logger.warning(f"文件选择方式 {method} 失败: {e}")
                continue
        
        self.logger.error("所有文件选择方式都失败")
        return []
    
    def select_folder(self, title: str = "选择文件夹") -> Optional[str]:
        """
        选择文件夹对话框
        
        Args:
            title: 对话框标题
            
        Returns:
            统一格式的结果字典
        """
        self.logger.info(f"启动文件夹选择对话框: {title}")
        
        folder = None
        last_error = None
        
        # 尝试不同的文件夹选择方法
        for method in self.available_methods:
            try:
                if method == 'win32':
                    folder = self._select_folder_win32(title)
                elif method == 'manual':
                    folder = self._select_folder_manual(title)
                
                self.logger.debug(f"{method} 文件夹选择结果: {folder}")
                
                if folder:
                    # 确保返回值是字符串
                    if isinstance(folder, list):
                        folder = folder[0] if folder else None
                    
                    if folder and isinstance(folder, (str, os.PathLike)):
                        folder_path = str(folder).strip()
                        if folder_path and os.path.exists(folder_path) and os.path.isdir(folder_path):
                            self.logger.info(f"成功选择文件夹: {folder_path}")
                            return {
                                'success': True,
                                'folder': folder_path,
                                'message': f'成功选择文件夹: {folder_path}'
                            }
                
            except Exception as e:
                last_error = str(e)
                self.logger.warning(f"{method} 文件夹选择失败: {e}")
                continue
        
        # 所有方法都失败
        error_msg = f"文件夹选择失败: {last_error}" if last_error else "未选择文件夹"
        self.logger.warning(error_msg)
        return {
            'success': False,
            'folder': None,
            'message': error_msg
        }
    
    def _get_default_file_types(self) -> List[Dict[str, str]]:
        """获取默认文件类型"""
        return [
            {
                'name': '所有支持的文件',
                'extensions': [ext for exts in self.supported_extensions.values() for ext in exts]
            },
            {
                'name': '图像文件',
                'extensions': self.supported_extensions['images']
            },
            {
                'name': '视频文件',
                'extensions': self.supported_extensions['videos']
            },
            {
                'name': '音频文件',
                'extensions': self.supported_extensions['audio']
            },
            {
                'name': '文档文件',
                'extensions': self.supported_extensions['documents']
            },
            {
                'name': '压缩文件',
                'extensions': self.supported_extensions['archives']
            },
            {
                'name': '代码文件',
                'extensions': self.supported_extensions['code']
            },
            {
                'name': '所有文件',
                'extensions': ['*']
            }
        ]
    
    def _select_files_win32(self, title: str, file_types: List[Dict[str, str]], 
                           multiple: bool) -> List[str]:
        """使用Windows API选择文件"""
        self.logger.debug("使用Windows API文件选择器")
        
        pythoncom.CoInitialize()
        
        try:
            # 创建文件对话框
            dialog = shell.SHCreateItemFromParsingName(
                shell.SHGetKnownFolderPath(shellcon.FOLDERID_Desktop),
                None,
                shell.IID_IShellItem
            )
            
            # 这里需要更复杂的Win32 API调用
            # 为了简化，暂时使用subprocess调用PowerShell
            return self._select_files_powershell(title, file_types, multiple)
            
        finally:
            pythoncom.CoUninitialize()
    
    def _select_folder_win32(self, title: str) -> Optional[str]:
        """使用Windows API选择文件夹"""
        self.logger.debug("使用Windows API文件夹选择器")
        
        try:
            # 使用PowerShell的文件夹选择器
            ps_script = f"""
Add-Type -AssemblyName System.Windows.Forms
$folder = New-Object System.Windows.Forms.FolderBrowserDialog
$folder.Description = "{title}"
$folder.ShowNewFolderButton = $true
if ($folder.ShowDialog() -eq 'OK') {{
    Write-Output $folder.SelectedPath
}}
"""
            
            result = subprocess.run(
                ['powershell', '-Command', ps_script],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
                
        except Exception as e:
            self.logger.warning(f"PowerShell文件夹选择失败: {e}")
        
        return None
    
    def _select_files_powershell(self, title: str, file_types: List[Dict[str, str]], 
                                multiple: bool) -> List[str]:
        """使用PowerShell选择文件"""
        try:
            # 构建文件过滤器
            filters = []
            for ft in file_types:
                if ft['extensions'] == ['*']:
                    filters.append(f"'{ft['name']}|*.*'")
                else:
                    pattern = ';'.join([f'*{ext}' for ext in ft['extensions']])
                    filters.append(f"'{ft['name']}|{pattern}'")
            
            filter_string = '|'.join(filters)
            
            # PowerShell脚本
            ps_script = f"""
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = "{title}"
$dialog.Filter = "{filter_string}"
$dialog.Multiselect = ${str(multiple).lower()}
$dialog.CheckFileExists = $true
$dialog.CheckPathExists = $true

if ($dialog.ShowDialog() -eq 'OK') {{
    if ($dialog.Multiselect) {{
        $dialog.FileNames | ForEach-Object {{ Write-Output $_ }}
    }} else {{
        Write-Output $dialog.FileName
    }}
}}
"""
            
            result = subprocess.run(
                ['powershell', '-Command', ps_script],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            self.logger.debug(f"PowerShell文件选择结果: 返回码={result.returncode}, 输出={result.stdout}")
            
            if result.returncode == 0 and result.stdout.strip():
                # 清理和过滤文件路径
                raw_files = [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]
                files = []
                
                for file_path in raw_files:
                    if file_path and os.path.exists(file_path):
                        files.append(file_path)
                    else:
                        self.logger.warning(f"PowerShell返回的文件路径不存在: {file_path}")
                
                return files
                
        except Exception as e:
            self.logger.warning(f"PowerShell文件选择失败: {e}")
        
        return []
    
    def _select_files_manual(self, title: str, multiple: bool) -> List[str]:
        """手动输入文件路径"""
        self.logger.debug("使用手动输入方式")
        
        print(f"\n{title}")
        print("=" * 50)
        
        if multiple:
            print("请输入文件路径（多个文件用分号;分隔）:")
            print("示例: C:\\path\\to\\file1.txt;C:\\path\\to\\file2.jpg")
        else:
            print("请输入文件路径:")
            print("示例: C:\\path\\to\\file.txt")
        
        paths_input = input("文件路径: ").strip()
        
        if not paths_input:
            return []
        
        if multiple:
            paths = [p.strip() for p in paths_input.split(';') if p.strip()]
        else:
            paths = [paths_input]
        
        # 验证路径
        valid_paths = []
        for path in paths:
            if os.path.isfile(path):
                valid_paths.append(path)
            else:
                print(f"警告: 文件不存在或无法访问: {path}")
        
        return valid_paths
    
    def _select_folder_manual(self, title: str) -> Optional[str]:
        """手动输入文件夹路径"""
        self.logger.debug("使用手动输入方式")
        
        print(f"\n{title}")
        print("=" * 50)
        print("请输入文件夹路径:")
        print("示例: C:\\path\\to\\folder")
        
        path = input("文件夹路径: ").strip()
        
        if not path:
            return None
        
        if os.path.isdir(path):
            return path
        else:
            print(f"警告: 文件夹不存在或无法访问: {path}")
            return None
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """
        获取文件信息
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件信息字典
        """
        try:
            self.logger.debug(f"获取文件信息: {file_path}, 类型: {type(file_path)}")
            
            # 类型检查和转换
            if isinstance(file_path, list):
                if not file_path:
                    return {'error': '文件路径列表为空'}
                # 如果是列表，取第一个元素
                file_path = file_path[0]
                self.logger.warning(f"文件路径是列表，取第一个元素: {file_path}")
            
            if not isinstance(file_path, (str, os.PathLike)):
                error_msg = f'文件路径类型错误: {type(file_path)}, 值: {file_path}'
                self.logger.error(error_msg)
                return {'error': error_msg}
            
            # 转换为字符串并清理
            file_path = str(file_path).strip()
            if not file_path:
                return {'error': '文件路径为空'}
            
            self.logger.debug(f"处理后的文件路径: {file_path}")
            
            path = Path(file_path)
            if not path.exists():
                return {'error': '文件不存在'}
            
            stat = path.stat()
            
            # 确定文件类型
            file_type = 'unknown'
            extension = path.suffix.lower()
            
            for category, extensions in self.supported_extensions.items():
                if extension in extensions:
                    file_type = category
                    break
            
            result = {
                'name': path.name,
                'path': str(path.absolute()),
                'size': stat.st_size,
                'size_human': self._format_file_size(stat.st_size),
                'modified': stat.st_mtime,
                'extension': extension,
                'type': file_type,
                'is_file': path.is_file(),
                'is_dir': path.is_dir()
            }
            
            self.logger.debug(f"文件信息获取成功: {result['name']}")
            return result
            
        except Exception as e:
            error_msg = f"获取文件信息失败: {e}"
            self.logger.error(error_msg, exc_info=True)
            return {'error': error_msg}
    
    def _format_file_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        import math
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_names[i]}"
    
    def scan_folder(self, folder_path: str, recursive: bool = False, 
                   file_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        扫描文件夹内容
        
        Args:
            folder_path: 文件夹路径
            recursive: 是否递归扫描子文件夹
            file_types: 文件类型过滤器（扩展名列表）
            
        Returns:
            扫描结果字典
        """
        try:
            self.logger.debug(f"开始扫描文件夹: {folder_path}, 类型: {type(folder_path)}")
            
            # 确保 folder_path 是字符串
            if not isinstance(folder_path, (str, os.PathLike)):
                self.logger.error(f"文件夹路径类型错误: {type(folder_path)}, 值: {folder_path}")
                return {'error': f'文件夹路径类型错误: {type(folder_path)}'}
            
            folder = Path(str(folder_path))
            if not folder.exists() or not folder.is_dir():
                return {'error': '文件夹不存在或不是有效目录'}
            
            files = []
            folders = []
            file_count = 0
            
            # 扫描文件和文件夹
            pattern = "**/*" if recursive else "*"
            self.logger.debug(f"使用扫描模式: {pattern}")
            
            for item in folder.glob(pattern):
                try:
                    self.logger.debug(f"处理项目: {item}, 类型: {type(item)}")
                    
                    if item.is_file():
                        # 检查文件类型过滤器
                        if file_types and item.suffix.lower() not in file_types:
                            continue
                        
                        # 确保传递字符串路径给 get_file_info
                        item_path = str(item.absolute())
                        self.logger.debug(f"获取文件信息: {item_path}, 类型: {type(item_path)}")
                        
                        file_info = self.get_file_info(item_path)
                        
                        if 'error' not in file_info:
                            files.append(file_info)
                            file_count += 1
                        else:
                            self.logger.warning(f"获取文件信息失败: {file_info['error']}")
                        
                    elif item.is_dir() and item != folder:
                        folders.append({
                            'name': item.name,
                            'path': str(item.absolute()),
                            'is_dir': True
                        })
                        
                except Exception as item_error:
                    self.logger.error(f"处理文件/文件夹时出错 {item}: {item_error}", exc_info=True)
                    continue
            
            self.logger.info(f"扫描完成: 找到 {file_count} 个文件, {len(folders)} 个文件夹")
            
            return {
                'folder': str(folder.absolute()),
                'files': files,
                'folders': folders,
                'total_files': len(files),
                'total_folders': len(folders)
            }
            
        except Exception as e:
            error_msg = f"扫描文件夹失败: {e}"
            self.logger.error(error_msg, exc_info=True)
            return {'error': error_msg}


class FileDisplayManager:
    """文件显示管理器"""
    
    def __init__(self):
        self.logger = get_logger('file_display')
    
    def create_file_list_html(self, files: List[Dict[str, Any]], 
                             show_checkboxes: bool = True,
                             show_preview: bool = True) -> str:
        """
        创建文件列表的HTML
        
        Args:
            files: 文件信息列表
            show_checkboxes: 是否显示复选框
            show_preview: 是否显示预览
            
        Returns:
            HTML字符串
        """
        html_parts = ['<div class="file-list">']
        
        for i, file_info in enumerate(files):
            if 'error' in file_info:
                continue
                
            # 文件项容器
            html_parts.append(f'<div class="file-item" data-index="{i}" data-path="{file_info["path"]}">')
            
            # 复选框
            if show_checkboxes:
                html_parts.append(f'<input type="checkbox" class="file-checkbox" id="file_{i}" checked>')
            
            # 文件图标
            file_icon = self._get_file_icon(file_info.get('type', 'unknown'))
            html_parts.append(f'<div class="file-icon">{file_icon}</div>')
            
            # 文件信息
            html_parts.append('<div class="file-info">')
            html_parts.append(f'<div class="file-name" title="{file_info["name"]}">{file_info["name"]}</div>')
            html_parts.append(f'<div class="file-details">')
            html_parts.append(f'  <span class="file-size">{file_info.get("size_human", "未知大小")}</span>')
            html_parts.append(f'  <span class="file-type">{file_info.get("type", "unknown").upper()}</span>')
            html_parts.append(f'</div>')
            html_parts.append('</div>')
            
            # 操作按钮
            html_parts.append('<div class="file-actions">')
            html_parts.append(f'<button class="btn-preview" onclick="previewFile(\'{file_info["path"]}\')">预览</button>')
            html_parts.append(f'<button class="btn-rename" onclick="renameFile({i})">重命名</button>')
            html_parts.append(f'<button class="btn-remove" onclick="removeFile({i})">移除</button>')
            html_parts.append('</div>')
            
            html_parts.append('</div>')
        
        html_parts.append('</div>')
        
        return '\n'.join(html_parts)
    
    def _get_file_icon(self, file_type: str) -> str:
        """获取文件类型图标"""
        icons = {
            'images': '🖼️',
            'videos': '🎥',
            'audio': '🎵',
            'documents': '📄',
            'archives': '📦',
            'code': '💻',
            'data': '📊',
            'unknown': '📁'
        }
        return icons.get(file_type, icons['unknown'])
    
    def create_rename_dialog_html(self, file_info: Dict[str, Any], 
                                 suggestions: List[str] = None) -> str:
        """
        创建重命名对话框的HTML
        
        Args:
            file_info: 文件信息
            suggestions: 名称建议列表
            
        Returns:
            HTML字符串
        """
        current_name = file_info.get('name', '')
        name_without_ext = Path(current_name).stem
        extension = Path(current_name).suffix
        
        html = f'''
        <div class="rename-dialog">
            <div class="dialog-header">
                <h3>重命名文件</h3>
                <div class="file-info-display">
                    <span class="file-icon">{self._get_file_icon(file_info.get('type', 'unknown'))}</span>
                    <span class="current-name">{current_name}</span>
                </div>
            </div>
            
            <div class="dialog-content">
                <div class="input-group">
                    <label for="new-filename">新文件名:</label>
                    <input type="text" id="new-filename" value="{name_without_ext}" placeholder="输入新的文件名">
                    <span class="file-extension">{extension}</span>
                </div>
                
                {self._create_suggestions_html(suggestions) if suggestions else ""}
            </div>
            
            <div class="dialog-actions">
                <button class="btn-cancel" onclick="closeRenameDialog()">取消</button>
                <button class="btn-confirm" onclick="confirmRename()">确认</button>
                <button class="btn-ai-suggest" onclick="generateAIName()">AI建议</button>
            </div>
        </div>
        '''
        
        return html
    
    def _create_suggestions_html(self, suggestions: List[str]) -> str:
        """创建名称建议的HTML"""
        if not suggestions:
            return ""
        
        html_parts = ['<div class="name-suggestions">']
        html_parts.append('<label>建议的名称:</label>')
        html_parts.append('<div class="suggestions-list">')
        
        for i, suggestion in enumerate(suggestions):
            html_parts.append(f'''
                <div class="suggestion-item" onclick="selectSuggestion('{suggestion}')">
                    <span class="suggestion-text">{suggestion}</span>
                </div>
            ''')
        
        html_parts.append('</div>')
        html_parts.append('</div>')
        
        return '\n'.join(html_parts)


# 全局实例
_file_selector = None

def get_file_selector() -> FileSelector:
    """获取文件选择器单例"""
    global _file_selector
    if _file_selector is None:
        _file_selector = FileSelector()
    return _file_selector