## 文脉通重构版开发任务列表

### 开发计划
- [x] 1. 配置管理模块 (config_manager)
- [x] 2. AI客户端模块 (ai_client)
- [x] 3. 文件分析器 (file_analyzer)
- [x] 4. 内容提取器 (content_extractor)
- [x] 5. 分类引擎 (classification_engine)
- [x] 6. 文件操作模块 (file_operations)
- [ ] 7. 智能重命名引擎 (rename_engine)
- [x] 8. PyWebView基础框架 (web_ui_foundation / ui_manager)
- [x] 9. 主界面
- [x] 10. 设置界面
- [ ] 11. 重命名界面
- [x] 12. 进度管理系统 (progress_system / progress_manager)
- [x] 13. 错误处理系统 (error_handling / logger)
- [ ] 14. 多语言支持 (multilingual_support)
- [x] 15. 主应用程序 (main_application / main.py)

### 📋 核心架构模块

**1. 配置管理模块 (config_manager)**
- 解析和管理 `config.ini` 中的所有配置项
- 处理API密钥、模型选择、语言设置等
- 提供配置热更新和验证功能

**2. AI客户端模块 (ai_client)**
- 使用 `openai` 库统一封装API调用
- 支持图像分析、文件分析、决策模型的多模型切换
- 处理API限流、重试机制和错误恢复

**3. 文件分析器 (file_analyzer)**
- 检测文件类型（图片、视频、文档、压缩包）
- 调用相应的AI模型进行内容分析
- 返回结构化的分析结果

**4. 内容提取器 (content_extractor)**
- 从各种格式文件中提取可分析内容
- 处理图像预处理、文本提取、元数据读取
- 支持压缩包内容递归分析

### 🤖 智能处理引擎

**5. 分类引擎 (classification_engine)**
- 基于AI分析结果自动生成分类策略
- 支持多级目录结构生成
- 处理中英文文件夹命名

**6. 文件操作模块 (file_operations)**
- 实现复制/移动两种操作模式
- 提供操作撤销功能
- 确保文件操作的安全性和完整性

**7. 智能重命名引擎 (rename_engine)**
- 基于文件内容生成描述性文件名
- 支持批量重命名预览
- 处理文件名冲突和特殊字符

### 🖥️ 用户界面层

**8. PyWebView基础框架 (web_ui_foundation)**
- 搭建基于 `pywebview` 的桌面应用框架
- 设计现代化的HTML/CSS/JS界面结构
- 实现Python后端与前端的通信桥梁

**9. 主界面 (main_interface)**
- 文件/文件夹选择器
- 实时处理进度显示
- 处理结果预览和确认

**10. 设置界面 (settings_interface)**
- API配置管理界面
- 模型选择和参数调整
- 语言和操作模式切换

**11. 重命名界面 (rename_interface)**
- 专用的智能重命名功能界面
- 重命名结果预览和批量确认
- 自定义重命名规则设置

### ⚙️ 支持系统

**12. 进度管理系统 (progress_system)**
- 多线程任务队列管理
- 实时进度更新和状态同步
- 支持任务暂停和恢复

**13. 错误处理系统 (error_handling)**
- 统一的错误捕获和处理机制
- 用户友好的错误提示
- 详细的日志记录和调试信息

**14. 多语言支持 (multilingual_support)**
- 中英文界面切换
- 本地化的文件夹命名策略
- 多语言错误消息和提示

**15. 主应用程序 (main_application)**
- 整合所有模块的主程序入口
- 应用程序生命周期管理
- 系统托盘和窗口管理

### 🛠️ 技术栈选择说明

- **PyWebView**: 提供现代化的桌面应用界面，支持HTML/CSS/JS，便于快速开发美观的UI
- **OpenAI库**: 统一的API调用接口，兼容多种AI服务提供商（SiliconFlow、OpenAI、Ollama等）
- **多线程处理**: 利用配置中的 `thread_count = 8` 进行并发文件处理
- **配置驱动**: 基于现有的 `config.ini` 结构，支持灵活的功能配置