#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 重命名引擎 (renaming_engine)

职责：
- 基于提取的文件内容与元数据，调用 AI 生成更有语义的文件名建议
- 提供单文件与批量接口
- 具备健壮的 JSON 解析与回退策略
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .logger import get_logger
from .config_manager import ConfigManager
from .content_extractor import ContentExtractor
from .file_analyzer import FileAnalyzer
from .ai_client import AIClient, AIResponse, AITaskType


# Windows 文件名禁止字符: <>:"/\|?*
WINDOWS_FORBIDDEN_CHARS = '<>:"/\\|?*'
WINDOWS_FORBIDDEN_PATTERN = re.compile(f"[{re.escape(WINDOWS_FORBIDDEN_CHARS)}]")


class RenamingEngine:
    """AI 文件重命名引擎"""

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        self.logger = get_logger("renaming_engine")
        self.config_manager = config_manager or ConfigManager()
        self.extractor = ContentExtractor(self.config_manager)

        # AI 客户端可能不可用（未安装 openai 或未配置），需兜底
        try:
            self.ai_client = AIClient(config_manager=self.config_manager)
        except Exception as e:
            self.logger.warning(f"AIClient 不可用，重命名将使用回退方案: {e}")
            self.ai_client = None

        # 文件分析器（与整理前一致的分析通道，带缓存）
        try:
            self.analyzer = FileAnalyzer(
                config_manager=self.config_manager,
                ai_client=self.ai_client,
                content_extractor=self.extractor,
            )
        except Exception as e:
            self.logger.warning(f"FileAnalyzer 初始化失败，将退回基础提取: {e}")
            self.analyzer = None

    # ------------------------------------------------------------------
    # 对外接口
    # ------------------------------------------------------------------
    def suggest_names_for_file(self, file_path: str) -> Dict[str, Any]:
        """为单个文件生成命名建议。

        Returns:
            {
              "suggested_names": [str, ...],
              "best_choice": str,
              "reasoning": str
            }
        """
        path = Path(file_path)
        file_info = None
        ai_analysis_text = ""
        try:
            if self.analyzer is not None:
                analysis = self.analyzer.analyze_file(path, task_type=AITaskType.ANALYZE_CONTENT)
                file_info = analysis.get("file_info") or {}
                ai_result = analysis.get("ai_result") or {}
                if isinstance(ai_result, dict) and ai_result.get("success") and ai_result.get("content"):
                    ai_analysis_text = str(ai_result.get("content"))
            else:
                file_info = self.extractor.extract_content(path)
        except Exception as e:
            self.logger.error(f"分析失败，使用回退: {path} -> {e}")
            return self._fallback_suggestions(path)

        # 构造用于命名的内容摘要（融合 AI 分析）
        content_for_naming = self._compose_content_for_naming(file_info)
        if ai_analysis_text:
            content_for_naming = f"{content_for_naming}\nAI分析: {ai_analysis_text}"[:2000]

        # 优先走 AI
        if self.ai_client is not None:
            try:
                ai_resp: AIResponse = self.ai_client.generate_filename(
                    content_for_naming, file_info={
                        "filename": file_info.get("filename", path.name),
                        "file_type": file_info.get("file_type", "unknown"),
                    }
                )
                if ai_resp and ai_resp.success and ai_resp.content:
                    parsed = self._parse_ai_json(ai_resp.content)
                    if parsed:
                        return self._post_process_suggestions(parsed, path)
            except Exception as e:
                self.logger.warning(f"AI 生成名称失败，使用回退: {e}")

        # 回退方案
        return self._fallback_suggestions(path, file_info)

    def suggest_names_batch(self, file_paths: List[str]) -> Dict[int, Dict[str, Any]]:
        """批量生成命名建议，返回按索引的映射。"""
        results: Dict[int, Dict[str, Any]] = {}
        for idx, fp in enumerate(file_paths):
            try:
                results[idx] = self.suggest_names_for_file(fp)
            except Exception as e:
                self.logger.error(f"批量生成建议失败 {fp}: {e}")
                results[idx] = self._fallback_suggestions(Path(fp))
        return results

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------
    def _compose_content_for_naming(self, file_info: Dict[str, Any]) -> str:
        """尽可能组合文本用于命名的上下文。"""
        parts: List[str] = []

        # 基础属性
        filename = file_info.get("filename")
        file_type = file_info.get("file_type")
        if filename:
            parts.append(f"文件名: {filename}")
        if file_type:
            parts.append(f"类型: {file_type}")

        # 文本内容
        for key in ("content", "content_preview"):
            if file_info.get(key):
                parts.append(str(file_info[key]))
                break

        # 图片/视频/音频的结构化摘要
        if file_type == "image":
            w = file_info.get("width")
            h = file_info.get("height")
            fmt = file_info.get("format")
            if w and h:
                parts.append(f"分辨率: {w}x{h}")
            if fmt:
                parts.append(f"格式: {fmt}")
        elif file_type == "video":
            dur = file_info.get("duration")
            codec = file_info.get("video_codec")
            if dur:
                parts.append(f"时长: {dur}s")
            if codec:
                parts.append(f"编码: {codec}")
        elif file_type == "audio":
            codec = file_info.get("codec")
            sr = file_info.get("sample_rate")
            if codec:
                parts.append(f"音频编码: {codec}")
            if sr:
                parts.append(f"采样率: {sr}")

        text = "\n".join(parts)
        # 限长
        return text[:2000]

    def _parse_ai_json(self, content: str) -> Optional[Dict[str, Any]]:
        """宽松解析 AI 返回 JSON。"""
        try:
            return json.loads(content)
        except Exception:
            try:
                start = content.find("{")
                end = content.rfind("}")
                if start != -1 and end != -1 and end > start:
                    return json.loads(content[start : end + 1])
            except Exception:
                return None
        return None

    def _post_process_suggestions(self, parsed: Dict[str, Any], path: Path) -> Dict[str, Any]:
        names = parsed.get("suggested_names") or []
        best = parsed.get("best_choice") or (names[0] if names else path.stem)
        reason = parsed.get("reasoning") or ""

        cleaned = [self._sanitize_filename(n, keep_extension=False) for n in names if isinstance(n, str)]
        if best:
            best = self._sanitize_filename(str(best), keep_extension=False)

        # 去重并保留顺序
        seen = set()
        unique = []
        for n in [best] + cleaned:
            if not n:
                continue
            if n not in seen:
                seen.add(n)
                unique.append(n)

        # 限制数量
        unique = unique[:5] if unique else [path.stem]

        return {
            "suggested_names": unique,
            "best_choice": unique[0],
            "reasoning": reason
        }

    def _fallback_suggestions(self, path: Path, file_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        stem = path.stem
        cleaned = self._sanitize_filename(stem, keep_extension=False)
        candidates = [cleaned]

        # 附加一些启发式候选
        try:
            if file_info:
                ft = file_info.get("file_type")
                if ft == "image" and file_info.get("width") and file_info.get("height"):
                    candidates.append(f"{cleaned}_{file_info['width']}x{file_info['height']}")
                if ft == "document" and file_info.get("page_count"):
                    candidates.append(f"{cleaned}_pages{file_info['page_count']}")
        except Exception:
            pass

        # 去重
        uniq = []
        seen = set()
        for n in candidates:
            if n and n not in seen:
                uniq.append(n)
                seen.add(n)

        return {
            "suggested_names": uniq[:3],
            "best_choice": uniq[0] if uniq else cleaned,
            "reasoning": "fallback"
        }

    def _sanitize_filename(self, name: str, keep_extension: bool = False) -> str:
        """清理非法字符，控制长度，避免首尾空格。"""
        # 去除扩展名（AI 建议通常不携带扩展名）
        if not keep_extension and "." in name:
            try:
                name = Path(name).stem
            except Exception:
                pass

        name = name.strip()
        # 替换 Windows 禁止字符
        name = WINDOWS_FORBIDDEN_PATTERN.sub("_", name)
        # 避免控制字符
        name = "".join(ch for ch in name if ord(ch) >= 32)
        # 收敛连字符
        name = re.sub(r"[\s\-]+", " ", name)
        name = name.replace(" ", "_")
        # 长度限制
        return name[:80] if len(name) > 80 else name


