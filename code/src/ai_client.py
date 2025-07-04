#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI客户端模块

提供统一的AI API调用接口，支持：
- 图像分析和理解
- 文件内容分析
- 智能决策和分类
- 多模型管理
- 错误处理和重试机制
"""

import base64
import time
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Generator, Callable
from datetime import datetime
from enum import Enum
import asyncio

# OpenAI库
try:
    from openai import OpenAI
    from openai.types.chat import ChatCompletion, ChatCompletionChunk
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# 本地模块
from .logger import get_logger
from .config_manager import ConfigManager


class ModelType(Enum):
    """AI模型类型枚举"""
    IMAGE_ANALYSIS = "image_analysis"
    FILE_ANALYSIS = "file_analysis"
    DECISION = "decision"
    VIDEO_ANALYSIS = "video_analysis"


class AITaskType(Enum):
    """AI任务类型枚举"""
    CLASSIFY_FILE = "classify_file"
    ANALYZE_IMAGE = "analyze_image"
    EXTRACT_TEXT = "extract_text"
    GENERATE_SUMMARY = "generate_summary"
    MAKE_DECISION = "make_decision"
    GENERATE_NAME = "generate_name"
    ANALYZE_CONTENT = "analyze_content"


class AIResponse:
    """AI响应结果"""
    
    def __init__(self, content: str, model: str, usage: Dict[str, Any] = None, 
                 metadata: Dict[str, Any] = None):
        self.content = content
        self.model = model
        self.usage = usage or {}
        self.metadata = metadata or {}
        self.timestamp = datetime.now()
        self.success = True
        self.error_message = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'content': self.content,
            'model': self.model,
            'usage': self.usage,
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat(),
            'success': self.success,
            'error_message': self.error_message
        }


class AIClient:
    """AI客户端类"""
    
    def __init__(self, config_manager: ConfigManager = None):
        """
        初始化AI客户端
        
        Args:
            config_manager: 配置管理器实例
        """
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI库未安装，请执行: pip install openai")
        
        self.config_manager = config_manager or ConfigManager()
        self.logger = get_logger('ai_client')
        
        # 加载配置
        self._load_config()

        # 先构建模型映射（_init_openai_client 可能依赖）
        self.model_map = {
            ModelType.IMAGE_ANALYSIS: self.config_manager.get_config('Settings', 'image_analysis_model'),
            ModelType.FILE_ANALYSIS: self.config_manager.get_config('Settings', 'file_analysis_model'),
            ModelType.DECISION: self.config_manager.get_config('Settings', 'decision_model'),
            ModelType.VIDEO_ANALYSIS: self.config_manager.get_config('Settings', 'video_analysis_model')
        }
        
        # 请求统计
        self.request_count = 0
        self.error_count = 0
        self.total_tokens = 0
        
        self.logger.info("AI客户端初始化完成")
        
        # 初始化OpenAI客户端
        self._init_openai_client()
    
    def _load_config(self):
        """加载配置"""
        # 验证API配置
        is_valid, error_msg = self.config_manager.validate_api_config()
        if not is_valid:
            raise ValueError(f"API配置无效: {error_msg}")
        
        # 获取API配置
        api_config = self.config_manager.get_api_config()
        self.api_key = api_config['api_key']
        self.api_url = api_config['api_url']
        self.api_type = api_config['api_type']
        
        # 语言配置
        self.language = self.config_manager.get_config('Settings', 'language', 'CN')
        
        self.logger.info(f"已加载API配置: {self.api_url}")
    
    def _init_openai_client(self):
        """初始化OpenAI客户端"""
        try:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.api_url
            )
            
            # 测试连接
            self._test_connection()
            
        except Exception as e:
            self.logger.error(f"初始化OpenAI客户端失败: {e}")
            raise
    
    def _test_connection(self):
        """测试API连接"""
        try:
            # 使用决策模型进行测试
            test_model = self.model_map.get(ModelType.DECISION, "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B")
            
            response = self.client.chat.completions.create(
                model=test_model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1
            )
            
            self.logger.info("API连接测试成功")
            
        except Exception as e:
            self.logger.warning(f"API连接测试失败: {e}")
            # 不抛出异常，允许客户端继续初始化
    
    def _encode_image(self, image_path: Union[str, Path]) -> str:
        """
        将图片编码为base64字符串
        
        Args:
            image_path: 图片文件路径
            
        Returns:
            base64编码的图片字符串
        """
        try:
            with open(image_path, 'rb') as image_file:
                image_data = image_file.read()
                base64_string = base64.b64encode(image_data).decode('utf-8')
                return base64_string
        except Exception as e:
            self.logger.error(f"图片编码失败 {image_path}: {e}")
            raise
    
    def _get_model_for_task(self, task_type: AITaskType) -> str:
        """根据任务类型获取对应的模型"""
        task_model_map = {
            AITaskType.ANALYZE_IMAGE: ModelType.IMAGE_ANALYSIS,
            AITaskType.CLASSIFY_FILE: ModelType.FILE_ANALYSIS,
            AITaskType.EXTRACT_TEXT: ModelType.FILE_ANALYSIS,
            AITaskType.GENERATE_SUMMARY: ModelType.FILE_ANALYSIS,
            AITaskType.MAKE_DECISION: ModelType.DECISION,
            AITaskType.GENERATE_NAME: ModelType.FILE_ANALYSIS,
            AITaskType.ANALYZE_CONTENT: ModelType.FILE_ANALYSIS
        }
        
        model_type = task_model_map.get(task_type, ModelType.DECISION)
        return self.model_map[model_type]
    
    def _call_api(self, messages: List[Dict[str, Any]], model: str = None, 
                  max_tokens: int = 4000, temperature: float = 0.7,
                  stream: bool = False, **kwargs) -> Union[AIResponse, Generator[str, None, None]]:
        """
        调用AI API
        
        Args:
            messages: 消息列表
            model: 模型名称
            max_tokens: 最大token数
            temperature: 温度参数
            stream: 是否流式响应
            **kwargs: 其他参数
            
        Returns:
            AI响应结果或流式生成器
        """
        if not model:
            model = self.model_map[ModelType.DECISION]
        
        try:
            self.request_count += 1
            start_time = time.time()
            
            # 记录API调用
            self.logger.debug(f"调用API: {model}, messages: {len(messages)}")
            
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=stream,
                **kwargs
            )
            
            duration = time.time() - start_time
            
            if stream:
                return self._handle_stream_response(response, model, duration)
            else:
                return self._handle_response(response, model, duration)
                
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"API调用失败: {e}")
            
            # 创建错误响应
            error_response = AIResponse("", model or "unknown")
            error_response.success = False
            error_response.error_message = str(e)
            return error_response
    
    def _handle_response(self, response: ChatCompletion, model: str, duration: float) -> AIResponse:
        """处理API响应"""
        try:
            content = response.choices[0].message.content
            usage = response.usage.model_dump() if response.usage else {}
            
            # 更新统计
            if 'total_tokens' in usage:
                self.total_tokens += usage['total_tokens']
            
            # 记录性能
            self.logger.debug(f"API调用完成: {duration:.2f}s, tokens: {usage.get('total_tokens', 0)}")
            
            # 创建响应对象
            ai_response = AIResponse(
                content=content,
                model=model,
                usage=usage,
                metadata={'duration': duration}
            )
            
            return ai_response
            
        except Exception as e:
            self.logger.error(f"处理API响应失败: {e}")
            error_response = AIResponse("", model)
            error_response.success = False
            error_response.error_message = str(e)
            return error_response
    
    def _handle_stream_response(self, response, model: str, start_time: float) -> Generator[str, None, None]:
        """处理流式API响应"""
        try:
            for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
            duration = time.time() - start_time
            self.logger.debug(f"流式API调用完成: {duration:.2f}s")
            
        except Exception as e:
            self.logger.error(f"处理流式响应失败: {e}")
            yield f"[错误]: {str(e)}"
    
    def analyze_image(self, image_path: Union[str, Path], 
                     prompt: str = None, task_type: str = "general") -> AIResponse:
        """
        分析图片内容
        
        Args:
            image_path: 图片文件路径
            prompt: 自定义提示词
            task_type: 任务类型 ('general', 'classify', 'extract', 'describe')
            
        Returns:
            AI分析结果
        """
        try:
            # 编码图片
            base64_image = self._encode_image(image_path)
            
            # 构建提示词
            if not prompt:
                prompt = self._build_image_analysis_prompt(task_type)
            
            # 构建消息
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ]
            
            # 调用API
            model = self.model_map[ModelType.IMAGE_ANALYSIS]
            response = self._call_api(messages, model, max_tokens=2000)
            
            self.logger.info(f"图片分析完成: {Path(image_path).name}")
            return response
            
        except Exception as e:
            self.logger.error(f"图片分析失败 {image_path}: {e}")
            error_response = AIResponse("", self.model_map[ModelType.IMAGE_ANALYSIS])
            error_response.success = False
            error_response.error_message = str(e)
            return error_response
    
    def analyze_file_content(self, file_content: str, file_info: Dict[str, Any],
                           task_type: AITaskType = AITaskType.CLASSIFY_FILE) -> AIResponse:
        """
        分析文件内容
        
        Args:
            file_content: 文件内容
            file_info: 文件信息字典
            task_type: 任务类型
            
        Returns:
            AI分析结果
        """
        try:
            # 构建提示词
            prompt = self._build_file_analysis_prompt(task_type, file_info)
            
            # 限制内容长度
            max_content_length = 8000
            if len(file_content) > max_content_length:
                file_content = file_content[:max_content_length] + "\n[内容已截断...]"
            
            # 构建消息
            messages = [
                {
                    "role": "system",
                    "content": prompt
                },
                {
                    "role": "user",
                    "content": f"文件信息：\n{json.dumps(file_info, ensure_ascii=False, indent=2)}\n\n文件内容：\n{file_content}"
                }
            ]
            
            # 调用API
            model = self._get_model_for_task(task_type)
            response = self._call_api(messages, model, max_tokens=2000)
            
            self.logger.info(f"文件内容分析完成: {file_info.get('filename', 'unknown')}")
            return response
            
        except Exception as e:
            self.logger.error(f"文件内容分析失败: {e}")
            error_response = AIResponse("", self._get_model_for_task(task_type))
            error_response.success = False
            error_response.error_message = str(e)
            return error_response
    
    def make_classification_decision(self, file_analyses: List[Dict[str, Any]], 
                                   classification_rules: Dict[str, Any] = None) -> AIResponse:
        """
        基于文件分析结果做出分类决策
        
        Args:
            file_analyses: 文件分析结果列表
            classification_rules: 分类规则
            
        Returns:
            分类决策结果
        """
        try:
            # 构建决策提示词
            prompt = self._build_decision_prompt(classification_rules)
            
            # 准备分析数据
            analysis_summary = self._prepare_analysis_summary(file_analyses)
            
            # 构建消息
            messages = [
                {
                    "role": "system",
                    "content": prompt
                },
                {
                    "role": "user",
                    "content": f"请基于以下文件分析结果进行分类决策：\n\n{analysis_summary}"
                }
            ]
            
            # 调用决策模型
            model = self.model_map[ModelType.DECISION]
            response = self._call_api(messages, model, max_tokens=3000, temperature=0.3)
            
            self.logger.info(f"分类决策完成，处理文件数: {len(file_analyses)}")
            return response
            
        except Exception as e:
            self.logger.error(f"分类决策失败: {e}")
            error_response = AIResponse("", self.model_map[ModelType.DECISION])
            error_response.success = False
            error_response.error_message = str(e)
            return error_response
    
    def generate_filename(self, file_content: str, file_info: Dict[str, Any]) -> AIResponse:
        """
        基于文件内容生成描述性文件名
        
        Args:
            file_content: 文件内容
            file_info: 文件信息
            
        Returns:
            生成的文件名建议
        """
        try:
            # 构建文件名生成提示词
            prompt = self._build_filename_generation_prompt()
            
            # 限制内容长度
            max_content_length = 2000
            if len(file_content) > max_content_length:
                file_content = file_content[:max_content_length] + "\n[内容已截断...]"
            
            # 构建消息
            messages = [
                {
                    "role": "system",
                    "content": prompt
                },
                {
                    "role": "user",
                    "content": f"原文件名: {file_info.get('filename', 'unknown')}\n文件类型: {file_info.get('file_type', 'unknown')}\n\n文件内容:\n{file_content}"
                }
            ]
            
            # 调用API
            model = self.model_map[ModelType.FILE_ANALYSIS]
            response = self._call_api(messages, model, max_tokens=200, temperature=0.5)
            
            self.logger.info(f"文件名生成完成: {file_info.get('filename', 'unknown')}")
            return response
            
        except Exception as e:
            self.logger.error(f"文件名生成失败: {e}")
            error_response = AIResponse("", self.model_map[ModelType.FILE_ANALYSIS])
            error_response.success = False
            error_response.error_message = str(e)
            return error_response
    
    def _build_image_analysis_prompt(self, task_type: str) -> str:
        """构建图片分析提示词"""
        base_prompt = "请分析这张图片的内容。"
        
        if self.language == "EN":
            base_prompt = "Please analyze the content of this image."
        
        task_prompts = {
            "general": {
                "CN": "请详细描述图片中的内容，包括主要对象、场景、颜色、构图等元素。",
                "EN": "Please describe the content of the image in detail, including main objects, scenes, colors, composition, etc."
            },
            "classify": {
                "CN": "请分析这张图片的类型和主题，并提供适合的分类标签。请以JSON格式返回结果，包含category（主分类）、subcategory（子分类）、tags（标签列表）、confidence（置信度）。",
                "EN": "Please analyze the type and theme of this image and provide appropriate classification labels. Return the result in JSON format, including category, subcategory, tags, and confidence."
            },
            "extract": {
                "CN": "请提取图片中的所有文字内容，如果有的话。同时识别图片中的主要元素和信息。",
                "EN": "Please extract all text content from the image if any, and identify the main elements and information."
            },
            "describe": {
                "CN": "请用详细的描述性语言描述这张图片，适合用作文件命名或分类依据。",
                "EN": "Please describe this image with detailed descriptive language, suitable for file naming or classification purposes."
            }
        }
        
        lang = self.language
        if task_type in task_prompts and lang in task_prompts[task_type]:
            return task_prompts[task_type][lang]
        
        return base_prompt
    
    def _build_file_analysis_prompt(self, task_type: AITaskType, file_info: Dict[str, Any]) -> str:
        """构建文件分析提示词"""
        file_type = file_info.get('file_type', 'unknown')
        filename = file_info.get('filename', 'unknown')
        
        if self.language == "CN":
            base_system = f"你是一个专业的文件分析助手。用户将提供一个{file_type}类型的文件（{filename}）的信息和内容，请基于要求进行分析。"
        else:
            base_system = f"You are a professional file analysis assistant. The user will provide information and content of a {file_type} file ({filename}), please analyze based on requirements."
        
        task_specific_prompts = {
            AITaskType.CLASSIFY_FILE: {
                "CN": f"{base_system}\n\n请分析文件内容并提供分类建议。返回JSON格式结果，包含：\n- category: 主分类（如：文档、图片、代码等）\n- subcategory: 子分类（更具体的分类）\n- confidence: 置信度（0-1）\n- reasoning: 分类理由\n- suggested_folder: 建议的文件夹名称",
                "EN": f"{base_system}\n\nPlease analyze the file content and provide classification suggestions. Return JSON format result including:\n- category: main category (e.g., document, image, code, etc.)\n- subcategory: subcategory (more specific classification)\n- confidence: confidence level (0-1)\n- reasoning: classification reasoning\n- suggested_folder: suggested folder name"
            },
            AITaskType.GENERATE_SUMMARY: {
                "CN": f"{base_system}\n\n请为这个文件生成一个简洁的摘要，突出主要内容和关键信息。",
                "EN": f"{base_system}\n\nPlease generate a concise summary for this file, highlighting the main content and key information."
            },
            AITaskType.EXTRACT_TEXT: {
                "CN": f"{base_system}\n\n请提取文件中的所有重要文本信息，去除格式化内容，返回纯文本。",
                "EN": f"{base_system}\n\nPlease extract all important text information from the file, remove formatting content, and return plain text."
            },
            AITaskType.ANALYZE_CONTENT: {
                "CN": f"{base_system}\n\n请深入分析文件内容，包括主题、结构、质量、用途等方面。",
                "EN": f"{base_system}\n\nPlease analyze the file content in depth, including themes, structure, quality, purpose, etc."
            }
        }
        
        lang = self.language
        if task_type in task_specific_prompts:
            return task_specific_prompts[task_type].get(lang, task_specific_prompts[task_type]["CN"])
        
        return base_system
    
    def _build_decision_prompt(self, classification_rules: Dict[str, Any] = None) -> str:
        """构建决策提示词"""
        if self.language == "CN":
            prompt = """你是一个智能文件分类决策系统。基于提供的文件分析结果，为每个文件做出最佳的分类决策。

