#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内容提取器模块

提供从各种文件格式中提取内容和元数据的功能，支持：
- 图片文件：EXIF数据、基本信息
- 视频文件：基本信息、元数据
- 文档文件：文本内容、属性信息
- 压缩文件：文件列表、结构信息
- 音频文件：基本信息、元数据
"""

import os
import mimetypes
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime
import json

# 基础库
import tempfile
import zipfile
import rarfile
import tarfile
import py7zr

# 图片处理
try:
    from PIL import Image
    from PIL.ExifTags import TAGS
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# 文档处理
try:
    import docx
    from openpyxl import load_workbook
    import pypdf
    OFFICE_AVAILABLE = True
except ImportError:
    OFFICE_AVAILABLE = False

# 视频/音频处理
try:
    import ffmpeg
    FFMPEG_AVAILABLE = True
except ImportError:
    FFMPEG_AVAILABLE = False

# 本地模块
from .logger import get_logger
from .config_manager import ConfigManager


class ContentExtractor:
    """文件内容提取器"""
    
    def __init__(self, config_manager: ConfigManager = None):
        """
        初始化内容提取器
        
        Args:
            config_manager: 配置管理器实例
        """
        self.config_manager = config_manager or ConfigManager()
        self.logger = get_logger('content_extractor')
        
        # 支持的文件类型
        self.supported_types = {
            'image': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.svg'],
            'video': ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'],
            'audio': ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a'],
            'document': ['.txt', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.rtf'],
            'archive': ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz'],
            'code': ['.py', '.js', '.html', '.css', '.java', '.cpp', '.c', '.h', '.xml', '.json']
        }
        
        # 初始化mimetypes
        mimetypes.init()
        
        self.logger.info("内容提取器初始化完成")
    
    def extract_content(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        提取文件内容和元数据
        
        Args:
            file_path: 文件路径
            
        Returns:
            包含文件内容和元数据的字典
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        self.logger.info(f"开始提取文件内容: {file_path}")
        
        try:
            # 基础信息
            basic_info = self._extract_basic_info(file_path)
            
            # 根据文件类型提取特定内容
            file_type = self._get_file_type(file_path)
            content_info = {}
            
            if file_type == 'image':
                content_info = self._extract_image_content(file_path)
            elif file_type == 'video':
                content_info = self._extract_video_content(file_path)
            elif file_type == 'audio':
                content_info = self._extract_audio_content(file_path)
            elif file_type == 'document':
                content_info = self._extract_document_content(file_path)
            elif file_type == 'archive':
                content_info = self._extract_archive_content(file_path)
            elif file_type == 'code':
                content_info = self._extract_code_content(file_path)
            else:
                content_info = self._extract_text_content(file_path)
            
            # 合并信息
            result = {
                **basic_info,
                **content_info,
                'file_type': file_type,
                'extraction_time': datetime.now().isoformat()
            }
            
            self.logger.info(f"文件内容提取完成: {file_path}")
            return result
            
        except Exception as e:
            self.logger.error(f"提取文件内容失败 {file_path}: {e}")
            # 返回基础信息，即使内容提取失败
            try:
                basic_info = self._extract_basic_info(file_path)
                basic_info['extraction_error'] = str(e)
                basic_info['file_type'] = 'unknown'
                return basic_info
            except Exception as basic_error:
                self.logger.error(f"提取基础信息也失败 {file_path}: {basic_error}")
                raise
    
    def _extract_basic_info(self, file_path: Path) -> Dict[str, Any]:
        """提取文件基础信息"""
        stat = file_path.stat()
        
        # 计算文件哈希值（可选，用于去重）
        file_hash = self._calculate_file_hash(file_path)
        
        return {
            'filename': file_path.name,
            'extension': file_path.suffix.lower(),
            'size_bytes': stat.st_size,
            'size_human': self._format_file_size(stat.st_size),
            'created_time': datetime.fromtimestamp(stat.st_ctime).isoformat(),
            'modified_time': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'accessed_time': datetime.fromtimestamp(stat.st_atime).isoformat(),
            'file_hash': file_hash,
            'mime_type': mimetypes.guess_type(str(file_path))[0] or 'unknown'
        }
    
    def _get_file_type(self, file_path: Path) -> str:
        """根据扩展名确定文件类型"""
        extension = file_path.suffix.lower()
        
        for file_type, extensions in self.supported_types.items():
            if extension in extensions:
                return file_type
        
        return 'unknown'
    
    def _extract_image_content(self, file_path: Path) -> Dict[str, Any]:
        """提取图片内容和EXIF信息"""
        if not PIL_AVAILABLE:
            return {'error': 'PIL库未安装，无法处理图片文件'}
        
        try:
            with Image.open(file_path) as img:
                info = {
                    'width': img.width,
                    'height': img.height,
                    'format': img.format,
                    'mode': img.mode,
                    'resolution': f"{img.width}x{img.height}",
                    'has_transparency': img.mode in ('RGBA', 'LA') or 'transparency' in img.info
                }
                
                # 提取EXIF数据
                exif_data = {}
                if hasattr(img, '_getexif'):
                    exif = img._getexif()
                    if exif:
                        for tag_id, value in exif.items():
                            tag = TAGS.get(tag_id, tag_id)
                            exif_data[tag] = str(value)
                
                if exif_data:
                    info['exif'] = exif_data
                
                return info
                
        except Exception as e:
            return {'error': f'图片处理失败: {e}'}
    
    def _extract_video_content(self, file_path: Path) -> Dict[str, Any]:
        """提取视频文件信息"""
        if not FFMPEG_AVAILABLE:
            return {'error': 'ffmpeg-python库未安装，无法处理视频文件'}
        
        try:
            probe = ffmpeg.probe(str(file_path))
            
            # 视频流信息
            video_streams = [s for s in probe['streams'] if s['codec_type'] == 'video']
            audio_streams = [s for s in probe['streams'] if s['codec_type'] == 'audio']
            
            info = {
                'duration': float(probe['format'].get('duration', 0)),
                'format_name': probe['format']['format_name'],
                'bit_rate': int(probe['format'].get('bit_rate', 0)),
                'video_streams_count': len(video_streams),
                'audio_streams_count': len(audio_streams)
            }
            
            # 主视频流信息
            if video_streams:
                video = video_streams[0]
                info.update({
                    'width': int(video.get('width', 0)),
                    'height': int(video.get('height', 0)),
                    'video_codec': video.get('codec_name', 'unknown'),
                    'video_bitrate': int(video.get('bit_rate', 0)),
                    'frame_rate': eval(video.get('r_frame_rate', '0/1')) if '/' in str(video.get('r_frame_rate', '')) else 0
                })
            
            # 主音频流信息
            if audio_streams:
                audio = audio_streams[0]
                info.update({
                    'audio_codec': audio.get('codec_name', 'unknown'),
                    'audio_bitrate': int(audio.get('bit_rate', 0)),
                    'sample_rate': int(audio.get('sample_rate', 0)),
                    'channels': int(audio.get('channels', 0))
                })
            
            return info
            
        except Exception as e:
            return {'error': f'视频处理失败: {e}'}
    
    def _extract_audio_content(self, file_path: Path) -> Dict[str, Any]:
        """提取音频文件信息"""
        if not FFMPEG_AVAILABLE:
            return {'error': 'ffmpeg-python库未安装，无法处理音频文件'}
        
        try:
            probe = ffmpeg.probe(str(file_path))
            
            # 音频流信息
            audio_streams = [s for s in probe['streams'] if s['codec_type'] == 'audio']
            
            info = {
                'duration': float(probe['format'].get('duration', 0)),
                'format_name': probe['format']['format_name'],
                'bit_rate': int(probe['format'].get('bit_rate', 0))
            }
            
            if audio_streams:
                audio = audio_streams[0]
                info.update({
                    'codec': audio.get('codec_name', 'unknown'),
                    'sample_rate': int(audio.get('sample_rate', 0)),
                    'channels': int(audio.get('channels', 0)),
                    'audio_bitrate': int(audio.get('bit_rate', 0))
                })
            
            # 提取标签信息
            tags = probe['format'].get('tags', {})
            if tags:
                info['metadata'] = {k.lower(): v for k, v in tags.items()}
            
            return info
            
        except Exception as e:
            return {'error': f'音频处理失败: {e}'}
    
    def _extract_document_content(self, file_path: Path) -> Dict[str, Any]:
        """提取文档内容"""
        extension = file_path.suffix.lower()
        
        if extension == '.txt':
            return self._extract_text_content(file_path)
        elif extension == '.pdf':
            return self._extract_pdf_content(file_path)
        elif extension in ['.doc', '.docx']:
            return self._extract_word_content(file_path)
        elif extension in ['.xls', '.xlsx']:
            return self._extract_excel_content(file_path)
        else:
            return self._extract_text_content(file_path)
    
    def _extract_text_content(self, file_path: Path) -> Dict[str, Any]:
        """提取纯文本文件内容"""
        try:
            # 尝试多种编码
            encodings = ['utf-8', 'gbk', 'cp1252', 'iso-8859-1']
            content = None
            encoding_used = None
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read()
                    encoding_used = encoding
                    break
                except UnicodeDecodeError:
                    continue
            
            if content is None:
                return {'error': '无法读取文件内容，编码不支持'}
            
            lines = content.splitlines()
            
            return {
                'content_preview': content[:1000] if len(content) > 1000 else content,
                'line_count': len(lines),
                'character_count': len(content),
                'word_count': len(content.split()),
                'encoding': encoding_used,
                'has_full_content': True
            }
            
        except Exception as e:
            return {'error': f'文本文件处理失败: {e}'}
    
    def _extract_pdf_content(self, file_path: Path) -> Dict[str, Any]:
        """提取PDF文件内容"""
        if not OFFICE_AVAILABLE:
            return {'error': 'pypdf库未安装，无法处理PDF文件'}
        
        try:
            with open(file_path, 'rb') as f:
                reader = pypdf.PdfReader(f)
                
                info = {
                    'page_count': len(reader.pages),
                    'is_encrypted': reader.is_encrypted
                }
                
                # 提取文档信息
                if reader.metadata:
                    metadata = {}
                    for key, value in reader.metadata.items():
                        clean_key = key.replace('/', '').lower()
                        metadata[clean_key] = str(value) if value else ''
                    info['metadata'] = metadata
                
                # 提取前几页文本内容作为预览
                text_content = []
                max_pages = min(3, len(reader.pages))
                
                for i in range(max_pages):
                    try:
                        page_text = reader.pages[i].extract_text()
                        if page_text.strip():
                            text_content.append(page_text.strip())
                    except Exception:
                        continue
                
                if text_content:
                    combined_text = '\n'.join(text_content)
                    info['content_preview'] = combined_text[:1000] if len(combined_text) > 1000 else combined_text
                    info['character_count'] = len(combined_text)
                    info['word_count'] = len(combined_text.split())
                
                return info
                
        except Exception as e:
            return {'error': f'PDF处理失败: {e}'}
    
    def _extract_word_content(self, file_path: Path) -> Dict[str, Any]:
        """提取Word文档内容"""
        if not OFFICE_AVAILABLE:
            return {'error': 'python-docx库未安装，无法处理Word文件'}
        
        try:
            doc = docx.Document(file_path)
            
            # 提取文本内容
            full_text = []
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    full_text.append(paragraph.text.strip())
            
            combined_text = '\n'.join(full_text)
            
            info = {
                'paragraph_count': len([p for p in doc.paragraphs if p.text.strip()]),
                'character_count': len(combined_text),
                'word_count': len(combined_text.split()),
                'content_preview': combined_text[:1000] if len(combined_text) > 1000 else combined_text
            }
            
            # 提取文档属性
            core_props = doc.core_properties
            if core_props:
                metadata = {}
                for prop in ['author', 'category', 'comments', 'created', 'keywords', 
                           'language', 'last_modified_by', 'modified', 'subject', 'title', 'version']:
                    value = getattr(core_props, prop, None)
                    if value:
                        if isinstance(value, datetime):
                            metadata[prop] = value.isoformat()
                        else:
                            metadata[prop] = str(value)
                
                if metadata:
                    info['metadata'] = metadata
            
            return info
            
        except Exception as e:
            return {'error': f'Word文档处理失败: {e}'}
    
    def _extract_excel_content(self, file_path: Path) -> Dict[str, Any]:
        """提取Excel文件内容"""
        if not OFFICE_AVAILABLE:
            return {'error': 'openpyxl库未安装，无法处理Excel文件'}
        
        try:
            workbook = load_workbook(file_path, read_only=True, data_only=True)
            
            info = {
                'sheet_count': len(workbook.sheetnames),
                'sheet_names': workbook.sheetnames
            }
            
            # 提取第一个工作表的部分内容作为预览
            if workbook.sheetnames:
                ws = workbook[workbook.sheetnames[0]]
                
                # 计算实际使用的行列数
                max_row = 0
                max_col = 0
                cell_count = 0
                
                preview_data = []
                max_preview_rows = 10
                
                for row_idx, row in enumerate(ws.iter_rows(values_only=True), 1):
                    if row_idx <= max_preview_rows:
                        row_data = []
                        for cell in row:
                            if cell is not None:
                                row_data.append(str(cell))
                                cell_count += 1
                            else:
                                row_data.append('')
                        
                        # 只保存非空行
                        if any(cell for cell in row_data):
                            preview_data.append(row_data)
                            max_row = row_idx
                            max_col = max(max_col, len([c for c in row_data if c]))
                    else:
                        # 继续计算但不保存数据
                        for cell in row:
                            if cell is not None:
                                cell_count += 1
                                max_row = row_idx
                
                info.update({
                    'used_rows': max_row,
                    'used_columns': max_col,
                    'cell_count': cell_count,
                    'preview_data': preview_data[:5]  # 只保存前5行作为预览
                })
            
            return info
            
        except Exception as e:
            return {'error': f'Excel文件处理失败: {e}'}
    
    def _extract_archive_content(self, file_path: Path) -> Dict[str, Any]:
        """提取压缩文件内容"""
        extension = file_path.suffix.lower()
        
        try:
            if extension == '.zip':
                return self._extract_zip_content(file_path)
            elif extension == '.rar':
                return self._extract_rar_content(file_path)
            elif extension == '.7z':
                return self._extract_7z_content(file_path)
            elif extension in ['.tar', '.gz', '.bz2', '.xz']:
                return self._extract_tar_content(file_path)
            else:
                return {'error': f'不支持的压缩格式: {extension}'}
                
        except Exception as e:
            return {'error': f'压缩文件处理失败: {e}'}
    
    def _extract_zip_content(self, file_path: Path) -> Dict[str, Any]:
        """提取ZIP文件内容"""
        with zipfile.ZipFile(file_path, 'r') as zip_file:
            file_list = zip_file.namelist()
            
            info = {
                'file_count': len(file_list),
                'file_list': file_list[:50],  # 最多显示50个文件
                'is_truncated': len(file_list) > 50
            }
            
            # 计算压缩比
            total_uncompressed = sum(zip_file.getinfo(name).file_size for name in file_list)
            total_compressed = sum(zip_file.getinfo(name).compress_size for name in file_list)
            
            if total_uncompressed > 0:
                info['compression_ratio'] = round((1 - total_compressed / total_uncompressed) * 100, 2)
                info['uncompressed_size'] = total_uncompressed
                info['compressed_size'] = total_compressed
            
            return info
    
    def _extract_rar_content(self, file_path: Path) -> Dict[str, Any]:
        """提取RAR文件内容"""
        try:
            with rarfile.RarFile(file_path, 'r') as rar_file:
                file_list = rar_file.namelist()
                
                return {
                    'file_count': len(file_list),
                    'file_list': file_list[:50],
                    'is_truncated': len(file_list) > 50
                }
        except rarfile.RarCannotExec:
            return {'error': 'RAR解压工具未安装或配置'}
    
    def _extract_7z_content(self, file_path: Path) -> Dict[str, Any]:
        """提取7Z文件内容"""
        with py7zr.SevenZipFile(file_path, 'r') as archive:
            file_list = archive.getnames()
            
            return {
                'file_count': len(file_list),
                'file_list': file_list[:50],
                'is_truncated': len(file_list) > 50
            }
    
    def _extract_tar_content(self, file_path: Path) -> Dict[str, Any]:
        """提取TAR文件内容"""
        mode = 'r'
        if file_path.suffix.lower() in ['.gz', '.tgz']:
            mode = 'r:gz'
        elif file_path.suffix.lower() in ['.bz2', '.tbz2']:
            mode = 'r:bz2'
        elif file_path.suffix.lower() in ['.xz', '.txz']:
            mode = 'r:xz'
        
        with tarfile.open(file_path, mode) as tar_file:
            file_list = tar_file.getnames()
            
            return {
                'file_count': len(file_list),
                'file_list': file_list[:50],
                'is_truncated': len(file_list) > 50
            }
    
    def _extract_code_content(self, file_path: Path) -> Dict[str, Any]:
        """提取代码文件内容"""
        try:
            # 代码文件通常是文本文件
            text_info = self._extract_text_content(file_path)
            
            if 'error' in text_info:
                return text_info
            
            # 添加代码特定的分析
            content = text_info.get('content_preview', '')
            
            # 简单的代码分析
            code_info = {
                'language': self._detect_programming_language(file_path),
                'has_imports': 'import ' in content or '#include' in content or 'require(' in content,
                'has_functions': 'def ' in content or 'function ' in content or 'void ' in content,
                'has_classes': 'class ' in content or 'interface ' in content,
                'has_comments': '//' in content or '/*' in content or '#' in content
            }
            
            # 合并信息
            return {**text_info, **code_info}
            
        except Exception as e:
            return {'error': f'代码文件处理失败: {e}'}
    
    def _detect_programming_language(self, file_path: Path) -> str:
        """根据文件扩展名检测编程语言"""
        extension = file_path.suffix.lower()
        
        language_map = {
            '.py': 'Python',
            '.js': 'JavaScript', 
            '.ts': 'TypeScript',
            '.html': 'HTML',
            '.css': 'CSS',
            '.java': 'Java',
            '.cpp': 'C++',
            '.c': 'C',
            '.h': 'C/C++ Header',
            '.xml': 'XML',
            '.json': 'JSON',
            '.yml': 'YAML',
            '.yaml': 'YAML',
            '.sql': 'SQL',
            '.php': 'PHP',
            '.rb': 'Ruby',
            '.go': 'Go',
            '.rs': 'Rust',
            '.swift': 'Swift',
            '.kt': 'Kotlin',
            '.cs': 'C#',
            '.vb': 'VB.NET'
        }
        
        return language_map.get(extension, 'Unknown')
    
    def _calculate_file_hash(self, file_path: Path, algorithm: str = 'md5') -> str:
        """计算文件哈希值"""
        try:
            hash_func = getattr(hashlib, algorithm)()
            
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_func.update(chunk)
            
            return hash_func.hexdigest()
            
        except Exception as e:
            self.logger.warning(f"计算文件哈希失败 {file_path}: {e}")
            return ''
    
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
    
    def get_supported_extensions(self) -> List[str]:
        """获取所有支持的文件扩展名"""
        extensions = []
        for file_type, exts in self.supported_types.items():
            extensions.extend(exts)
        return sorted(list(set(extensions)))
    
    def is_supported_file(self, file_path: Union[str, Path]) -> bool:
        """检查文件是否被支持"""
        file_path = Path(file_path)
        extension = file_path.suffix.lower()
        
        all_extensions = self.get_supported_extensions()
        return extension in all_extensions
    
    def batch_extract(self, file_paths: List[Union[str, Path]], 
                     callback=None) -> Dict[str, Dict[str, Any]]:
        """
        批量提取文件内容
        
        Args:
            file_paths: 文件路径列表
            callback: 进度回调函数，接收 (current, total, file_path) 参数
            
        Returns:
            文件路径到提取结果的映射
        """
        results = {}
        total = len(file_paths)
        
        self.logger.info(f"开始批量提取内容，共 {total} 个文件")
        
        for i, file_path in enumerate(file_paths):
            try:
                if callback:
                    callback(i + 1, total, file_path)
                
                results[str(file_path)] = self.extract_content(file_path)
                
            except Exception as e:
                self.logger.error(f"批量提取失败 {file_path}: {e}")
                results[str(file_path)] = {'error': str(e)}
        
        self.logger.info(f"批量提取完成，成功: {len([r for r in results.values() if 'error' not in r])}, "
                        f"失败: {len([r for r in results.values() if 'error' in r])}")
        
        return results