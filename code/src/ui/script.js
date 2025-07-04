// 应用程序主逻辑
class DocStreamApp {
    constructor() {
        this.currentPage = 'file-organize';
        this.config = {};
        this.isProcessing = false;
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.loadConfig();
        this.updateUI();
    }
    
    // 设置事件监听器
    setupEventListeners() {
        // 导航点击事件
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', async (e) => {
                e.preventDefault();
                const page = item.dataset.page;
                await this.switchPage(page);
            });
        });
        
        // 文件选择按钮
        document.getElementById('selectFilesBtn')?.addEventListener('click', () => {
            this.selectFiles();
        });
        
        document.getElementById('selectFolderBtn')?.addEventListener('click', () => {
            this.selectFolder();
        });
        
        // 设置表单提交
        document.getElementById('settingsForm')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveSettings();
        });
        
        // 重置按钮
        document.getElementById('resetBtn')?.addEventListener('click', () => {
            this.resetSettings();
        });
        
        // 文件拖拽处理
        this.setupFileDragDrop();
        
        // 处理按钮事件
        document.getElementById('pauseBtn')?.addEventListener('click', () => {
            this.pauseProcessing();
        });
        
        document.getElementById('cancelBtn')?.addEventListener('click', () => {
            this.cancelProcessing();
        });
    }
    
    // 页面切换
    async switchPage(pageId) {
        // 移除当前活动状态
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
        });
        document.querySelectorAll('.page').forEach(page => {
            page.classList.remove('active');
        });
        
        // 设置新的活动状态
        document.querySelector(`[data-page="${pageId}"]`)?.classList.add('active');
        document.getElementById(pageId)?.classList.add('active');
        
        this.currentPage = pageId;
        
        // 如果切换到设置页面，先加载配置再填充表单
        if (pageId === 'settings') {
            await this.loadConfig();
            this.loadSettingsForm();
        }
    }
    
    // 加载配置
    async loadConfig() {
        try {
            if (window.pywebview && window.pywebview.api) {
                this.config = await window.pywebview.api.get_config();
                console.log('配置加载成功:', this.config);
            }
        } catch (error) {
            console.error('加载配置失败:', error);
            this.showNotification('加载配置失败', 'error');
        }
    }
    
    // 加载设置表单
    loadSettingsForm() {
        const form = document.getElementById('settingsForm');
        if (!form) {
            console.error('设置表单未找到');
            return;
        }
        
        if (!this.config) {
            console.error('配置数据为空，无法填充表单');
            return;
        }
        
        console.log('开始填充设置表单:', this.config);
        
        // 填充API配置
        const apiConfig = this.config.API || {};
        document.getElementById('apiKey').value = apiConfig.api_key || '';
        document.getElementById('apiUrl').value = apiConfig.api_url || 'https://api.siliconflow.cn/v1';
        document.getElementById('apiType').value = apiConfig.api_type || 'OpenAI API';
        
        // 填充基本设置
        const settings = this.config.Settings || {};
        document.getElementById('language').value = settings.language || 'CN';
        document.getElementById('fileOperation').value = settings.file_operation || 'copy';
        document.getElementById('threadCount').value = settings.thread_count || '8';
        
        // 填充AI模型配置
        document.getElementById('imageAnalysisModel').value = settings.image_analysis_model || 'Pro/Qwen/Qwen2-VL-7B-Instruct';
        document.getElementById('fileAnalysisModel').value = settings.file_analysis_model || 'Pro/deepseek-ai/DeepSeek-R1-Distill-Qwen-7B';
        document.getElementById('decisionModel').value = settings.decision_model || 'deepseek-ai/DeepSeek-R1-Distill-Qwen-32B';
        document.getElementById('enableVideoAnalysis').checked = settings.enable_video_analysis === 'true';
        document.getElementById('videoAnalysisModel').value = settings.video_analysis_model || 'Pro/Qwen/Qwen2-VL-7B-Instruct';
        
        // 填充日志配置
        const loggingConfig = this.config.Logging || {};
        document.getElementById('logLevel').value = loggingConfig.log_level || 'INFO';
        document.getElementById('consoleLogLevel').value = loggingConfig.console_log_level || 'WARNING';
        document.getElementById('logToFile').checked = loggingConfig.log_to_file === 'true';
        document.getElementById('logToConsole').checked = loggingConfig.log_to_console === 'true';
        document.getElementById('logFormat').value = loggingConfig.log_format || 'detailed';
        document.getElementById('logFileSize').value = loggingConfig.log_file_size || '10';
        document.getElementById('logFileCount').value = loggingConfig.log_file_count || '5';
        document.getElementById('logDir').value = loggingConfig.log_dir || 'logs';
        
        console.log('设置表单填充完成');
    }
    
    // 保存设置
    async saveSettings() {
        try {
            const formData = new FormData(document.getElementById('settingsForm'));
            const config = {
                API: {
                    api_key: formData.get('api_key'),
                    api_url: formData.get('api_url'),
                    api_type: formData.get('api_type')
                },
                Settings: {
                    language: formData.get('language'),
                    file_operation: formData.get('file_operation'),
                    image_analysis_model: formData.get('image_analysis_model'),
                    file_analysis_model: formData.get('file_analysis_model'),
                    decision_model: formData.get('decision_model'),
                    enable_video_analysis: formData.get('enable_video_analysis') ? 'true' : 'false',
                    video_analysis_model: formData.get('video_analysis_model'),
                    thread_count: formData.get('thread_count'),
                    subfolder_mode: 'whole'
                },
                Logging: {
                    log_level: formData.get('log_level'),
                    console_log_level: formData.get('console_log_level'),
                    log_to_file: formData.get('log_to_file') ? 'true' : 'false',
                    log_to_console: formData.get('log_to_console') ? 'true' : 'false',
                    log_format: formData.get('log_format'),
                    log_file_size: formData.get('log_file_size'),
                    log_file_count: formData.get('log_file_count'),
                    log_dir: formData.get('log_dir')
                }
            };
            
            if (window.pywebview && window.pywebview.api) {
                const result = await window.pywebview.api.save_config(config);
                if (result && result.success) {
                    this.config = config;
                    this.showNotification(result.message || '设置保存成功', 'success');
                } else {
                    this.showNotification(result.message || '设置保存失败', 'error');
                }
            }
        } catch (error) {
            console.error('保存设置失败:', error);
            this.showNotification('保存设置失败', 'error');
        }
    }
    
    // 重置设置
    resetSettings() {
        if (confirm('确定要重置所有设置吗？')) {
            document.getElementById('settingsForm').reset();
            this.showNotification('设置已重置', 'success');
        }
    }
    
    // 选择文件
    async selectFiles() {
        try {
            if (window.pywebview && window.pywebview.api) {
                const files = await window.pywebview.api.select_files();
                if (files && files.length > 0) {
                    this.startProcessing(files);
                }
            }
        } catch (error) {
            console.error('选择文件失败:', error);
            this.showNotification('选择文件失败', 'error');
        }
    }
    
    // 选择文件夹
    async selectFolder() {
        try {
            if (window.pywebview && window.pywebview.api) {
                const folder = await window.pywebview.api.select_folder();
                if (folder) {
                    this.startProcessing([folder]);
                }
            }
        } catch (error) {
            console.error('选择文件夹失败:', error);
            this.showNotification('选择文件夹失败', 'error');
        }
    }
    
    // 设置文件拖拽功能
    setupFileDragDrop() {
        const uploadArea = document.getElementById('uploadArea');
        if (!uploadArea) return;
        
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });
        
        uploadArea.addEventListener('dragleave', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
        });
        
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            
            const files = Array.from(e.dataTransfer.files);
            if (files.length > 0) {
                this.startProcessing(files.map(f => f.path || f.name));
            }
        });
    }
    
    // 开始处理文件
    async startProcessing(files) {
        this.isProcessing = true;
        
        // 显示处理面板
        document.getElementById('uploadArea').style.display = 'none';
        document.getElementById('processingPanel').style.display = 'block';
        
        try {
            if (window.pywebview && window.pywebview.api) {
                const result = await window.pywebview.api.start_processing(files);
                if (!result || !result.success) {
                    this.showNotification(result?.message || '处理启动失败', 'error');
                    this.resetProcessingUI();
                }
            }
        } catch (error) {
            console.error('处理文件失败:', error);
            this.showNotification('处理文件失败', 'error');
            this.resetProcessingUI();
        }
    }
    
    // 暂停处理
    async pauseProcessing() {
        try {
            if (window.pywebview && window.pywebview.api) {
                const result = await window.pywebview.api.pause_processing();
                if (result && result.success) {
                    this.showNotification(result.message || '处理已暂停', 'warning');
                } else {
                    this.showNotification(result?.message || '暂停失败', 'error');
                }
            }
        } catch (error) {
            console.error('暂停处理失败:', error);
        }
    }
    
    // 取消处理
    async cancelProcessing() {
        if (confirm('确定要取消当前处理吗？')) {
            try {
                if (window.pywebview && window.pywebview.api) {
                    const result = await window.pywebview.api.cancel_processing();
                    this.resetProcessingUI();
                    if (result && result.success) {
                        this.showNotification(result.message || '处理已取消', 'warning');
                    } else {
                        this.showNotification(result?.message || '取消失败', 'error');
                    }
                }
            } catch (error) {
                console.error('取消处理失败:', error);
            }
        }
    }
    
    // 恢复处理
    async resumeProcessing() {
        try {
            if (window.pywebview && window.pywebview.api) {
                const result = await window.pywebview.api.resume_processing();
                if (result && result.success) {
                    this.showNotification(result.message || '处理已恢复', 'info');
                } else {
                    this.showNotification(result?.message || '恢复失败', 'error');
                }
            }
        } catch (error) {
            console.error('恢复处理失败:', error);
        }
    }
    
    // 获取任务状态
    async getTaskStatus() {
        try {
            if (window.pywebview && window.pywebview.api) {
                const result = await window.pywebview.api.get_task_status();
                if (result && result.success) {
                    return result.task;
                } else {
                    console.log('没有活跃的任务');
                    return null;
                }
            }
        } catch (error) {
            console.error('获取任务状态失败:', error);
            return null;
        }
    }
    
    // 获取进度统计
    async getProgressStatistics() {
        try {
            if (window.pywebview && window.pywebview.api) {
                const result = await window.pywebview.api.get_progress_statistics();
                if (result && result.success) {
                    return result.statistics;
                } else {
                    console.error('获取统计信息失败:', result?.message);
                    return null;
                }
            }
        } catch (error) {
            console.error('获取统计信息失败:', error);
            return null;
        }
    }
    
    // 重置处理界面
    resetProcessingUI() {
        this.isProcessing = false;
        document.getElementById('uploadArea').style.display = 'block';
        document.getElementById('processingPanel').style.display = 'none';
        document.getElementById('progressFill').style.width = '0%';
        document.getElementById('progressText').textContent = '准备中...';
        document.getElementById('progressPercent').textContent = '0%';
        document.getElementById('fileList').innerHTML = '';
    }
    
    // 更新处理进度
    updateProgress(progress) {
        // 更新进度条
        const percentage = Math.round(progress.percentage);
        document.getElementById('progressFill').style.width = `${percentage}%`;
        document.getElementById('progressPercent').textContent = `${percentage}%`;
        
        // 更新进度文本
        document.getElementById('progressText').textContent = progress.text || '处理中...';
        
        // 更新文件列表
        if (progress.files && progress.files.length > 0) {
            const fileListHtml = progress.files.map(file => {
                let statusIcon = '';
                let statusText = '';
                
                switch (file.status) {
                    case 'completed':
                        statusIcon = '✓';
                        statusText = '已完成';
                        break;
                    case 'failed':
                        statusIcon = '✗';
                        statusText = `失败: ${file.error || '未知错误'}`;
                        break;
                    case 'pending':
                        statusIcon = '⏳';
                        statusText = '等待中';
                        break;
                    default:
                        statusIcon = '⏳';
                        statusText = file.status;
                }
                
                return `
                    <div class="file-item ${file.status}" title="${file.path || file.name}">
                        <span class="file-icon">${statusIcon}</span>
                        <span class="file-name">${file.name}</span>
                        <span class="file-status">${statusText}</span>
                    </div>
                `;
            }).join('');
            
            document.getElementById('fileList').innerHTML = fileListHtml;
        }
        
        // 检查是否完成
        if (progress.completed || progress.percentage >= 100) {
            this.isProcessing = false;
            // 不在这里显示通知，因为会由状态回调处理
        }
        
        // 存储当前任务ID（如果有）
        if (progress.task_id) {
            this.currentTaskId = progress.task_id;
        }
    }
    
    // 显示通知
    showNotification(message, type = 'info') {
        const notification = document.getElementById('notification');
        notification.textContent = message;
        notification.className = `notification ${type}`;
        notification.classList.add('show');
        
        setTimeout(() => {
            notification.classList.remove('show');
        }, 3000);
    }
    
    // 更新UI
    updateUI() {
        // 根据配置更新界面语言等
        if (this.config && this.config.Settings) {
            const language = this.config.Settings.language;
            if (language === 'EN') {
                this.switchToEnglish();
            }
        }
    }
    
    // 切换到英文界面
    switchToEnglish() {
        // 这里可以添加国际化逻辑
        console.log('Switching to English...');
    }
}

