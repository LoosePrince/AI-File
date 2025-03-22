from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
                           QFrame, QLineEdit, QComboBox, QFormLayout, QTextEdit, QMessageBox,
                           QSlider, QScrollArea, QGroupBox, QButtonGroup, QRadioButton, QListWidget,
                           QListWidgetItem, QFileDialog, QApplication, QProgressBar)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QMutex
from PyQt5.QtGui import QFont
import configparser
import os
from file_organizer import FileOrganizer
import json
import re
import openai

class BasePage(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(20)
        self.init_ui()
        
    def init_ui(self):
        # 创建标题容器
        title_container = QFrame()
        title_container.setStyleSheet("background: transparent; border: none;")
        title_layout = QVBoxLayout(title_container)
        title_layout.setSpacing(5)
        title_layout.setContentsMargins(0, 0, 0, 20)
        
        # 标题
        header_layout = QHBoxLayout()
        header_layout.setAlignment(Qt.AlignCenter)
        self.title = QLabel(self.get_title())
        self.title.setFont(QFont("Microsoft YaHei UI", 24, QFont.Bold))
        self.title.setStyleSheet("color: #4CAF50; border: none;")
        header_layout.addWidget(self.title)
        
        title_layout.addLayout(header_layout)
        
        # 子标题
        subtitle = QLabel(self.get_subtitle())
        subtitle.setStyleSheet("color: #aaaaaa; font-size: 9pt; border: none; background: transparent;")
        subtitle.setFont(QFont("Microsoft YaHei UI", 9))
        title_layout.addWidget(subtitle)
        
        self.layout.addWidget(title_container)
        
        # 添加内容
        content = QFrame()
        content.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border-radius: 8px;
            }
        """)
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setSpacing(15)
        self.content_layout.setContentsMargins(20, 20, 20, 20)
        
        self.setup_content(self.content_layout)
        
        self.layout.addWidget(content)
        self.layout.addStretch()
    
    def get_title(self):
        return "页面标题"
        
    def get_subtitle(self):
        return "页面描述"
        
    def setup_content(self, layout):
        pass

class RenameWorker(QThread):
    """重命名工作线程"""
    progress = pyqtSignal(dict)  # 发送进度信息
    finished = pyqtSignal()      # 完成信号
    error = pyqtSignal(str)      # 错误信号
    
    def __init__(self, file_organizer, files, language="中文", force_reanalyze=False):
        super().__init__()
        self.file_organizer = file_organizer
        self.files = files
        self.language = language
        self.force_reanalyze = force_reanalyze
        self.is_running = True
        
    def run(self):
        try:
            for file_path in self.files:
                if not self.is_running:
                    break
                    
                try:
                    # 如果需要强制重新分析，从缓存中删除该文件的记录
                    if self.force_reanalyze:
                        # 记录重新分析的信息
                        self.file_organizer.logger.log_info(f"强制重新分析文件：{file_path}")
                        # 计算文件的MD5，从缓存中删除
                        file_md5 = self.file_organizer._calculate_md5(file_path)
                        if file_md5 in self.file_organizer.analysis_cache:
                            del self.file_organizer.analysis_cache[file_md5]
                            # 保存更新后的缓存
                            self.file_organizer._save_analysis_cache()
                    
                    # 分析文件
                    analysis_result = self.file_organizer._analyze_file(file_path)
                    
                    if not analysis_result:
                        raise Exception("文件分析失败")
                        
                    # 记录分析结果
                    self.file_organizer.logger.log_info(f"文件分析结果：{json.dumps(analysis_result, ensure_ascii=False)}")
                    
                    # 生成新文件名
                    old_name = os.path.basename(file_path)
                    new_name = self.generate_new_filename(analysis_result, old_name)
                    
                    # 发送进度信息
                    self.progress.emit({
                        'file_path': file_path,
                        'new_name': new_name,
                        'status': 'success'
                    })
                    
                except Exception as e:
                    self.file_organizer.logger.log_error(f"处理文件失败：{str(e)}")
                    self.progress.emit({
                        'file_path': file_path,
                        'error': str(e),
                        'status': 'error'
                    })
                    
            self.finished.emit()
            
        except Exception as e:
            self.error.emit(str(e))
            
    def generate_new_filename(self, analysis_result, old_name):
        """根据分析结果生成新的文件名"""
        try:
            # 调用 API 生成新文件名
            response = openai.ChatCompletion.create(
                model=self.file_organizer.decision_model,
                messages=[
                    {"role": "user", "content": f"""请根据以下文件信息生成一个合适的文件名。文件名要简洁明了，能反映文件内容。不需要包含文件扩展名，我将自动添加原始文件的扩展名。文件名要符合操作系统命名规范（不能包含特殊字符）。
文件信息：
{json.dumps(analysis_result, ensure_ascii=False, indent=2)}

原文件名：{old_name}，新文件名使用{self.language}命名
"""
                    },{
                        "role": "user",
                        "content": """