请考虑以下因素：
1. 文件类型和扩展名
2. 文件内容和主题
3. 文件大小和复杂度
4. 相似文件的归类原则
5. 用户的使用习惯

返回JSON格式的决策结果，包含：
{
  "classifications": [
    {
      "file_id": "文件标识",
      "category": "主分类",
      "subcategory": "子分类",
      "confidence": 0.95,
      "reasoning": "分类理由",
      "suggested_path": "建议路径"
    }
  ],
  "summary": {
    "total_files": 数量,
    "categories_used": ["分类1", "分类2"],
    "recommendations": ["建议1", "建议2"]
  }
}"""
        else:
            prompt = """You are an intelligent file classification decision system. Based on the provided file analysis results, make optimal classification decisions for each file.

Please consider the following factors:
1. File type and extension
2. File content and theme
3. File size and complexity
4. Classification principles for similar files
5. User usage patterns

Return decision results in JSON format:
{
  "classifications": [
    {
      "file_id": "file identifier",
      "category": "main category",
      "subcategory": "subcategory",
      "confidence": 0.95,
      "reasoning": "classification reasoning",
      "suggested_path": "suggested path"
    }
  ],
  "summary": {
    "total_files": count,
    "categories_used": ["category1", "category2"],
    "recommendations": ["recommendation1", "recommendation2"]
  }
}"""
        
        if classification_rules:
            if self.language == "CN":
                prompt += f"\n\n特殊分类规则：\n{json.dumps(classification_rules, ensure_ascii=False, indent=2)}"
            else:
                prompt += f"\n\nSpecial classification rules:\n{json.dumps(classification_rules, ensure_ascii=False, indent=2)}"
        
        return prompt
    
    def _build_filename_generation_prompt(self) -> str:
        """构建文件名生成提示词"""
        if self.language == "CN":
            return """你是一个智能文件重命名助手。基于文件内容生成描述性的文件名。