// 密码显示/隐藏切换
function togglePasswordVisibility(inputId) {
    const input = document.getElementById(inputId);
    const button = input.nextElementSibling;
    
    if (input.type === 'password') {
        input.type = 'text';
        button.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                <path d="M17.94 17.94C16.2306 19.243 14.1491 19.9649 12 20C5 20 1 12 1 12C2.24389 9.68192 3.96914 7.65663 6.06 6.06M9.9 4.24C10.5883 4.0789 11.2931 3.99836 12 4C19 4 23 12 23 12C22.393 13.1356 21.6691 14.2048 20.84 15.19M14.12 14.12C13.8454 14.4148 13.5141 14.6512 13.1462 14.8151C12.7782 14.9791 12.3809 15.0673 11.9781 15.0744C11.5753 15.0815 11.1752 15.0074 10.8016 14.8565C10.4281 14.7056 10.0887 14.4811 9.80385 14.1962C9.51900 13.9113 9.29439 13.5719 9.14351 13.1984C8.99262 12.8248 8.91853 12.4247 8.92563 12.0219C8.93274 11.6191 9.02091 11.2218 9.18488 10.8538C9.34884 10.4858 9.58525 10.1546 9.88 9.88" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M1 1L23 23" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
        `;
    } else {
        input.type = 'password';
        button.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                <path d="M1 12S5 4 12 4S23 12 23 12S19 20 12 20S1 12 1 12Z" stroke="currentColor" stroke-width="2"/>
                <circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="2"/>
            </svg>
        `;
    }
}

// 窗口控制函数
function minimizeWindow() {
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.minimize_window().catch(console.error);
    }
}

function toggleMaximize() {
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.toggle_maximize().catch(console.error);
    }
}

function closeWindow() {
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.close_window().catch(console.error);
    }
}

// 全局应用实例
let app;

// 等待页面加载完成后初始化应用
document.addEventListener('DOMContentLoaded', function() {
    app = new DocStreamApp();
    
    // 等待pywebview API准备就绪
    function waitForPywebview() {
        if (window.pywebview) {
            window.pywebview.api.ready.then(() => {
                console.log('PyWebView API 准备就绪');
                app.loadConfig();
            });
        } else {
            setTimeout(waitForPywebview, 100);
        }
    }
    
    waitForPywebview();
});

// 从Python后端接收进度更新
window.updateProgress = function(progress) {
    if (app) {
        app.updateProgress(progress);
    }
};

// 从Python后端接收通知
window.showNotification = function(message, type) {
    if (app) {
        app.showNotification(message, type);
    }
}; 