请严格按照以下JSON格式输出（注意：不要输出多余的内容，只输出json，不要使用代码块包裹）：
{
    "new_name": "新文件名（不要包含扩展名）",
    "reason": "重命名原因"
}"""
                    },
                ]
            )
            
            # 获取生成的结果
            result_text = response.choices[0].message.content.strip()
            if result_text.startswith("```json") and result_text.endswith("```"):
                result_text = result_text[7:-3].strip()
            
            # 记录 AI 返回的结果
            self.file_organizer.logger.log_info(f"AI 返回结果：{result_text}")
            
            try:
                # 尝试解析 JSON
                result = json.loads(result_text)
                new_name = result.get('new_name', '')
                reason = result.get('reason', '')
                
                # 如果没有获取到新名称，使用原文件名（不含扩展名）
                if not new_name:
                    new_name = os.path.splitext(old_name)[0]
                    
                # 确保文件名合法
                new_name = self._sanitize_filename(new_name)
                
                # 移除新文件名中可能包含的扩展名
                new_name = os.path.splitext(new_name)[0]
                
                # 获取原文件扩展名并添加
                old_ext = os.path.splitext(old_name)[1]
                new_name += old_ext
                
                return new_name
                
            except json.JSONDecodeError as e:
                self.file_organizer.logger.log_error(f"解析 AI 返回的 JSON 失败：{str(e)}\n返回内容：{result_text}")
                return old_name
            
        except Exception as e:
            self.file_organizer.logger.log_error(f"生成新文件名失败：{str(e)}")
            return old_name
            
    def _sanitize_filename(self, filename):
        """清理文件名，确保符合操作系统命名规范"""
        # 替换非法字符
        illegal_chars = r'[<>:"/\\|?*]'
        filename = re.sub(illegal_chars, '_', filename)
        
        # 移除首尾空格和点
        filename = filename.strip('. ')
        
        # 如果文件名为空，使用默认名称
        if not filename:
            filename = "unnamed_file"
            
        return filename
        
    def stop(self):
        """停止处理"""
        self.is_running = False

class RenamePage(BasePage):
    def __init__(self):
        super().__init__()
        self.rename_worker = None
        self.rename_decisions = []
        self.current_file_index = -1
        self.retry_count = {}  # 记录每个文件的重试次数
        self.total_files = 0   # 总文件数
        self.processed_files = 0  # 已处理文件数
        
    def get_title(self):
        return "智能文件重命名"
        
    def get_subtitle(self):
        return "使用AI智能识别文件内容，自动生成合适的文件名"
        
    def setup_content(self, layout):
        # 创建文件列表区域
        list_group = QGroupBox("文件列表")
        list_group.setStyleSheet("""
            QGroupBox {
                color: #ffffff;
                font-family: "Microsoft YaHei UI";
                font-size: 8pt;
                border: 1px solid #444444;
                border-radius: 4px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        list_layout = QVBoxLayout(list_group)
        
        # 创建文件列表
        self.file_list = QListWidget()
        self.file_list.setStyleSheet("""
            QListWidget {
                background-color: #333333;
                color: #ffffff;
                border: 1px solid #444444;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 5px;
            }
            QListWidget::item:selected {
                background-color: #4CAF50;
                color: white;
            }
        """)
        # 添加文件列表选择变化事件
        self.file_list.currentRowChanged.connect(self.on_file_selection_changed)
        list_layout.addWidget(self.file_list)
        
        # 创建按钮区域
        button_layout = QHBoxLayout()
        
        # 添加文件按钮
        add_file_btn = QPushButton("添加文件")
        add_file_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 12px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #2d4d2f;
                color: #aaaaaa;
            }
        """)
        add_file_btn.clicked.connect(self.add_files)
        
        # 添加文件夹按钮
        add_folder_btn = QPushButton("添加文件夹")
        add_folder_btn.setStyleSheet(add_file_btn.styleSheet())
        add_folder_btn.clicked.connect(self.add_folder)
        
        # 删除选中按钮
        remove_btn = QPushButton("删除选中")
        remove_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 12px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:disabled {
                background-color: #6e2823;
                color: #aaaaaa;
            }
        """)
        remove_btn.clicked.connect(self.remove_selected)
        
        button_layout.addWidget(add_file_btn)
        button_layout.addWidget(add_folder_btn)
        button_layout.addWidget(remove_btn)
        button_layout.addStretch()
        
        list_layout.addLayout(button_layout)
        layout.addWidget(list_group)
        
        # 创建重命名预览区域
        preview_group = QGroupBox("重命名预览(可以在预览列表选择文件进行重新重命名)")
        preview_group.setStyleSheet(f"""
            {list_group.styleSheet()}
            QGroupBox {{
                font-family: "Microsoft YaHei UI";
                font-size: 8pt;
            }}
        """)
        preview_layout = QVBoxLayout(preview_group)
        
        # 创建预览列表
        self.preview_list = QListWidget()
        self.preview_list.setStyleSheet(self.file_list.styleSheet())
        # 移除双击事件连接
        # self.preview_list.itemDoubleClicked.connect(self.confirm_rename)  # 双击执行重命名
        # 添加预览列表选择变化事件
        self.preview_list.currentRowChanged.connect(self.on_preview_selection_changed)
        preview_layout.addWidget(self.preview_list)
        
        # 创建预览按钮区域
        preview_button_layout = QHBoxLayout()
        
        # 重试按钮
        self.retry_btn = QPushButton("重试")
        self.retry_btn.setStyleSheet(add_file_btn.styleSheet())
        self.retry_btn.clicked.connect(self.retry_rename)
        self.retry_btn.setEnabled(True)  # 默认启用
        
        # 确认按钮
        self.confirm_btn = QPushButton("确认重命名")
        self.confirm_btn.setStyleSheet(add_file_btn.styleSheet())
        self.confirm_btn.clicked.connect(self.confirm_rename)
        self.confirm_btn.setEnabled(True)  # 默认启用
        
        preview_button_layout.addWidget(self.retry_btn)
        preview_button_layout.addWidget(self.confirm_btn)
        preview_button_layout.addStretch()
        
        preview_layout.addLayout(preview_button_layout)
        layout.addWidget(preview_group)
        
        # 创建进度显示区域
        progress_group = QGroupBox("处理进度")
        progress_group.setStyleSheet("""
            QGroupBox {
                color: #ffffff;
                font-family: "Microsoft YaHei UI";
                font-size: 8pt;
                border: 1px solid #444444;
                border-radius: 4px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        progress_layout = QVBoxLayout(progress_group)
        
        # 创建进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #444444;
                border-radius: 4px;
                text-align: center;
                height: 20px;
                background-color: #333333;
                color: white;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                width: 10px;
                margin: 0px;
            }
        """)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        
        # 创建状态标签
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #ffffff; font-family: 'Microsoft YaHei UI'; font-size: 9pt;")
        self.status_label.setAlignment(Qt.AlignCenter)
        progress_layout.addWidget(self.status_label)
        
        # 加入主布局
        layout.addWidget(progress_group)
        
        # 创建底部按钮区域
        bottom_layout = QHBoxLayout()
        
        # 开始重命名按钮
        self.start_btn = QPushButton("开始重命名")
        self.start_btn.setStyleSheet(add_file_btn.styleSheet())
        self.start_btn.clicked.connect(self.start_rename)
        self.start_btn.setEnabled(False)
        
        # 一键重命名按钮
        self.rename_all_btn = QPushButton("一键重命名")
        self.rename_all_btn.setStyleSheet(add_file_btn.styleSheet())
        self.rename_all_btn.clicked.connect(self.confirm_all_renames)
        self.rename_all_btn.setEnabled(False)
        
        # 取消按钮
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #666666;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 12px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #555555;
            }
            QPushButton:disabled {
                background-color: #3d3d3d;
                color: #aaaaaa;
            }
        """)
        self.cancel_btn.clicked.connect(self.cancel_rename)
        self.cancel_btn.setEnabled(False)
        
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.start_btn)
        bottom_layout.addWidget(self.rename_all_btn)
        bottom_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(bottom_layout)
        
        # 初始化变量
        self.file_organizer = None
        self.rename_decisions = []
        self.current_file_index = -1
        
    def add_files(self):
        """添加文件到列表"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择文件",
            "",
            "所有文件 (*.*)"
        )
        for file in files:
            self.file_list.addItem(file)
        self.update_start_button()
        
    def add_folder(self):
        """添加文件夹到列表"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择文件夹"
        )
        if folder:
            for root, _, files in os.walk(folder):
                for file in files:
                    file_path = os.path.join(root, file)
                    self.file_list.addItem(file_path)
            self.update_start_button()
            
    def remove_selected(self):
        """从列表中删除选中的文件"""
        current_row = self.file_list.currentRow()
        if current_row >= 0:
            # 获取要删除的文件路径
            file_path = self.file_list.item(current_row).text()
            
            # 从文件列表中删除
            self.file_list.takeItem(current_row)
            
            # 从预览列表和决策中删除对应项
            for i, decision in enumerate(self.rename_decisions[:]):
                if decision['file_path'] == file_path:
                    # 从预览列表中删除
                    self.preview_list.takeItem(i)
                    # 从决策列表中删除
                    self.rename_decisions.pop(i)
                    break
            
            # 更新按钮状态
            self.update_start_button()
            self.rename_all_btn.setEnabled(len(self.rename_decisions) > 0)
            
    def update_start_button(self):
        """更新开始重命名按钮状态"""
        self.start_btn.setEnabled(self.file_list.count() > 0)
        
    def start_rename(self):
        """开始重命名过程"""
        # 初始化 FileOrganizer
        config = configparser.ConfigParser()
        config.read('config.ini', encoding='utf-8')
        api_key = config.get('API', 'api_key', fallback='')
        language = config.get('Settings', 'language', fallback='中文')
        self.file_organizer = FileOrganizer(api_key)
        
        # 确认是否清空当前预览
        if self.preview_list.count() > 0:
            reply = QMessageBox.question(self, '确认', '开始新的重命名过程将清空当前预览结果，是否继续？',
                                      QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                return
        
        # 清空预览列表
        self.preview_list.clear()
        self.rename_decisions = []
        self.retry_count = {}  # 重置重试计数
        
        # 获取所有文件路径
        files = []
        for i in range(self.file_list.count()):
            files.append(self.file_list.item(i).text())
            
        if not files:
            QMessageBox.warning(self, "警告", "请先添加要重命名的文件")
            return
            
        # 禁用按钮
        self.start_btn.setEnabled(False)
        self.retry_btn.setEnabled(False)
        self.confirm_btn.setEnabled(False)
        self.rename_all_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        
        # 重置进度
        self.total_files = len(files)
        self.processed_files = 0
        self.update_progress(0, f"准备处理 {self.total_files} 个文件...")
        
        # 创建并启动工作线程
        self.rename_worker = RenameWorker(self.file_organizer, files, language)
        self.rename_worker.progress.connect(self.handle_progress)
        self.rename_worker.finished.connect(self.handle_finished)
        self.rename_worker.error.connect(self.handle_error)
        self.rename_worker.start()
        
    def handle_progress(self, data):
        """处理进度信息"""
        if data['status'] == 'success':
            # 增加已处理文件计数
            self.processed_files += 1
            
            # 更新进度条和状态
            progress = int((self.processed_files / self.total_files) * 100)
            self.update_progress(progress, f"已处理 {self.processed_files}/{self.total_files} 个文件")
            
            # 更新或添加到预览列表
            file_path = data['file_path']
            new_name = data['new_name']
            
            # 查找是否已存在该文件的预览
            existing_index = -1
            for i, decision in enumerate(self.rename_decisions):
                if decision['file_path'] == file_path:
                    existing_index = i
                    break
            
            if existing_index >= 0:
                # 更新现有预览
                self.rename_decisions[existing_index]['new_name'] = new_name
                self.preview_list.item(existing_index).setText(
                    f"{os.path.basename(file_path)} -> {new_name}"
                )
            else:
                # 添加新预览
                self.rename_decisions.append({
                    'file_path': file_path,
                    'new_name': new_name
                })
                preview_item = QListWidgetItem(f"{os.path.basename(file_path)} -> {new_name}")
                self.preview_list.addItem(preview_item)
            
            # 确保确认按钮和一键重命名按钮启用
            self.confirm_btn.setEnabled(True)
            self.rename_all_btn.setEnabled(len(self.rename_decisions) > 0)
            
        else:
            # 处理错误情况
            self.processed_files += 1
            progress = int((self.processed_files / self.total_files) * 100)
            self.update_progress(progress, f"处理失败: {data.get('error', '未知错误')}")
            
            # 显示错误信息
            QMessageBox.warning(self, "警告", f"处理文件失败：{data['error']}")
            
    def handle_finished(self):
        """处理完成"""
        # 启用按钮
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText("取消")
        self.cancel_btn.clicked.disconnect()
        self.cancel_btn.clicked.connect(self.cancel_rename)
        
        # 确保重试和确认按钮已启用
        self.retry_btn.setEnabled(True)
        self.retry_btn.setText("重试")  # 重置按钮文本
        self.confirm_btn.setEnabled(True)
        
        # 启用一键重命名按钮（如果有结果）
        self.rename_all_btn.setEnabled(len(self.rename_decisions) > 0)
        
        # 更新进度显示为完成
        self.update_progress(100, "处理完成")
        
        # 显示完成消息
        QMessageBox.information(self, "完成", "所有文件处理完成")
        
    def handle_error(self, error_msg):
        """处理错误"""
        # 更新进度显示为错误
        self.update_progress(0, f"发生错误: {error_msg}")
        
        QMessageBox.critical(self, "错误", f"处理过程中发生错误：{error_msg}")
        self.handle_finished()
        
    def retry_rename(self):
        """重试当前预览窗口中选中的文件"""
        current_row = self.preview_list.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "请在预览窗口中选择一个文件")
            return
        
        # 获取选中的决策
        if current_row >= len(self.rename_decisions):
            QMessageBox.warning(self, "警告", "预览项与决策不匹配，请重新开始")
            return
        
        decision = self.rename_decisions[current_row]
        file_path = decision['file_path']
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "警告", f"文件不存在: {file_path}")
            return
        
        # 显示正在处理的文件
        self.preview_list.setCurrentRow(current_row)
        QApplication.processEvents()  # 确保UI更新
        
        # 增加重试计数
        self.retry_count[file_path] = self.retry_count.get(file_path, 0) + 1
        
        # 日志记录
        if self.file_organizer:
            self.file_organizer.logger.log_info(f"重试文件：{file_path}，重试次数：{self.retry_count[file_path]}")
        
        # 初始化 FileOrganizer
        config = configparser.ConfigParser()
        config.read('config.ini', encoding='utf-8')
        api_key = config.get('API', 'api_key', fallback='')
        language = config.get('Settings', 'language', fallback='中文')
        self.file_organizer = FileOrganizer(api_key)
        
        # 禁用重试按钮，防止重复点击
        self.retry_btn.setEnabled(False)
        self.retry_btn.setText("处理中...")
        QApplication.processEvents()  # 确保UI更新
        
        # 创建并启动工作线程，只处理选中的文件
        self.rename_worker = RenameWorker(self.file_organizer, [file_path], language, 
                                        force_reanalyze=self.retry_count[file_path] > 1)
        self.rename_worker.progress.connect(self.handle_progress)
        self.rename_worker.finished.connect(self.handle_finished)
        self.rename_worker.error.connect(self.handle_error)
        self.rename_worker.start()
        
    def confirm_rename(self):
        """确认当前预览窗口中选中文件的重命名"""
        current_row = self.preview_list.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "请在预览窗口中选择一个文件")
            return
        
        # 获取选中的决策
        if current_row >= len(self.rename_decisions):
            QMessageBox.warning(self, "警告", "预览项与决策不匹配，请重新开始")
            return
        
        decision = self.rename_decisions[current_row]
        old_path = decision['file_path']
        new_name = decision['new_name']
        
        # 检查文件是否存在
        if not os.path.exists(old_path):
            QMessageBox.warning(self, "警告", f"文件不存在: {old_path}")
            # 从预览和决策中移除
            self.preview_list.takeItem(current_row)
            self.rename_decisions.pop(current_row)
            return
        
        new_path = os.path.join(os.path.dirname(old_path), new_name)
        
        try:
            # 记录重命名操作
            if self.file_organizer:
                self.file_organizer.logger.log_info(f"重命名文件：{old_path} -> {new_path}")
            
            # 执行重命名
            if self.file_organizer._safe_file_operation("move", old_path, new_path):
                # 更新文件列表中的路径
                for i in range(self.file_list.count()):
                    if self.file_list.item(i).text() == old_path:
                        self.file_list.item(i).setText(new_path)
                        self.file_list.setCurrentRow(i)  # 选中该文件
                        break
                
                # 更新决策列表中的路径
                self.rename_decisions[current_row]['file_path'] = new_path
                
                # 更新预览列表（添加已重命名标记）
                old_name = os.path.basename(old_path)
                self.preview_list.item(current_row).setText(f"[已重命名] {old_name} -> {new_name}")
                
                QMessageBox.information(self, "成功", f"文件重命名成功：\n{old_name} -> {new_name}")
            else:
                QMessageBox.warning(self, "警告", "文件重命名失败")
                
        except Exception as e:
            if self.file_organizer:
                self.file_organizer.logger.log_error(f"重命名文件失败：{str(e)}")
            QMessageBox.warning(self, "错误", f"重命名文件失败：{str(e)}")
            
    def cancel_rename(self):
        """取消重命名过程"""
        if self.rename_worker and self.rename_worker.isRunning():
            self.rename_worker.stop()
            self.rename_worker.wait()
            
        # 重置状态
        self.cancel_btn.setEnabled(False)
        self.start_btn.setEnabled(True)
        
        # 重置进度条
        self.update_progress(0, "已取消")
        
        # 确定是否清空预览
        if self.preview_list.count() > 0:
            reply = QMessageBox.question(self, '确认', '是否清空当前预览结果？',
                                      QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.preview_list.clear()
                self.rename_decisions = []
                self.rename_all_btn.setEnabled(False)
        else:
            self.preview_list.clear()
            self.rename_decisions = []
            self.rename_all_btn.setEnabled(False)
        
    def confirm_all_renames(self):
        """确认所有文件的重命名"""
        # 检查是否有文件需要重命名
        if not self.rename_decisions:
            QMessageBox.warning(self, "警告", "没有可重命名的文件")
            return
        
        # 确认是否执行批量重命名
        reply = QMessageBox.question(self, '确认', f'确定要对 {len(self.rename_decisions)} 个文件执行重命名操作吗？',
                                  QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No:
            return
        
        # 准备进度显示
        total = len(self.rename_decisions)
        self.update_progress(0, f"开始重命名 {total} 个文件...")
        
        try:
            # 记录成功和失败的文件
            success_count = 0
            failed_files = []
            
            for i, decision in enumerate(self.rename_decisions):
                # 更新进度
                progress = int((i / total) * 100)
                current_file = os.path.basename(decision['file_path'])
                self.update_progress(progress, f"正在重命名 ({i+1}/{total}): {current_file}")
                
                old_path = decision['file_path']
                new_name = decision['new_name']
                new_path = os.path.join(os.path.dirname(old_path), new_name)
                
                # 跳过已经重命名的文件
                if old_path == new_path or not os.path.exists(old_path):
                    continue
                    
                # 记录重命名操作
                if self.file_organizer:
                    self.file_organizer.logger.log_info(f"批量重命名文件：{old_path} -> {new_path}")
                
                # 执行重命名
                try:
                    if self.file_organizer._safe_file_operation("move", old_path, new_path):
                        success_count += 1
                        
                        # 更新文件列表中的路径
                        for j in range(self.file_list.count()):
                            if self.file_list.item(j).text() == old_path:
                                self.file_list.item(j).setText(new_path)
                                break
                        
                        # 更新决策列表中的路径
                        for j, d in enumerate(self.rename_decisions):
                            if d['file_path'] == old_path:
                                self.rename_decisions[j]['file_path'] = new_path
                                # 更新预览列表项
                                if j < self.preview_list.count():
                                    old_name = os.path.basename(old_path)
                                    self.preview_list.item(j).setText(f"[已重命名] {old_name} -> {new_name}")
                                break
                    else:
                        failed_files.append(os.path.basename(old_path))
                except Exception as e:
                    self.file_organizer.logger.log_error(f"重命名文件失败：{str(e)}")
                    failed_files.append(os.path.basename(old_path))
            
            # 完成进度显示
            self.update_progress(100, f"完成重命名: 成功 {success_count} 个, 失败 {len(failed_files)} 个")
            
            # 显示结果
            if failed_files:
                QMessageBox.warning(self, "部分完成", 
                                  f"成功重命名 {success_count} 个文件，{len(failed_files)} 个文件失败。\n失败文件：\n" + "\n".join(failed_files))
            else:
                QMessageBox.information(self, "成功", f"成功重命名 {success_count} 个文件")
                
        except Exception as e:
            self.update_progress(0, f"重命名过程出错: {str(e)}")
            if self.file_organizer:
                self.file_organizer.logger.log_error(f"批量重命名文件失败：{str(e)}")
            QMessageBox.critical(self, "错误", f"重命名文件失败：{str(e)}")

    def on_file_selection_changed(self, current_row):
        """文件列表选择变化时更新预览列表选择"""
        if current_row < 0 or not self.rename_decisions:
            return
            
        # 获取选中的文件路径
        file_path = self.file_list.item(current_row).text()
        
        # 在决策列表中查找对应项
        for i, decision in enumerate(self.rename_decisions):
            if decision['file_path'] == file_path:
                # 如果预览列表中有此项，则选中它
                if i < self.preview_list.count():
                    self.preview_list.setCurrentRow(i)
                break
    
    def on_preview_selection_changed(self, current_row):
        """预览列表选择变化时更新文件列表选择"""
        if current_row < 0 or current_row >= len(self.rename_decisions):
            return
            
        # 获取决策中的文件路径
        file_path = self.rename_decisions[current_row]['file_path']
        
        # 在文件列表中查找对应项
        for i in range(self.file_list.count()):
            if self.file_list.item(i).text() == file_path:
                self.file_list.setCurrentRow(i)
                break

    def update_progress(self, value, status_text=None):
        """更新进度条和状态文本"""
        self.progress_bar.setValue(value)
        if status_text:
            self.status_label.setText(status_text)
        QApplication.processEvents()  # 确保UI立即更新

class SettingsPage(BasePage):
    # 添加配置更新信号
    config_updated = pyqtSignal()
    
    def get_title(self):
        return "设置"
        
    def get_subtitle(self):
        return "配置API和语言设置"
        
    def setup_content(self, layout):
        self.config = configparser.ConfigParser()
        self.load_config()
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: #2d2d2d;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #666666;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical {
                height: 0px;
            }
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        
        # 创建内容容器
        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: transparent;")
        form_layout = QFormLayout(content_widget)
        form_layout.setSpacing(15)
        
        # API设置
        api_section = QLabel("API设置")
        api_section.setFont(QFont("Microsoft YaHei UI", 14, QFont.Bold))
        api_section.setStyleSheet("color: #ffffff; border: none; background: transparent;")
        form_layout.addRow(api_section)
        
        # API URL
        self.api_url = QLineEdit()
        self.api_url.setFont(QFont("Microsoft YaHei UI", 9))
        self.api_url.setStyleSheet("""
            QLineEdit {
                background-color: #333333;
                color: #ffffff;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 8px;
            }
            QLineEdit:focus {
                border: 1px solid #4CAF50;
            }
        """)
        self.api_url.setText(self.config.get('API', 'api_url', fallback=''))
        form_layout.addRow(QLabel("API URL:", font=QFont("Microsoft YaHei UI", 9), styleSheet="color: #ffffff; border: none; background: transparent;"), self.api_url)
        
        # API Key
        self.api_key = QLineEdit()
        self.api_key.setFont(QFont("Microsoft YaHei UI", 9))
        self.api_key.setStyleSheet(self.api_url.styleSheet())
        self.api_key.setEchoMode(QLineEdit.Password)
        self.api_key.setText(self.config.get('API', 'api_key', fallback=''))
        form_layout.addRow(QLabel("API Key:", font=QFont("Microsoft YaHei UI", 9), styleSheet="color: #ffffff; border: none; background: transparent;"), self.api_key)
        
        # 基本设置
        basic_section = QLabel("基本设置")
        basic_section.setFont(QFont("Microsoft YaHei UI", 14, QFont.Bold))
        basic_section.setStyleSheet("color: #ffffff; border: none; background: transparent;")
        form_layout.addRow(basic_section)
        
        # 文件分类语言
        self.language = QComboBox()
        self.language.setFont(QFont("Microsoft YaHei UI", 9))
        self.language.setStyleSheet("""
            QComboBox {
                background-color: #333333;
                color: #ffffff;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 8px;
            }
            QComboBox:hover {
                border: 1px solid #4CAF50;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: url(down_arrow.png);
                width: 12px;
                height: 12px;
            }
        """)
        self.language.addItems(["中文", "English"])
        current_lang = self.config.get('Settings', 'language', fallback='中文')
        index = self.language.findText(current_lang)
        if index >= 0:
            self.language.setCurrentIndex(index)
        form_layout.addRow(QLabel("文件分类语言:", font=QFont("Microsoft YaHei UI", 9), styleSheet="color: #ffffff; border: none; background: transparent;"), self.language)
        
        # 文件操作模式
        self.file_operation = QComboBox()
        self.file_operation.setFont(QFont("Microsoft YaHei UI", 9))
        self.file_operation.setStyleSheet(self.language.styleSheet())
        self.file_operation.addItems(["复制", "移动"])
        current_op = self.config.get('Settings', 'file_operation', fallback='copy')
        self.file_operation.setCurrentIndex(0 if current_op == 'copy' else 1)
        form_layout.addRow(QLabel("文件操作模式:", font=QFont("Microsoft YaHei UI", 9), styleSheet="color: #ffffff; border: none; background: transparent;"), self.file_operation)
        
        # 子文件夹处理方式
        subfolder_section = QLabel("子文件夹处理设置")
        subfolder_section.setFont(QFont("Microsoft YaHei UI", 14, QFont.Bold))
        subfolder_section.setStyleSheet("color: #ffffff; border: none; background: transparent;")
        form_layout.addRow(subfolder_section)
        
        self.subfolder_mode = QComboBox()
        self.subfolder_mode.setFont(QFont("Microsoft YaHei UI", 9))
        self.subfolder_mode.setStyleSheet(self.language.styleSheet())
        
        # 添加处理方式选项
        self.subfolder_mode.addItem("整体处理：将子文件夹作为整体分类", "whole")
        self.subfolder_mode.addItem("全部解体：将所有文件单独分类", "extract_all")
        self.subfolder_mode.addItem("智能提取：分析提取格格不入的文件", "extract_partial")
        
        # 加载当前设置
        self.load_subfolder_settings()
        
        # 处理方式描述
        self.subfolder_description = QLabel()
        self.subfolder_description.setWordWrap(True)
        self.subfolder_description.setFont(QFont("Microsoft YaHei UI", 9))
        self.subfolder_description.setStyleSheet("color: #aaaaaa; border: none; background: transparent;")
        form_layout.addRow(QLabel("处理方式:", font=QFont("Microsoft YaHei UI", 9), styleSheet="color: #ffffff; border: none; background: transparent;"), self.subfolder_mode)
        form_layout.addRow("", self.subfolder_description)
        
        # 性能设置
        performance_section = QLabel("性能设置")
        performance_section.setFont(QFont("Microsoft YaHei UI", 14, QFont.Bold))
        performance_section.setStyleSheet("color: #ffffff; border: none; background: transparent;")
        form_layout.addRow(performance_section)
        
        # 线程数设置
        thread_layout = QHBoxLayout()
        self.thread_count = QSlider(Qt.Horizontal)
        self.thread_count.setMinimum(1)
        self.thread_count.setMaximum(32)
        self.thread_count.setValue(self.config.getint('Settings', 'thread_count', fallback=8))
        
        self.thread_count.setStyleSheet("""
            QSlider {
                background: transparent;
            }
            QSlider::groove:horizontal {
                height: 8px;
                background: #333333;
                margin: 2px 0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #4CAF50;
                width: 16px;
                margin: -4px 0;
                border-radius: 8px;
            }
            QSlider::sub-page:horizontal {
                background: #4CAF50;
                border-radius: 4px;
            }
        """)
        
        self.thread_count_label = QLabel(str(self.thread_count.value()))
        self.thread_count_label.setStyleSheet("color: #ffffff; border: none; background: transparent;")
        self.thread_count.valueChanged.connect(lambda v: self.thread_count_label.setText(str(v)))
        
        thread_layout.addWidget(self.thread_count)
        thread_layout.addWidget(self.thread_count_label)
        form_layout.addRow(QLabel("线程数:", font=QFont("Microsoft YaHei UI", 9), styleSheet="color: #ffffff; border: none; background: transparent;"), thread_layout)
        
        # 视频分析设置
        video_section = QLabel("视频分析设置")
        video_section.setFont(QFont("Microsoft YaHei UI", 14, QFont.Bold))
        video_section.setStyleSheet("color: #ffffff; border: none; background: transparent;")
        form_layout.addRow(video_section)
        
        # 是否启用视频分析
        self.enable_video = QComboBox()
        self.enable_video.setFont(QFont("Microsoft YaHei UI", 9))
        self.enable_video.setStyleSheet(self.language.styleSheet())
        self.enable_video.addItems(["否", "是"])
        current_video_enabled = self.config.getboolean('Settings', 'enable_video_analysis', fallback=False)
        self.enable_video.setCurrentIndex(1 if current_video_enabled else 0)
        form_layout.addRow(QLabel("启用视频分析:", font=QFont("Microsoft YaHei UI", 9), styleSheet="color: #ffffff; border: none; background: transparent;"), self.enable_video)
        
        # 视频分析警告
        video_warning = QLabel("注意：视频分析会消耗大量API资源，可能会导致高额费用！")
        video_warning.setStyleSheet("color: #ff6b6b; border: none; background: transparent;")
        video_warning.setFont(QFont("Microsoft YaHei UI", 9))
        form_layout.addRow("", video_warning)

        # 模型设置
        model_section = QLabel("模型设置")
        model_section.setFont(QFont("Microsoft YaHei UI", 14, QFont.Bold))
        model_section.setStyleSheet("color: #ffffff; border: none; background: transparent;")
        form_layout.addRow(model_section)
        
        # 图像分析模型
        self.image_model = QLineEdit()
        self.image_model.setFont(QFont("Microsoft YaHei UI", 9))
        self.image_model.setStyleSheet(self.api_url.styleSheet())
        self.image_model.setText(self.config.get('Settings', 'image_analysis_model', 
            fallback='Pro/Qwen/Qwen2-VL-7B-Instruct'))
        form_layout.addRow(QLabel("图像分析模型:", font=QFont("Microsoft YaHei UI", 9), styleSheet="color: #ffffff; border: none; background: transparent;"), self.image_model)
        
        # 视频分析模型
        self.video_model = QLineEdit()
        self.video_model.setFont(QFont("Microsoft YaHei UI", 9))
        self.video_model.setStyleSheet(self.api_url.styleSheet())
        self.video_model.setText(self.config.get('Settings', 'video_analysis_model', 
            fallback='Pro/Qwen/Qwen2-VL-7B-Instruct'))
        form_layout.addRow(QLabel("视频分析模型:", font=QFont("Microsoft YaHei UI", 9), styleSheet="color: #ffffff; border: none; background: transparent;"), self.video_model)
        
        # 文件分析模型
        self.file_model = QLineEdit()
        self.file_model.setFont(QFont("Microsoft YaHei UI", 9))
        self.file_model.setStyleSheet(self.api_url.styleSheet())
        self.file_model.setText(self.config.get('Settings', 'file_analysis_model',
            fallback='deepseek-ai/DeepSeek-R1-Distill-Qwen-7B'))
        form_layout.addRow(QLabel("文件分析模型:", font=QFont("Microsoft YaHei UI", 9), styleSheet="color: #ffffff; border: none; background: transparent;"), self.file_model)
        
        # 整理决策模型
        self.decision_model = QLineEdit()
        self.decision_model.setFont(QFont("Microsoft YaHei UI", 9))
        self.decision_model.setStyleSheet(self.api_url.styleSheet())
        self.decision_model.setText(self.config.get('Settings', 'decision_model',
            fallback='deepseek-ai/DeepSeek-R1-Distill-Qwen-32B'))
        form_layout.addRow(QLabel("整理决策模型:", font=QFont("Microsoft YaHei UI", 9), styleSheet="color: #ffffff; border: none; background: transparent;"), self.decision_model)
        
        # 设置滚动区域的内容
        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)
        
        # 添加保存按钮（在滚动区域外）
        save_btn = QPushButton("保存设置")
        save_btn.setFont(QFont("Microsoft YaHei UI", 10))
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 12px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #2d4d2f;
                color: #aaaaaa;
            }
        """)
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn, alignment=Qt.AlignRight)
        
    def load_config(self):
        """加载配置文件"""
        try:
            self.config.read('config.ini', encoding='utf-8')
            if not self.config.has_section('API'):
                self.config.add_section('API')
            if not self.config.has_section('Settings'):
                self.config.add_section('Settings')
        except Exception as e:
            QMessageBox.warning(self, "警告", f"读取配置文件失败：{str(e)}")
        
    def load_subfolder_settings(self):
        """从配置文件加载子文件夹处理方式设置"""
        try:
            mode = self.config.get('Settings', 'subfolder_mode', fallback='smart')
            # 查找对应的索引
            for i in range(self.subfolder_mode.count()):
                if self.subfolder_mode.itemData(i) == mode:
                    self.subfolder_mode.setCurrentIndex(i)
                    break
        except Exception as e:
            print(f"加载子文件夹处理方式设置失败: {str(e)}")
            
    def save_settings(self):
        """保存设置到配置文件"""
        try:
            # 更新配置
            if not self.config.has_section('API'):
                self.config.add_section('API')
            if not self.config.has_section('Settings'):
                self.config.add_section('Settings')
                
            self.config.set('API', 'api_url', self.api_url.text())
            self.config.set('API', 'api_key', self.api_key.text())
            self.config.set('Settings', 'language', self.language.currentText())
            self.config.set('Settings', 'file_operation', 'copy' if self.file_operation.currentText() == '复制' else 'move')
            self.config.set('Settings', 'image_analysis_model', self.image_model.text())
            self.config.set('Settings', 'file_analysis_model', self.file_model.text())
            self.config.set('Settings', 'decision_model', self.decision_model.text())
            self.config.set('Settings', 'enable_video_analysis', 'true' if self.enable_video.currentText() == '是' else 'false')
            self.config.set('Settings', 'video_analysis_model', self.video_model.text())
            
            # 保存线程数设置
            self.config.set('Settings', 'thread_count', str(self.thread_count.value()))
            
            # 获取选中的处理方式
            mode = self.subfolder_mode.itemData(self.subfolder_mode.currentIndex())
            self.config.set('Settings', 'subfolder_mode', mode)
            
            # 保存到文件
            with open('config.ini', 'w', encoding='utf-8') as f:
                self.config.write(f)
                
            # 发送配置更新信号
            self.config_updated.emit()
            
            QMessageBox.information(self, "成功", "设置已保存")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存设置失败：{str(e)}")