要求：
1. 文件名应该简洁明了，能反映文件的主要内容
2. 使用适当的中文或英文，避免特殊字符
3. 长度控制在50个字符以内
4. 保持原文件的扩展名
5. 如果是重要文档，可以包含日期或版本信息

返回JSON格式：
{
  "suggested_names": ["建议名称1", "建议名称2", "建议名称3"],
  "best_choice": "最佳选择",
  "reasoning": "命名理由"
}"""
        else:
            return """You are an intelligent file renaming assistant. Generate descriptive filenames based on file content.

Requirements:
1. Filenames should be concise and clear, reflecting the main content
2. Use appropriate Chinese or English, avoid special characters
3. Keep length under 50 characters
4. Maintain the original file extension
5. For important documents, include date or version information if relevant

Return JSON format:
{
  "suggested_names": ["suggested name 1", "suggested name 2", "suggested name 3"],
  "best_choice": "best choice",
  "reasoning": "naming reasoning"
}"""
    
    def _prepare_analysis_summary(self, file_analyses: List[Dict[str, Any]]) -> str:
        """准备文件分析摘要"""
        summary_parts = []
        
        for i, analysis in enumerate(file_analyses, 1):
            file_info = analysis.get('file_info', {})
            ai_result = analysis.get('ai_result') or {}
            
            part = f"文件 {i}:\n"
            part += f"  名称: {file_info.get('filename', 'unknown')}\n"
            part += f"  类型: {file_info.get('file_type', 'unknown')}\n"
            part += f"  大小: {file_info.get('size_human', 'unknown')}\n"
            
            if ai_result.get('success'):
                part += f"  AI分析: {ai_result.get('content', '')[:200]}...\n"
            else:
                part += f"  分析失败: {ai_result.get('error_message', '')}\n"
            
            part += "\n"
            summary_parts.append(part)
        
        return "\n".join(summary_parts)
    
    def get_available_models(self) -> Dict[str, str]:
        """获取可用的模型列表"""
        return {
            "图像分析模型": self.model_map[ModelType.IMAGE_ANALYSIS],
            "文件分析模型": self.model_map[ModelType.FILE_ANALYSIS],
            "决策模型": self.model_map[ModelType.DECISION],
            "视频分析模型": self.model_map[ModelType.VIDEO_ANALYSIS]
        }
    
    def update_model_config(self, model_type: ModelType, model_name: str):
        """更新模型配置"""
        self.model_map[model_type] = model_name
        
        # 更新配置文件
        config_key_map = {
            ModelType.IMAGE_ANALYSIS: 'image_analysis_model',
            ModelType.FILE_ANALYSIS: 'file_analysis_model',
            ModelType.DECISION: 'decision_model',
            ModelType.VIDEO_ANALYSIS: 'video_analysis_model'
        }
        
        if model_type in config_key_map:
            self.config_manager.set_config('Settings', config_key_map[model_type], model_name)
            self.config_manager.save_config()
            
        self.logger.info(f"更新模型配置: {model_type.value} -> {model_name}")
    
    def get_usage_statistics(self) -> Dict[str, Any]:
        """获取使用统计"""
        success_rate = ((self.request_count - self.error_count) / self.request_count * 100) if self.request_count > 0 else 0
        
        return {
            "total_requests": self.request_count,
            "successful_requests": self.request_count - self.error_count,
            "error_count": self.error_count,
            "success_rate": round(success_rate, 2),
            "total_tokens": self.total_tokens,
            "average_tokens_per_request": round(self.total_tokens / self.request_count, 2) if self.request_count > 0 else 0
        }
    
    def reset_statistics(self):
        """重置统计信息"""
        self.request_count = 0
        self.error_count = 0
        self.total_tokens = 0
        self.logger.info("统计信息已重置")
    
    async def batch_analyze_files(self, file_analyses: List[Dict[str, Any]], 
                                 callback: Callable = None) -> List[AIResponse]:
        """
        批量分析文件（异步）
        
        Args:
            file_analyses: 文件分析数据列表
            callback: 进度回调函数
            
        Returns:
            AI分析结果列表
        """
        results = []
        total = len(file_analyses)
        
        self.logger.info(f"开始批量AI分析，共 {total} 个文件")
        
        for i, analysis in enumerate(file_analyses):
            try:
                if callback:
                    callback(i + 1, total, analysis.get('file_info', {}).get('filename', 'unknown'))
                
                # 分析文件内容
                file_content = analysis.get('content', '')
                file_info = analysis.get('file_info', {})
                
                result = self.analyze_file_content(file_content, file_info, AITaskType.CLASSIFY_FILE)
                results.append(result)
                
                # 短暂延迟，避免API限流
                await asyncio.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"批量分析文件失败: {e}")
                error_response = AIResponse("", "unknown")
                error_response.success = False
                error_response.error_message = str(e)
                results.append(error_response)
        
        self.logger.info(f"批量AI分析完成，成功: {len([r for r in results if r.success])}, "
                        f"失败: {len([r for r in results if not r.success])}")
        
        return results