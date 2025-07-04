#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件分析器模块 (file_analyzer)

职责：
1. 检测并标识文件类型（图片、视频、文档、压缩包、代码等）
2. 结合 `ContentExtractor` 提取文件基础信息及内容
3. 调用 `AIClient` 对文件内容进行进一步 AI 分析（可选）
4. 返回统一的数据结构供后续模块（分类、重命名等）使用

本模块并不直接做分类决策，而是专注于「分析」阶段。后续的分类、重命名等功能可基于
此模块的返回结果进行决策处理。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Any, List, Union, Optional
import json, threading

# 本地模块
from .config_manager import ConfigManager
from .logger import get_logger
from .content_extractor import ContentExtractor
from .ai_client import AIClient, AITaskType, AIResponse


class FileAnalyzer:
    """文件分析器核心类"""

    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        ai_client: Optional[AIClient] = None,
        content_extractor: Optional[ContentExtractor] = None,
    ) -> None:
        # 配置管理器
        self.config_manager = config_manager or ConfigManager()

        # 日志器
        self.logger = get_logger("file_analyzer")

        # 内容提取器 & AI 客户端
        self.content_extractor = content_extractor or ContentExtractor(
            config_manager=self.config_manager
        )
        self.ai_client = ai_client  # 允许外部传入以便做 Mock 或共享实例
        if self.ai_client is None:
            try:
                # AIClient 依赖 openai 库，用户可在无网络或无 key 的环境下跳过
                self.ai_client = AIClient(config_manager=self.config_manager)
            except Exception as e:
                # AI 客户端不可用时，仅记录日志，后续分析流程将跳过 AI 调用
                self.logger.warning(f"AIClient 初始化失败，已禁用 AI 分析功能: {e}")
                self.ai_client = None

        # 从配置读取开关
        self.enable_video_analysis = (
            str(
                self.config_manager.get_config(
                    "Settings", "enable_video_analysis", "false"
                )
            ).lower()
            == "true"
        )

        self.logger.info("文件分析器初始化完成")

        # -------------- 缓存相关 ------------------
        cache_dir = Path("cache")
        cache_dir.mkdir(exist_ok=True)
        self._cache_path = cache_dir / "analysis_cache.json"
        self._cache_lock = threading.Lock()
        self._analysis_cache: Dict[str, Dict[str, Any]] = self._load_cache()

    # ---------------------------------------------------------------------
    # 公共方法
    # ---------------------------------------------------------------------

    def analyze_file(
        self,
        file_path: Union[str, Path],
        task_type: AITaskType = AITaskType.CLASSIFY_FILE,
    ) -> Dict[str, Any]:
        """分析单个文件

        Args:
            file_path: 文件路径
            task_type: AI 分析任务类型，默认 `CLASSIFY_FILE`

        Returns:
            统一结构的分析结果字典，包含：
            {
                "file_info": <基础信息+内容摘要>,
                "ai_result": <AIResponse.to_dict()> 或 None,
            }
        """
        file_path = Path(file_path)
        self.logger.debug(f"开始分析文件: {file_path}")

        if not file_path.exists() or not file_path.is_file():
            error_msg = f"文件不存在: {file_path}"
            self.logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        # 0. 检查缓存 -------------------------------------------------------
        file_hash = None
        if file_path.exists():
            # 先快速获取 md5
            file_hash = self.content_extractor._calculate_file_hash(file_path)
            if file_hash and file_hash in self._analysis_cache:
                self.logger.debug(f"命中缓存: {file_path}")
                return self._analysis_cache[file_hash]

        # 1. 内容提取阶段 ---------------------------------------------------
        try:
            file_info = self.content_extractor.extract_content(file_path)
            # 补充完整路径
            file_info["file_path"] = str(file_path.resolve())
            file_hash = file_info.get("file_hash", file_hash)
        except Exception as e:
            # 若内容提取失败，直接返回错误信息
            self.logger.error(f"内容提取失败: {e}")
            return {"file_info": {"error": str(e)}, "ai_result": None}

        # 2. AI 分析阶段 -----------------------------------------------------
        ai_result_dict: Optional[Dict[str, Any]] = None
        if self.ai_client is not None:
            ai_result_dict = self._run_ai_analysis(
                file_path=file_path,
                file_info=file_info,
                task_type=task_type,
            )
        else:
            self.logger.debug("AIClient 不可用，跳过 AI 分析阶段")

        result = {"file_info": file_info, "ai_result": ai_result_dict}

        # 写入缓存
        if file_hash:
            with self._cache_lock:
                self._analysis_cache[file_hash] = result
            self._save_cache()

        return result

    async def analyze_files_batch(
        self,
        file_paths: List[Union[str, Path]],
        task_type: AITaskType = AITaskType.CLASSIFY_FILE,
        progress_callback=None,
    ) -> List[Dict[str, Any]]:
        """批量分析文件（异步）

        Args:
            file_paths: 文件路径列表
            task_type: AI 任务类型
            progress_callback: 进度回调，用于 UI 更新

        Returns:
            分析结果列表，与 `file_paths` 顺序一致
        """
        results: List[Dict[str, Any]] = []
        total = len(file_paths)
        for idx, p in enumerate(file_paths, start=1):
            try:
                result = self.analyze_file(p, task_type=task_type)
            except Exception as e:
                result = {"file_info": {"error": str(e)}, "ai_result": None}
            results.append(result)

            # 进度回调
            if progress_callback is not None:
                try:
                    progress_callback(idx, total, result)
                except Exception:  # noqa: E722
                    pass  # 忽略回调错误，保持分析流程
        return results

    # ---------------------------------------------------------------------
    # 私有辅助方法
    # ---------------------------------------------------------------------

    def _run_ai_analysis(
        self,
        file_path: Path,
        file_info: Dict[str, Any],
        task_type: AITaskType,
    ) -> Optional[Dict[str, Any]]:
        """根据文件类型调用 AIClient 做进一步分析"""
        file_type = file_info.get("file_type", "unknown")
        self.logger.debug(f"文件类型: {file_type} -> 准备调用 AI 分析")

        # 若 AIClient 初始化失败，这里会是 None
        if self.ai_client is None:
            return None

        try:
            if file_type == "image":
                response: AIResponse = self.ai_client.analyze_image(file_path)
            elif file_type == "video":
                if self.enable_video_analysis:
                    # 对于视频，目前 AIClient 没有专用接口，
                    # 这里简单地将元数据作为文本发送给通用文件分析模型
                    video_meta_str = os.linesep.join(
                        [f"{k}: {v}" for k, v in file_info.items() if k != "file_type"]
                    )
                    response = self.ai_client.analyze_file_content(
                        file_content=video_meta_str,
                        file_info=file_info,
                        task_type=AITaskType.ANALYZE_CONTENT,
                    )
                else:
                    self.logger.info("已禁用视频 AI 分析，跳过")
                    return None
            else:
                # 文档/代码/压缩包等统一走文本分析
                # ContentExtractor 在提取文档时，会将主要内容放入 "content" 字段
                content_text = str(file_info.get("content", ""))
                if not content_text:
                    self.logger.debug("未提取到可用文本内容，跳过 AI 分析")
                    return None
                response = self.ai_client.analyze_file_content(
                    file_content=content_text,
                    file_info=file_info,
                    task_type=task_type,
                )

            return response.to_dict() if isinstance(response, AIResponse) else None
        except Exception as e:
            self.logger.error(f"AI 分析失败: {e}")
            return {"success": False, "error": str(e)}

    # ------------------ 缓存方法 ------------------
    def _load_cache(self) -> Dict[str, Any]:
        if self._cache_path.exists():
            try:
                with open(self._cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_cache(self):
        try:
            with self._cache_lock:
                with open(self._cache_path, "w", encoding="utf-8") as f:
                    json.dump(self._analysis_cache, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


# -------------------------------------------------------------------------
# 便捷函数
# -------------------------------------------------------------------------

def get_file_analyzer() -> FileAnalyzer:
    """获取（或创建）文件分析器单例，方便外部调用"""
    # 这里不实现严格单例，只提供简单的共享实例
    if not hasattr(get_file_analyzer, "_instance"):
        get_file_analyzer._instance = FileAnalyzer()
    return get_file_analyzer._instance 