# 文脉通 (DocStream Navigator) - 重构版

> **一款基于人工智能技术的智能文件整理工具**  
> 使用AI技术智能识别文件内容，自动进行分类整理，让您的文件管理更轻松、更高效

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8+-green.svg)](https://python.org)
[![Status](https://img.shields.io/badge/Status-开发中-yellow.svg)]()

## 🚀 项目概述

文脉通是一款智能文件整理工具，寓意**贯通文档信息的脉络，实现流畅高效的文件整理和调用**。本版本是对原项目的完全重构，采用现代化的技术栈，提供更好的用户体验和更强大的功能。

### 🔄 重构说明

- **抛弃 PyQt5**：使用 PyWebView 提供更现代化的界面体验
- **统一 AI 调用**：采用 OpenAI 库统一管理多种 AI 服务
- **模块化架构**：重新设计代码结构，提高可维护性
- **增强功能**：支持更多文件格式和更智能的分类策略

## ✨ 主要功能

### 🤖 AI 智能识别
- **多模型支持**：集成图像分析、文件分析、决策模型
- **多格式兼容**：支持图片、视频、文档、压缩包等多种文件类型
- **内容理解**：深度分析文件内容，生成准确的分类建议

### 📁 智能文件整理
- **自动分类**：基于 AI 分析结果自动创建合理的目录结构
- **灵活操作**：支持复制/移动两种文件操作模式
- **批量处理**：高效处理大量文件，支持多线程并发
- **撤销功能**：安全的操作撤销机制

### 🏷️ 智能重命名
- **内容驱动**：根据文件内容自动生成描述性文件名
- **批量重命名**：支持批量文件重命名和预览
- **冲突处理**：智能处理文件名冲突和特殊字符

### 🌍 多语言支持
- **界面本地化**：支持中英文界面切换
- **命名国际化**：支持中英文文件夹命名策略
- **内容识别**：多语言文档内容识别和分析

## 🛠️ 技术栈

### 核心框架
- **PyWebView**: 现代化桌面应用界面框架
- **OpenAI Library**: 统一的 AI API 调用接口
- **Python 3.8+**: 主要开发语言

### AI 服务支持
- **SiliconFlow**: 默认 AI 服务提供商
- **OpenAI**: 官方 OpenAI API
- **Ollama**: 本地 AI 模型支持
- **自定义模型**: 支持用户自定义 AI 模型

### 前端技术
- **HTML5/CSS3**: 现代化界面设计
- **JavaScript**: 交互逻辑实现
- **Responsive Design**: 自适应界面布局

## 📂 项目结构

```
AI-File/
├── code/                   # 源代码目录
│   ├── main.py            # 应用程序入口
│   ├── config.ini         # 配置文件
│   ├── src/               # 核心模块
│   └── tool/              # 工具函数
├── LICENSE                # 开源许可证
└── README.md             # 项目说明文档
```

## ⚙️ 配置说明

项目配置通过 `code/config.ini` 文件管理：

```ini
[API]
api_key = your_api_key_here          # AI 服务 API 密钥
api_url = https://api.siliconflow.cn/v1  # API 服务地址
api_type = OpenAI API                # API 类型

[Settings]
language = CN                        # 界面语言 (CN/EN)
file_operation = move                # 文件操作模式 (copy/move)
thread_count = 8                     # 并发线程数
subfolder_mode = whole               # 子文件夹处理模式
```

## 🚧 开发状态

**当前状态**: 🔨 开发中

## 🎯 快速开始

### 环境要求
- Python 3.8 或更高版本
- 稳定的网络连接（用于 AI API 调用）
- Windows 10/11 或 macOS 10.14+ 或 Linux

### 安装依赖
```bash
pip install -r requirements.txt
```

### 配置设置
1. 复制 `config.ini.example` 为 `config.ini`
2. 填入您的 AI 服务 API 密钥
3. 根据需要调整其他配置项

### 运行应用
```bash
python code/main.py
```

## 🤝 贡献指南

我们欢迎社区贡献！请遵循以下步骤：

1. Fork 本项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📄 许可证

本项目采用 Apache 2.0 许可证。详情请参阅 [LICENSE](LICENSE) 文件。

## 🔗 相关链接

- **官方网站**: [ai-file.xzt.plus](https://ai-file.xzt.plus/)
- **原项目**: [GitHub - LoosePrince/AI-File](https://github.com/LoosePrince/AI-File)
- **问题反馈**: [Issues](https://github.com/LoosePrince/AI-File/issues)

## ⚠️ 免责声明

- 建议首次使用时选择"复制"模式而非"移动"模式
- 处理重要文件前请先备份
- 请妥善保管 API 密钥，避免泄露

---

**© 2025 ai-file.xzt.plus. 保留所有权利。**