class AboutPage(BasePage):
    def get_title(self):
        return "关于"
        
    def get_subtitle(self):
        return "了解更多信息"
        
    def setup_content(self, layout):
        about_text = QLabel()
        about_text.setWordWrap(True)
        about_text.setOpenExternalLinks(True)
        about_text.setTextFormat(Qt.RichText)
        about_text.setFont(QFont("Microsoft YaHei UI", 10))
        about_text.setStyleSheet("""
            QLabel {
                background-color: transparent;
                color: #ffffff;
                border: none;
                padding: 10px;
            }
        """)
        
        about_content = """
        <h2 style="color: #4CAF50;">文脉通 (DocStream Navigator)</h2>
        <p style="color: #aaaaaa;">版本：v1.3.0</p>
        <br>
        <p style="color: #ffffff;">这是一个使用AI技术的智能文件整理工具，它可以：</p>
        <ul style="color: #ffffff;">
            <li>自动分析文件内容</li>
            <li>智能归类文件</li>
            <li>批量整理文件</li>
            <li>支持图像压缩(非独立功能，会在分析过大图像时自动压缩)</li>
            <li>支持视频分析、压缩包分析(非独立功能，会在需要时自动处理)</li>
        </ul>
        <br>
        <p style="color: #ffffff;">技术支持：</p>
        <ul style="color: #ffffff;">
            <li><a href="https://openai.com" style="color: #4CAF50; text-decoration: underline;">OpenAI API</a></li>
            <li><a href="https://siliconflow.com" style="color: #4CAF50; text-decoration: underline;">SiliconFlow API</a></li>
            <li><a href="https://www.riverbankcomputing.com/software/pyqt/" style="color: #4CAF50; text-decoration: underline;">PyQt5</a></li>
            <li><a href="https://www.python.org" style="color: #4CAF50; text-decoration: underline;">Python 3.8+</a></li>
        </ul>
        <br>
        <p style="color: #aaaaaa;">© 2025 <a href="https://github.com/LoosePrince" style="color: #4CAF50; text-decoration: underline;">树梢（LoosePrince）</a>，所有权利保留。</p>
        """
        
        about_text.setText(about_content)
        layout.addWidget(about_text)