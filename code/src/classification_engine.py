#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分类引擎模块 (classification_engine)

职责：
1. 接受来自 `FileAnalyzer` 的分析结果列表，调用 `AIClient.make_classification_decision` 获得整体分类建议。
2. 解析 AI 返回的 JSON 字符串，构建 `file_path -> 分类信息` 的映射。
3. 在 AI 不可用或解析失败时，使用 `fallback` 规则（基于 `file_type`）进行简单分类。
4. 提供 `organize_files` 方法，调用 `FileOperationManager.organize_files_by_classification` 将文件复制/移动至目标目录。

分类信息统一数据结构：
{
    "category": "主分类",
    "subcategory": "子分类",          # 可选
    "confidence": 0.95,              # AI 置信度，可选
    "reasoning": "分类理由",         # 可选
    "suggested_path": "建议相对路径"   # 可选
}
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

# 本地模块
from .config_manager import ConfigManager
from .logger import get_logger
from .ai_client import AIClient, AIResponse
from .file_operations import FileOperationManager


class ClassificationEngine:
    """文件分类引擎"""

    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        ai_client: Optional[AIClient] = None,
        file_operation_manager: Optional[FileOperationManager] = None,
    ) -> None:
        self.config_manager = config_manager or ConfigManager()
        self.logger = get_logger("classification_engine")

        # AI 客户端（可选）
        if ai_client is not None:
            self.ai_client = ai_client
        else:
            try:
                self.ai_client = AIClient(config_manager=self.config_manager)
            except Exception as e:
                self.logger.warning(f"AIClient 初始化失败，分类将使用回退模式: {e}")
                self.ai_client = None

        # 文件操作管理器（用于整理文件，可选）
        self.file_operation_manager = file_operation_manager or FileOperationManager(
            config_manager=self.config_manager
        )

    # ------------------------------------------------------------------
    # 公开方法
    # ------------------------------------------------------------------
    def classify_files(
        self,
        file_analyses: List[Dict[str, Any]],
        classification_rules: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """对文件进行分类决策

        Args:
            file_analyses: 来自 `FileAnalyzer.analyze_file` 的结果列表
            classification_rules: 额外的分类规则（可选）

        Returns:
            classification_results: {file_path: classification_dict}
        """
        if not file_analyses:
            return {}

        # 如果无法使用 AI，则直接回退
        if self.ai_client is None:
            self.logger.info("AIClient 不可用，使用 fallback 规则进行分类")
            return self._fallback_classification(file_analyses)

        # 调用 AI 做整体分类决策
        try:
            ai_response: AIResponse = self.ai_client.make_classification_decision(
                file_analyses, classification_rules
            )
        except Exception as e:
            self.logger.error(f"调用 AI 分类失败: {e}")
            return self._fallback_classification(file_analyses)

        if not ai_response.success:
            self.logger.error(f"AI 分类响应失败: {ai_response.error_message}")
            return self._fallback_classification(file_analyses)

        # 解析 AI 返回内容
        classification_results = self._parse_ai_classification(
            ai_response.content, file_analyses
        )
        if not classification_results:
            self.logger.warning("AI 分类解析失败，使用 fallback 规则")
            classification_results = self._fallback_classification(file_analyses)

        return classification_results

    def organize_files(
        self,
        classification_results: Dict[str, Dict[str, Any]],
        target_root: Union[str, Path],
        operation_mode: str = None,
    ) -> Dict[str, Any]:
        """根据分类结果整理文件（复制/移动）

        Args:
            classification_results: `classify_files` 的输出结果
            target_root: 目标根目录
            operation_mode: 'copy' 或 'move'，默认为配置中的 `file_operation`

        Returns:
            文件操作统计结果
        """
        # 若包含用户编辑的 suggested_path，优先按照 suggested_path 组织
        adjusted_results: Dict[str, Dict[str, Any]] = {}
        for file_path, info in classification_results.items():
            info = dict(info) if info else {}
            # 兼容 new_path/suggested_path
            if info.get('suggested_path'):
                info['category'] = info.get('category', 'Custom')
                # 将 suggested_path 拆分为 category/subcategory（可选）
                sp = str(info['suggested_path']).strip('/\\')
                parts = [p for p in sp.replace('\\', '/').split('/') if p]
                if len(parts) >= 1:
                    info['category'] = parts[0]
                if len(parts) >= 2:
                    info['subcategory'] = '/'.join(parts[1:])
            adjusted_results[file_path] = info

        return self.file_operation_manager.organize_files_by_classification(
            adjusted_results, target_root, operation_mode
        )

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------
    def _parse_ai_classification(
        self,
        content: str,
        file_analyses: List[Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        """解析 AI 返回的 JSON 分类结果"""
        if not content:
            return {}

        # 尝试直接解析
        parsed_json: Optional[Dict[str, Any]] = None
        try:
            parsed_json = json.loads(content)
        except json.JSONDecodeError:
            # 尝试提取 JSON 子串
            try:
                start = content.find("{")
                end = content.rfind("}")
                if start != -1 and end != -1 and end > start:
                    parsed_json = json.loads(content[start : end + 1])
            except Exception:
                parsed_json = None

        if not parsed_json:
            self.logger.error("无法解析 AI 返回的 JSON 内容")
            return {}

        classifications = parsed_json.get("classifications", [])
        if not isinstance(classifications, list):
            self.logger.error("AI JSON 中缺少 'classifications' 列表")
            return {}

        # 构建 filename/path 映射
        file_map: Dict[str, str] = {}
        for analysis in file_analyses:
            fi = analysis.get("file_info", {})
            path = fi.get("file_path") or fi.get("full_path") or fi.get("filename")
            if not path:
                continue
            # 使用文件名和完整路径两种键进行映射
            filename = fi.get("filename", path)
            file_map[filename] = path
            file_map[path] = path

        # 预构建索引到路径映射，便于处理 "文件 1" 这类编号
        index_path_map: Dict[int, str] = {}
        for idx, analysis in enumerate(file_analyses, 1):  # 1-based
            fi = analysis.get("file_info", {})
            path = fi.get("file_path") or fi.get("full_path") or fi.get("filename")
            if path:
                index_path_map[idx] = path

        classification_results: Dict[str, Dict[str, Any]] = {}
        for item in classifications:
            file_id = item.get("file_id") or item.get("filename") or ""
            if not file_id:
                continue
            file_path = file_map.get(file_id)

            # 尝试匹配 "文件 1" / "File 1" 模式
            if not file_path:
                import re
                m = re.match(r"(?:文件|file)\s*(\d+)", str(file_id).strip(), re.IGNORECASE)
                if m:
                    idx = int(m.group(1))
                    file_path = index_path_map.get(idx)

            if not file_path:
                # 尝试直接把 file_id 当作路径
                file_path = file_id

            classification_results[file_path] = {
                "category": item.get("category", "Unknown"),
                "subcategory": item.get("subcategory", ""),
                "confidence": item.get("confidence"),
                "reasoning": item.get("reasoning"),
                "suggested_path": item.get("suggested_path"),
            }

        return classification_results

    def _fallback_classification(
        self, file_analyses: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """AI 失效时的简单分类方案：按 file_type 分组"""
        results: Dict[str, Dict[str, Any]] = {}
        for analysis in file_analyses:
            file_info = analysis.get("file_info", {})
            file_type = file_info.get("file_type", "unknown").capitalize()
            filename = file_info.get("filename")
            full_path = file_info.get("file_path") or filename  # FileAnalyzer 目前未存储完整路径
            if not full_path:
                continue
            results[full_path] = {
                "category": file_type if file_type else "Unknown",
                "subcategory": "",
                "confidence": None,
                "reasoning": "Fallback classification by file_type",
                "suggested_path": None,
            }
        return results


# ----------------------------------------------------------------------
# 便捷函数
# ----------------------------------------------------------------------

def get_classification_engine() -> ClassificationEngine:
    """获取（或创建）分类引擎单例"""
    if not hasattr(get_classification_engine, "_instance"):
        get_classification_engine._instance = ClassificationEngine()
    return get_classification_engine._instance 