// 应用程序主逻辑
class DocStreamApp {
    constructor() {
        this.currentPage = 'file-organize';
        this.config = {};
        this.isProcessing = false;
        this.selectedFiles = [];
        this.renameFiles = [];
        this.currentRenameIndex = -1;
        this.classificationResults = null;
        
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
        
        // 扫描文件夹按钮
        document.getElementById('scanFolderBtn')?.addEventListener('click', () => {
            this.showScanOptions();
        });
        
        document.getElementById('startScanBtn')?.addEventListener('click', () => {
            this.startFolderScan();
        });
        
        // 文件管理按钮
        document.getElementById('selectAllBtn')?.addEventListener('click', () => {
            this.selectAllFiles();
        });
        
        document.getElementById('deselectAllBtn')?.addEventListener('click', () => {
            this.deselectAllFiles();
        });
        
        document.getElementById('clearFilesBtn')?.addEventListener('click', () => {
            this.clearFileList();
        });
        
        document.getElementById('startProcessingBtn')?.addEventListener('click', () => {
            this.startFileProcessing();
        });
        
        // 重命名页面按钮
        document.getElementById('selectRenameFilesBtn')?.addEventListener('click', () => {
            this.selectFilesForRename();
        });
        
        document.getElementById('selectRenameFolderBtn')?.addEventListener('click', () => {
            this.selectFolderForRename();
        });
        
        document.getElementById('generateAllNamesBtn')?.addEventListener('click', () => {
            this.generateAllAINames();
        });
        
        document.getElementById('applyAllRenamesBtn')?.addEventListener('click', () => {
            this.applyAllRenames();
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
                this.showNotification('正在选择文件...', 'info');
                
                const selectResult = await window.pywebview.api.select_files();
                if (selectResult && selectResult.success && selectResult.files.length > 0) {
                    // 获取已选择的文件信息
                    const result = await window.pywebview.api.get_selected_files();
                    if (result && result.success) {
                        this.selectedFiles = result.files || [];
                        this.displaySelectedFiles();
                        this.showNotification(`成功选择 ${this.selectedFiles.length} 个文件`, 'success');
                    } else {
                        this.showNotification('获取文件信息失败', 'error');
                    }
                } else {
                    this.showNotification(selectResult?.message || '未选择任何文件', 'warning');
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
                this.showNotification('正在选择文件夹...', 'info');
                
                const selectResult = await window.pywebview.api.select_folder();
                if (selectResult && selectResult.success && selectResult.folder) {
                    // 自动扫描文件夹
                    this.showNotification('正在扫描文件夹...', 'info');
                    
                    const recursive = document.getElementById('recursiveScan')?.checked || false;
                    const result = await window.pywebview.api.scan_folder_for_files(selectResult.folder, recursive);
                    
                    if (result && result.success) {
                        this.selectedFiles = result.files || [];
                        this.displaySelectedFiles();
                        this.showNotification(`扫描完成，找到 ${this.selectedFiles.length} 个文件`, 'success');
                    } else {
                        this.showNotification(result?.message || '扫描文件夹失败', 'error');
                    }
                } else {
                    this.showNotification(selectResult?.message || '未选择文件夹', 'warning');
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
        
        // 若包含分类结果标记，自动弹出确认面板
        if (progress.classification_results && !this.classificationResults) {
            // 主动向后端取一次详细结果
            window.pywebview.api.get_classification_results(progress.task_id)
                .then(res => {
                    if (res && res.success) {
                        this.handleClassificationReady({task_id: progress.task_id, results: res.results});
                    }
                })
                .catch(console.error);
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
    
    // ==================== 新增功能方法 ====================
    
    // 显示扫描选项
    showScanOptions() {
        const scanOptions = document.getElementById('scanOptions');
        scanOptions.style.display = scanOptions.style.display === 'none' ? 'block' : 'none';
    }
    
    // 开始文件夹扫描
    async startFolderScan() {
        try {
            // 先选择文件夹
            const selectResult = await window.pywebview.api.select_folder();
            if (!selectResult || !selectResult.success || !selectResult.folder) {
                this.showNotification(selectResult?.message || '未选择文件夹', 'warning');
                return;
            }
            
            const recursive = document.getElementById('recursiveScan').checked;
            const fileTypeFilter = document.getElementById('fileTypeFilter').value;
            
            this.showNotification('正在扫描文件夹...', 'info');
            
            if (window.pywebview && window.pywebview.api) {
                const result = await window.pywebview.api.scan_folder_for_files(selectResult.folder, recursive);
                if (result && result.success) {
                    this.selectedFiles = result.files || [];
                    this.displaySelectedFiles();
                    this.showNotification(`扫描完成，找到 ${this.selectedFiles.length} 个文件`, 'success');
                } else {
                    this.showNotification(result?.message || '扫描失败', 'error');
                }
            }
        } catch (error) {
            console.error('扫描文件夹失败:', error);
            this.showNotification('扫描文件夹失败', 'error');
        }
    }
    
    // 显示选择的文件
    displaySelectedFiles() {
        const fileDisplayArea = document.getElementById('fileDisplayArea');
        const selectedFilesList = document.getElementById('selectedFilesList');
        const fileCount = document.getElementById('fileCount');
        const totalSize = document.getElementById('totalSize');
        
        if (this.selectedFiles.length === 0) {
            fileDisplayArea.style.display = 'none';
            return;
        }
        
        // 计算总大小
        const totalBytes = this.selectedFiles.reduce((sum, file) => sum + (file.size || 0), 0);
        
        // 更新统计信息
        fileCount.textContent = `已选择 ${this.selectedFiles.length} 个文件`;
        totalSize.textContent = `总大小: ${this.formatFileSize(totalBytes)}`;
        
        // 生成文件列表HTML
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.generate_file_list_html(true).then(result => {
                if (result && result.success) {
                    selectedFilesList.innerHTML = result.html;
                    this.bindFileListEvents();
                }
            });
        }
        
        fileDisplayArea.style.display = 'block';
    }
    
    // 绑定文件列表事件
    bindFileListEvents() {
        // 绑定复选框事件
        document.querySelectorAll('.file-checkbox').forEach((checkbox, index) => {
            checkbox.addEventListener('change', () => {
                this.updateFileSelection();
            });
        });
        
        // 绑定预览按钮事件
        document.querySelectorAll('.btn-preview').forEach((btn) => {
            btn.addEventListener('click', () => {
                const filePath = btn.getAttribute('onclick').match(/'([^']+)'/)[1];
                this.previewFile(filePath);
            });
        });
        
        // 绑定重命名按钮事件
        document.querySelectorAll('.btn-rename').forEach((btn) => {
            btn.addEventListener('click', () => {
                const match = btn.getAttribute('onclick').match(/renameFile\((\d+)\)/);
                if (match) {
                    this.showRenameDialog(parseInt(match[1]));
                }
            });
        });
        
        // 绑定移除按钮事件
        document.querySelectorAll('.btn-remove').forEach((btn) => {
            btn.addEventListener('click', () => {
                const match = btn.getAttribute('onclick').match(/removeFile\((\d+)\)/);
                if (match) {
                    this.removeFile(parseInt(match[1]));
                }
            });
        });
    }
    
    // 格式化文件大小
    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    // 更新文件选择状态
    updateFileSelection() {
        const checkboxes = document.querySelectorAll('.file-checkbox');
        const selectedCount = Array.from(checkboxes).filter(cb => cb.checked).length;
        
        document.getElementById('fileCount').textContent = `已选择 ${selectedCount} 个文件`;
    }
    
    // 全选文件
    selectAllFiles() {
        document.querySelectorAll('.file-checkbox').forEach(checkbox => {
            checkbox.checked = true;
        });
        this.updateFileSelection();
    }
    
    // 取消全选
    deselectAllFiles() {
        document.querySelectorAll('.file-checkbox').forEach(checkbox => {
            checkbox.checked = false;
        });
        this.updateFileSelection();
    }
    
    // 清空文件列表
    async clearFileList() {
        if (confirm('确定要清空文件列表吗？')) {
            this.selectedFiles = [];
            document.getElementById('fileDisplayArea').style.display = 'none';
            
            // 清除分类结果
            this.clearClassificationResults();
            
            if (window.pywebview && window.pywebview.api) {
                await window.pywebview.api.clear_file_list();
            }
            
            this.showNotification('文件列表已清空', 'success');
        }
    }
    
    // 开始文件处理
    async startFileProcessing() {
        const selectedPaths = this.getSelectedFilePaths();
        if (selectedPaths.length === 0) {
            this.showNotification('请先选择要处理的文件', 'warning');
            return;
        }
        
        // 清除之前的分类结果
        this.clearClassificationResults();
        
        await this.startProcessing(selectedPaths);
    }
    
    // 获取选中的文件路径
    getSelectedFilePaths() {
        const checkboxes = document.querySelectorAll('.file-checkbox:checked');
        return Array.from(checkboxes).map(checkbox => {
            return checkbox.closest('.file-item').dataset.path;
        });
    }
    
    // 移除文件
    async removeFile(index) {
        if (window.pywebview && window.pywebview.api) {
            const result = await window.pywebview.api.remove_file_from_list(index);
            if (result && result.success) {
                this.selectedFiles.splice(index, 1);
                this.displaySelectedFiles();
                this.showNotification(result.message, 'success');
            }
        }
    }
    
    // 预览文件
    async previewFile(filePath) {
        try {
            if (window.pywebview && window.pywebview.api) {
                const result = await window.pywebview.api.preview_file(filePath);
                if (result && result.success) {
                    this.showPreviewDialog(result.preview);
                } else {
                    this.showNotification('预览失败', 'error');
                }
            }
        } catch (error) {
            console.error('预览文件失败:', error);
            this.showNotification('预览文件失败', 'error');
        }
    }
    
    // 显示预览对话框
    showPreviewDialog(preview) {
        const dialog = document.getElementById('previewDialog');
        const content = document.getElementById('previewDialogContent');
        
        let html = '<div class="preview-content">';
        
        // 如果是图片，显示缩略图
        if (preview.type === 'images' && preview.thumbnail) {
            html += `<img src="file://${preview.thumbnail}" class="preview-image" alt="预览图">`;
        }
        
        // 文件信息
        html += '<div class="preview-info">';
        html += '<h4>文件信息</h4>';
        html += '<div class="preview-details">';
        html += `<span class="preview-label">文件名:</span><span class="preview-value">${preview.name}</span>`;
        html += `<span class="preview-label">大小:</span><span class="preview-value">${preview.size}</span>`;
        html += `<span class="preview-label">类型:</span><span class="preview-value">${preview.type.toUpperCase()}</span>`;
        html += `<span class="preview-label">路径:</span><span class="preview-value">${preview.path}</span>`;
        html += '</div>';
        html += '</div>';
        
        // 内容预览
        if (preview.content_preview) {
            html += '<div class="content-preview">';
            html += preview.content_preview;
            html += '</div>';
        }
        
        html += '</div>';
        
        content.innerHTML = html;
        dialog.style.display = 'flex';
    }
    
    // ==================== 重命名功能 ====================
    
    // 选择重命名文件
    async selectFilesForRename() {
        try {
            if (window.pywebview && window.pywebview.api) {
                this.showNotification('正在选择文件...', 'info');
                
                const selectResult = await window.pywebview.api.select_files();
                if (selectResult && selectResult.success && selectResult.files.length > 0) {
                    // 获取详细文件信息
                    const result = await window.pywebview.api.get_selected_files();
                    if (result && result.success) {
                        this.renameFiles = result.files.map(file => ({
                            path: file.path,
                            name: file.name,
                            newName: ''
                        }));
                        this.displayRenameFiles();
                        this.showNotification(`成功选择 ${this.renameFiles.length} 个文件`, 'success');
                    } else {
                        this.showNotification('获取文件信息失败', 'error');
                    }
                } else {
                    this.showNotification(selectResult?.message || '未选择任何文件', 'warning');
                }
            }
        } catch (error) {
            console.error('选择文件失败:', error);
            this.showNotification('选择文件失败', 'error');
        }
    }
    
    // 选择重命名文件夹
    async selectFolderForRename() {
        try {
            if (window.pywebview && window.pywebview.api) {
                this.showNotification('正在选择文件夹...', 'info');
                
                const selectResult = await window.pywebview.api.select_folder();
                if (selectResult && selectResult.success && selectResult.folder) {
                    this.showNotification('正在扫描文件夹...', 'info');
                    
                    const result = await window.pywebview.api.scan_folder_for_files(selectResult.folder, false);
                    if (result && result.success) {
                        this.renameFiles = result.files.map(file => ({
                            path: file.path,
                            name: file.name,
                            newName: ''
                        }));
                        this.displayRenameFiles();
                        this.showNotification(`扫描完成，找到 ${this.renameFiles.length} 个文件`, 'success');
                    } else {
                        this.showNotification(result?.message || '扫描文件夹失败', 'error');
                    }
                } else {
                    this.showNotification(selectResult?.message || '未选择文件夹', 'warning');
                }
            }
        } catch (error) {
            console.error('选择文件夹失败:', error);
            this.showNotification('选择文件夹失败', 'error');
        }
    }
    
    // 显示重命名文件列表
    displayRenameFiles() {
        const renameDisplayArea = document.getElementById('renameDisplayArea');
        const renameFilesList = document.getElementById('renameFilesList');
        const renameFileCount = document.getElementById('renameFileCount');
        
        if (this.renameFiles.length === 0) {
            renameDisplayArea.style.display = 'none';
            return;
        }
        
        renameFileCount.textContent = `已选择 ${this.renameFiles.length} 个文件`;
        
        // 生成重命名列表HTML
        let html = '';
        this.renameFiles.forEach((file, index) => {
            const fileName = file.name || file.path.split('/').pop().split('\\').pop();
            
            html += `
                <div class="rename-item" data-index="${index}">
                    <div class="file-icon">📄</div>
                    <div class="rename-item-info">
                        <div class="current-name">${fileName}</div>
                        <div class="new-name ${file.newName ? '' : 'empty'}">
                            ${file.newName || '未设置新名称'}
                        </div>
                    </div>
                    <div class="rename-item-actions">
                        <button class="btn btn-outline" onclick="window.app.showRenameDialog(${index})">重命名</button>
                        <button class="btn btn-secondary" onclick="window.app.generateAIName(${index})">AI建议</button>
                        <button class="btn btn-preview" onclick="window.app.previewFile('${file.path}')">预览</button>
                    </div>
                </div>
            `;
        });
        
        renameFilesList.innerHTML = html;
        renameDisplayArea.style.display = 'block';
    }
    
    // 显示重命名对话框
    async showRenameDialog(index) {
        this.currentRenameIndex = index;
        
        try {
            if (window.pywebview && window.pywebview.api) {
                const result = await window.pywebview.api.get_rename_dialog_html(index);
                if (result && result.success) {
                    const dialog = document.getElementById('renameDialog');
                    const content = document.getElementById('renameDialogContent');
                    content.innerHTML = result.html;
                    dialog.style.display = 'flex';
                }
            }
        } catch (error) {
            console.error('显示重命名对话框失败:', error);
            this.showNotification('显示重命名对话框失败', 'error');
        }
    }
    
    // 生成AI文件名建议
    async generateAIName(index) {
        try {
            this.showNotification('正在生成AI建议...', 'info');
            
            if (window.pywebview && window.pywebview.api) {
                const result = await window.pywebview.api.generate_ai_filename_suggestions(index);
                if (result && result.success) {
                    // 重新显示对话框，包含建议
                    this.currentRenameIndex = index;
                    const dialogResult = await window.pywebview.api.get_rename_dialog_html(index, result.suggestions);
                    if (dialogResult && dialogResult.success) {
                        const dialog = document.getElementById('renameDialog');
                        const content = document.getElementById('renameDialogContent');
                        content.innerHTML = dialogResult.html;
                        dialog.style.display = 'flex';
                    }
                    this.showNotification('AI建议生成完成', 'success');
                } else {
                    this.showNotification(result.message || 'AI建议生成失败', 'error');
                }
            }
        } catch (error) {
            console.error('生成AI建议失败:', error);
            this.showNotification('生成AI建议失败', 'error');
        }
    }
    
    // 批量生成AI名称
    async generateAllAINames() {
        if (this.renameFiles.length === 0) {
            this.showNotification('请先选择要重命名的文件', 'warning');
            return;
        }
        
        this.showNotification('正在批量生成AI建议...', 'info');
        
        // 这里可以循环为每个文件生成AI建议
        // 为了演示，我们只是给每个文件设置一个示例名称
        this.renameFiles.forEach((file, index) => {
            if (!file.newName) {
                const fileName = file.name || file.path.split('/').pop().split('\\').pop();
                const nameWithoutExt = fileName.substring(0, fileName.lastIndexOf('.'));
                file.newName = `${nameWithoutExt}_AI重命名`;
            }
        });
        
        this.displayRenameFiles();
        this.showNotification('批量AI建议生成完成', 'success');
    }
    
    // 应用全部重命名
    async applyAllRenames() {
        const filesToRename = this.renameFiles.filter(file => file.newName);
        
        if (filesToRename.length === 0) {
            this.showNotification('没有需要重命名的文件', 'warning');
            return;
        }
        
        if (!confirm(`确定要重命名 ${filesToRename.length} 个文件吗？`)) {
            return;
        }
        
        this.showNotification('正在执行重命名...', 'info');
        
        // 显示进度面板
        const progressPanel = document.getElementById('renameProgressPanel');
        progressPanel.style.display = 'block';
        
        let successCount = 0;
        let failedCount = 0;
        
        for (let i = 0; i < filesToRename.length; i++) {
            const file = filesToRename[i];
            const progress = Math.round((i / filesToRename.length) * 100);
            
            // 更新进度
            document.getElementById('renameProgressText').textContent = `正在重命名: ${file.name || file.path}`;
            document.getElementById('renameProgressPercent').textContent = `${progress}%`;
            document.getElementById('renameProgressFill').style.width = `${progress}%`;
            
            try {
                if (window.pywebview && window.pywebview.api) {
                    const result = await window.pywebview.api.rename_file(i, file.newName);
                    if (result && result.success) {
                        successCount++;
                    } else {
                        failedCount++;
                    }
                }
            } catch (error) {
                failedCount++;
            }
            
            // 添加小延迟以显示进度
            await new Promise(resolve => setTimeout(resolve, 100));
        }
        
        // 完成
        document.getElementById('renameProgressText').textContent = '重命名完成';
        document.getElementById('renameProgressPercent').textContent = '100%';
        document.getElementById('renameProgressFill').style.width = '100%';
        
        this.showNotification(`重命名完成: 成功 ${successCount} 个，失败 ${failedCount} 个`, 'success');
        
        // 3秒后隐藏进度面板
        setTimeout(() => {
            progressPanel.style.display = 'none';
        }, 3000);
    }
    
    // 处理分类结果
    handleClassificationReady(data) {
        console.log('收到分类结果', data);
        this.classificationResults = data;
        
        // 更新文件列表显示分类结果，而不是显示确认面板
        this.updateFileListWithClassification(data.results);
        
        // 显示确认整理按钮
        this.showClassificationActions();
        
        this.showNotification('AI分类已完成，请确认整理', 'info');
    }
    
    // 更新文件列表显示分类结果
    updateFileListWithClassification(results) {
        const fileItems = document.querySelectorAll('.file-item');
        
        fileItems.forEach((item) => {
            const filePath = item.dataset.path;
            if (results && results[filePath]) {
                const classification = results[filePath];
                const category = classification.category || '未知';
                const subcategory = classification.subcategory ? ` / ${classification.subcategory}` : '';
                const newPath = classification.new_path || `${category}${subcategory}`;
                
                // 查找或创建新路径显示元素
                let pathDisplay = item.querySelector('.classification-result');
                if (!pathDisplay) {
                    pathDisplay = document.createElement('div');
                    pathDisplay.className = 'classification-result';
                    
                    // 插入到文件信息之后
                    const fileInfo = item.querySelector('.file-info');
                    if (fileInfo) {
                        fileInfo.appendChild(pathDisplay);
                    }
                }
                
                pathDisplay.innerHTML = `<span class="new-path-label">新路径：</span><span class="new-path-value">${newPath}</span>`;
                
                // 添加分类完成的样式
                item.classList.add('classified');
            }
        });
    }
    
    // 显示分类操作按钮
    showClassificationActions() {
        // 在文件操作区域添加确认整理按钮
        const fileActions = document.querySelector('.file-actions');
        if (fileActions) {
            // 先移除已存在的确认按钮
            const existingBtn = fileActions.querySelector('#confirmOrganizeBtn');
            if (existingBtn) {
                existingBtn.remove();
            }
            
            // 添加新的确认整理按钮
            const confirmBtn = document.createElement('button');
            confirmBtn.id = 'confirmOrganizeBtn';
            confirmBtn.className = 'btn btn-primary';
            confirmBtn.textContent = '确认整理';
            confirmBtn.addEventListener('click', () => {
                this.confirmOrganize();
            });
            
            fileActions.appendChild(confirmBtn);
        }
    }
    
    // 处理确认整理按钮点击
    async confirmOrganize() {
        if (!this.classificationResults) {
            this.showNotification('未找到分类结果', 'warning');
            return;
        }
        const targetDir = prompt('请输入目标目录(留空则自动创建 organized):', '');
        try {
            const resp = await window.pywebview.api.confirm_organize(this.classificationResults.task_id, targetDir || null);
            if (resp && resp.success) {
                this.showNotification('文件整理完成', 'success');
                // 移除确认按钮并重置分类状态
                const confirmBtn = document.getElementById('confirmOrganizeBtn');
                if (confirmBtn) {
                    confirmBtn.remove();
                }
                // 清除分类结果显示
                this.clearClassificationResults();
            } else {
                this.showNotification(resp?.message || '文件整理失败', 'error');
            }
        } catch (e) {
            console.error(e);
            this.showNotification('文件整理失败', 'error');
        }
    }
    
    // 清除分类结果显示
    clearClassificationResults() {
        const fileItems = document.querySelectorAll('.file-item');
        fileItems.forEach((item) => {
            item.classList.remove('classified');
            const classificationResult = item.querySelector('.classification-result');
            if (classificationResult) {
                classificationResult.remove();
            }
        });
        this.classificationResults = null;
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

// 从Python后端接收分类结果准备就绪事件
window.onClassificationReady = function(data) {
    try {
        const parsed = (typeof data === 'string') ? JSON.parse(data) : data;
        if (app) {
            app.handleClassificationReady(parsed);
        }
    } catch (e) {
        console.error('处理分类结果失败', e);
    }
};

// ==================== 全局辅助函数 ====================

// 关闭重命名对话框
function closeRenameDialog() {
    document.getElementById('renameDialog').style.display = 'none';
}

// 关闭预览对话框
function closePreviewDialog() {
    document.getElementById('previewDialog').style.display = 'none';
}

// 确认重命名
function confirmRename() {
    const newName = document.getElementById('new-filename').value.trim();
    if (!newName) {
        window.app.showNotification('请输入新的文件名', 'warning');
        return;
    }
    
    if (window.app.currentRenameIndex >= 0) {
        window.app.renameFiles[window.app.currentRenameIndex].newName = newName;
        window.app.displayRenameFiles();
        closeRenameDialog();
        window.app.showNotification('文件名已设置', 'success');
    }
}

// 选择建议的名称
function selectSuggestion(suggestion) {
    document.getElementById('new-filename').value = suggestion;
}

// 生成AI建议（在对话框中）
function generateAIName() {
    if (window.app.currentRenameIndex >= 0) {
        window.app.generateAIName(window.app.currentRenameIndex);
    }
}

// 重命名文件（从文件列表调用）
function renameFile(index) {
    window.app.showRenameDialog(index);
}

// 移除文件（从文件列表调用）
function removeFile(index) {
    window.app.removeFile(index);
}

// 预览文件（从文件列表调用）
function previewFile(filePath) {
    window.app.previewFile(filePath);
}