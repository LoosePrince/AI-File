import os
import sys
import configparser
import json
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QPushButton, QLabel, QFrame, QFileDialog,
                           QProgressBar, QTextEdit, QCheckBox, QMessageBox,
                           QScrollArea, QListWidget, QListWidgetItem, QStackedWidget,
                           QLineEdit, QTreeWidget)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt5.QtGui import QFont, QIcon, QDesktopServices
from file_organizer import FileOrganizer, MessageType
from logger import Logger
from config import API_KEY
from pages import RenamePage, SettingsPage, AboutPage

class OrganizeThread(QThread):
    progress = pyqtSignal(str, int)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, directory, output_dir):
        super().__init__()
        self.directory = directory
        self.output_dir = output_dir
        self.prompt = None  # 添加提示词属性

    def set_prompt(self, prompt):
        """设置提示词"""
        self.prompt = prompt

    def run(self):
        try:
            # 统计总文件数
            total_files = sum([len(files) for _, _, files in os.walk(self.directory)])
            analyzed_files = 0
            
            def progress_callback(message, progress=None):
                nonlocal analyzed_files
                
                # 不同类型的消息需要不同的进度处理
                if "正在分析" in message or "使用缓存分析结果" in message:
                    # 文件分析阶段
                    analyzed_files += 1
                    file_progress = int((analyzed_files / total_files) * 100) if total_files > 0 else 0
                    self.progress.emit(message, file_progress)
                elif progress is not None:
                    # 使用API直接传递的进度
                    self.progress.emit(message, progress)
                else:
                    # 无进度的消息
                    self.progress.emit(message, -1)  # -1表示无进度
            
            # 从配置文件读取API密钥
            config = configparser.ConfigParser()
            try:
                config.read('config.ini', encoding='utf-8')
                api_key = config.get('API', 'api_key')
            except:
                # 如果读取失败，使用导入的默认值
                from config import API_KEY as api_key

            organizer = FileOrganizer(api_key, output_dir=self.output_dir)
            # 添加进度回调
            organizer.set_progress_callback(progress_callback)
            # 设置提示词
            if self.prompt:
                organizer.set_prompt(self.prompt)
            result = organizer.organize_directory(self.directory)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

class MoveFilesThread(QThread):
    progress = pyqtSignal(str, int)
    finished = pyqtSignal(bool)  # 修改为传递是否为移动模式的布尔值
    error = pyqtSignal(str)

    def __init__(self, source_dir, output_dir, files):
        super().__init__()
        self.source_dir = source_dir
        self.output_dir = output_dir
        self.files = files
        
        # 读取配置文件确定操作模式
        self.file_operation = 'copy'  # 默认使用复制模式
        try:
            config = configparser.ConfigParser()
            config.read('config.ini', encoding='utf-8')
            self.file_operation = config.get('Settings', 'file_operation', fallback='copy')
        except Exception as e:
            print(f"读取文件操作模式失败: {str(e)}")

    def run(self):
        try:
            total_files = len(self.files)
            for i, file_info in enumerate(self.files, 1):
                original_path = file_info['original_path']
                new_path = file_info['new_path']
                
                # 如果指定了输出目录，调整目标路径
                if self.output_dir:
                    target_path = os.path.join(self.output_dir, new_path.lstrip(os.sep))
                else:
                    target_path = os.path.join(os.path.dirname(original_path), new_path.lstrip(os.sep))
                
                if os.path.exists(original_path):
                    # 创建目标目录
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    
                    operation_name = "复制" if self.file_operation == 'copy' else "移动"
                    
                    # 根据操作模式执行复制或移动
                    if self.file_operation == 'copy':
                        import shutil
                        shutil.copy2(original_path, target_path)  # copy2保留文件的元数据
                    else:
                        import shutil
                        shutil.move(original_path, target_path)
                        
                    progress = int((i / total_files) * 100)
                    self.progress.emit(f"已{operation_name}: {os.path.basename(original_path)} -> {os.path.dirname(new_path)}", progress)
            
            # 完成后传递是否为移动模式的标志
            is_move_mode = self.file_operation != 'copy'
            self.finished.emit(is_move_mode)
        except Exception as e:
            self.error.emit(str(e))

class RestoreFilesThread(QThread):
    progress = pyqtSignal(str, int)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, source_dir, output_dir, files):
        super().__init__()
        self.source_dir = source_dir
        self.output_dir = output_dir
        self.files = files

    def run(self):
        try:
            total_files = len(self.files)
            
            # 创建原始路径到文件信息的映射
            file_map = {f['original_path']: f for f in self.files}
            
            for i, file_info in enumerate(self.files, 1):
                original_path = file_info['original_path']
                new_path = file_info['new_path']
                
                # 计算当前文件的实际路径
                if self.output_dir:
                    current_path = os.path.join(self.output_dir, new_path.lstrip(os.sep))
                else:
                    current_path = os.path.join(os.path.dirname(original_path), new_path.lstrip(os.sep))
                
                # 如果文件不存在，可能有序号，尝试查找带序号的版本
                if not os.path.exists(current_path):
                    basename = os.path.basename(current_path)
                    dirname = os.path.dirname(current_path)
                    name, ext = os.path.splitext(basename)
                    
                    # 检查是否有带序号的版本存在
                    found = False
                    for j in range(2, 10):  # 检查_2到_9的版本
                        numbered_path = os.path.join(dirname, f"{name}_{j}{ext}")
                        if os.path.exists(numbered_path):
                            current_path = numbered_path
                            found = True
                            break
                    
                    if not found:
                        self.progress.emit(f"找不到文件: {new_path}", -1)
                        continue
                
                if os.path.exists(current_path):
                    # 确保原始目录存在
                    os.makedirs(os.path.dirname(original_path), exist_ok=True)
                    
                    # 检查目标是否已存在
                    if os.path.exists(original_path):
                        # 目标已存在，添加序号
                        dirname = os.path.dirname(original_path)
                        basename = os.path.basename(original_path)
                        name, ext = os.path.splitext(basename)
                        
                        # 查找可用的名称
                        counter = 1
                        while True:
                            new_restore_path = os.path.join(dirname, f"{name}_restored_{counter}{ext}")
                            if not os.path.exists(new_restore_path):
                                self.progress.emit(f"目标已存在，还原到: {new_restore_path}", -1)
                                original_path = new_restore_path
                                break
                            counter += 1
                    
                    # 还原文件
                    os.rename(current_path, original_path)
                    progress = int((i / total_files) * 100)
                    self.progress.emit(f"已还原: {os.path.basename(original_path)}", progress)
            
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

class DropArea(QLabel):
    dropped = pyqtSignal(str)
    clicked = pyqtSignal()  # 添加点击信号
    
    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #CCCCCC;
                border-radius: 10px;
                background-color: #333333;
                padding: 20px;
                color: #6C757D;
            }
            QLabel:hover {
                border-color: #4CAF50;
                background-color: #3D3D3D;
            }
        """)
        self.setText("拖放文件夹到这里\n或点击选择文件夹")
        self.setAcceptDrops(True)
        self.setMinimumSize(400, 200)
        self.setCursor(Qt.PointingHandCursor)  # 添加鼠标指针样式
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
            self.setStyleSheet("""
                QLabel {
                    border: 2px dashed #4CAF50;
                    border-radius: 10px;
                    background-color: #3D3D3D;
                    padding: 20px;
                    color: #2E7D32;
                }
            """)
        else:
            event.ignore()
            
    def dragLeaveEvent(self, event):
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #CCCCCC;
                border-radius: 10px;
                background-color: #333333;
                padding: 20px;
                color: #6C757D;
            }
            QLabel:hover {
                border-color: #4CAF50;
                background-color: #3D3D3D;
            }
        """)
        
    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if os.path.isdir(path):
                self.dropped.emit(path)
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #CCCCCC;
                border-radius: 10px;
                background-color: #333333;
                padding: 20px;
                color: #6C757D;
            }
            QLabel:hover {
                border-color: #4CAF50;
                background-color: #3D3D3D;
            }
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()  # 发送点击信号

class FileOrganizerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.logger = Logger()  # 实例化日志类
        self.setWindowTitle("文脉通 (DocStream Navigator)")
        self.setGeometry(100, 100, 1200, 800)
        
        # 设置无边框窗口
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 创建自定义标题栏
        self.title_bar = QWidget(self)
        self.title_bar.setFixedHeight(40)
        self.title_bar.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                border: 1px solid #333333;
            }
        """)
        
        # 创建标题栏布局
        title_bar_layout = QHBoxLayout(self.title_bar)
        title_bar_layout.setContentsMargins(10, 0, 10, 0)
        title_bar_layout.setSpacing(10)
        
        # 添加标题
        title_label = QLabel("文脉通 (DocStream Navigator)")
        title_label.setStyleSheet("color: #4CAF50; font-size: 14px; font-weight: bold;border: none;background: transparent;")
        title_bar_layout.addWidget(title_label)
        
        # 添加弹性空间
        title_bar_layout.addStretch()
        
        # 添加最小化和关闭按钮
        self.minimize_btn = QPushButton("─")
        self.minimize_btn.setFixedSize(30, 30)
        self.minimize_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #ffffff;
                border: none;
                border-radius: 15px;
            }
            QPushButton:hover {
                background-color: #333333;
            }
        """)
        self.minimize_btn.clicked.connect(self.showMinimized)
        
        self.close_btn = QPushButton("×")
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #ffffff;
                border: none;
                border-radius: 15px;
            }
            QPushButton:hover {
                background-color: #e81123;
            }
        """)
        self.close_btn.clicked.connect(self.close)
        
        title_bar_layout.addWidget(self.minimize_btn)
        title_bar_layout.addWidget(self.close_btn)
        
        # 设置主窗口样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
                border-radius: 10px;
            }
            QLabel {
                color: #ffffff;
                font-family: "Microsoft YaHei UI";
            }
            QPushButton {
                background-color: #333333;
                color: #ffffff;
                border: none;
                padding: 8px;
                border-radius: 4px;
                font-family: "Microsoft YaHei UI";
            }
            QPushButton:hover {
                background-color: #444444;
            }
            QPushButton#greenButton {
                background-color: #4CAF50;
            }
            QPushButton#greenButton:hover {
                background-color: #45a049;
            }
            QFrame {
                background-color: #2d2d2d;
                border: 1px solid #333333;
            }
            QTextEdit, QListWidget {
                background-color: #2d2d2d;
                color: #ffffff;
                border: none;
                font-family: "Microsoft YaHei UI";
            }
            QProgressBar {
                background-color: #333333;
                color: #ffffff;
                border: none;
                text-align: center;
                font-family: "Microsoft YaHei UI";
            }
            QProgressBar::chunk {
                background-color: #666666;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QCheckBox {
                color: #ffffff;
                font-family: "Microsoft YaHei UI";
            }
            /* 滚动条整体样式 */
            QScrollBar:vertical {
                border: none;
                background: #2d2d2d;
                width: 10px;
                margin: 0px;
            }
            /* 滚动条滑块 */
            QScrollBar::handle:vertical {
                background: #666666;
                min-height: 20px;
                border-radius: 5px;
            }
            /* 滚动条上方按钮 */
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
            /* 滚动条下方按钮 */
            QScrollBar::add-line:vertical {
                height: 0px;
            }
            /* 滚动条背景 */
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
            /* 水平滚动条样式 */
            QScrollBar:horizontal {
                border: none;
                background: #2d2d2d;
                height: 10px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: #666666;
                min-width: 20px;
                border-radius: 5px;
            }
            QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            QScrollBar::add-line:horizontal {
                width: 0px;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }
        """)
        
        self.organizer = None
        self.is_organizing = False
        self.source_dir = ""
        self.output_dir = ""
        self.organize_result = None
        self.config = configparser.ConfigParser()
        self.cache_file = "file_organize_cache.json"  # 添加缓存文件路径
        
        self.init_ui()
        self.check_restore_cache()  # 检查是否有可还原的缓存
        
        # 设置窗口阴影
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 添加鼠标事件处理
        self.title_bar.mousePressEvent = self.mousePressEvent
        self.title_bar.mouseMoveEvent = self.mouseMoveEvent
        self.title_bar.mouseReleaseEvent = self.mouseReleaseEvent
        
        self.dragging = False
        self.offset = None
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.offset = event.pos()
            
    def mouseMoveEvent(self, event):
        if self.dragging:
            self.move(self.mapToGlobal(event.pos() - self.offset))
            
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False
            self.offset = None
        
    def init_ui(self):
        # 创建主窗口部件
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        # 创建主布局
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 添加标题栏
        main_layout.addWidget(self.title_bar)
        
        # 创建内容区域
        content_widget = QWidget()
        content_widget.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                border-bottom-left-radius: 10px;
                border-bottom-right-radius: 10px;
            }
        """)
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # 创建侧边栏
        sidebar = QFrame()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet("""
            background-color: #121212;
            border-right: 1px solid #333333;
            border-bottom-left-radius: 10px;
        """)
        sidebar_layout = QVBoxLayout(sidebar)
        
        # 添加标题
        title = QLabel("文脉通")
        title.setFont(QFont("Microsoft YaHei UI", 16, QFont.Bold))
        title.setStyleSheet("color: #4CAF50; border: none;")
        title.setAlignment(Qt.AlignCenter)
        sidebar_layout.addWidget(title)
        
        # 添加导航按钮
        self.file_manage_btn = QPushButton("文件整理")
        self.file_manage_btn.setFont(QFont("Microsoft YaHei UI", 10))
        self.file_manage_btn.clicked.connect(lambda: self.show_page("file_manage"))
        sidebar_layout.addWidget(self.file_manage_btn)
        
        self.rename_btn = QPushButton("智能文件重命名")
        self.rename_btn.setFont(QFont("Microsoft YaHei UI", 10))
        self.rename_btn.clicked.connect(lambda: self.show_page("rename"))
        sidebar_layout.addWidget(self.rename_btn)
        
        self.settings_btn = QPushButton("设置")
        self.settings_btn.setFont(QFont("Microsoft YaHei UI", 10))
        self.settings_btn.clicked.connect(lambda: self.show_page("settings"))
        sidebar_layout.addWidget(self.settings_btn)
        
        self.about_btn = QPushButton("关于")
        self.about_btn.setFont(QFont("Microsoft YaHei UI", 10))
        self.about_btn.clicked.connect(lambda: self.show_page("about"))
        sidebar_layout.addWidget(self.about_btn)
        
        sidebar_layout.addStretch()
        
        # 创建堆叠式页面容器
        self.page_container = QStackedWidget()
        self.page_container.setStyleSheet("""
            QStackedWidget {
                background-color: #1e1e1e;
                border-bottom-right-radius: 10px;
            }
        """)
        
        # 创建并添加各个页面
        self.file_manage_page = QWidget()  # 原有的文件整理页面
        self.setup_file_manage_page(self.file_manage_page)
        self.page_container.addWidget(self.file_manage_page)
        
        self.rename_page = RenamePage()
        self.page_container.addWidget(self.rename_page)
        
        self.settings_page = SettingsPage()
        self.page_container.addWidget(self.settings_page)
        
        self.about_page = AboutPage()
        self.page_container.addWidget(self.about_page)
        
        # 将侧边栏和页面容器添加到内容布局
        content_layout.addWidget(sidebar)
        content_layout.addWidget(self.page_container)
        
        # 将内容区域添加到主布局
        main_layout.addWidget(content_widget)
        
        # 设置初始页面
        self.show_page("file_manage")
        
    def show_page(self, page_name):
        # 重置所有按钮样式
        for btn in [self.file_manage_btn, self.rename_btn, self.settings_btn, self.about_btn]:
            btn.setStyleSheet("")
        
        # 设置选中按钮样式
        if page_name == "file_manage":
            self.file_manage_btn.setStyleSheet("background-color: #333333;")
            self.page_container.setCurrentWidget(self.file_manage_page)
        elif page_name == "rename":
            self.rename_btn.setStyleSheet("background-color: #333333;")
            self.page_container.setCurrentWidget(self.rename_page)
        elif page_name == "settings":
            self.settings_btn.setStyleSheet("background-color: #333333;")
            self.page_container.setCurrentWidget(self.settings_page)
        elif page_name == "about":
            self.about_btn.setStyleSheet("background-color: #333333;")
            self.page_container.setCurrentWidget(self.about_page)
            
    def setup_file_manage_page(self, page):
        # 创建主布局
        main_layout = QVBoxLayout(page)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)
        
        # 创建内容容器
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(20)
        
        # 修改标题和子标题的布局
        title_container = QFrame()
        title_container.setStyleSheet("background: transparent; border: none;")
        title_layout = QVBoxLayout(title_container)
        title_layout.setSpacing(5)
        title_layout.setContentsMargins(0, 0, 0, 15)  # 减小底部边距
        
        # 标题和还原按钮行
        header_layout = QHBoxLayout()
        header_layout.setAlignment(Qt.AlignCenter)  # 居中对齐
        content_title = QLabel("超级文件归档工具")
        content_title.setFont(QFont("Microsoft YaHei UI", 24, QFont.Bold))
        content_title.setStyleSheet("color: #4CAF50; border: none;")
        header_layout.addWidget(content_title)
        
        # 添加还原按钮
        self.restore_btn = QPushButton("一键还原")
        self.restore_btn.setObjectName("greenButton")
        self.restore_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 10px;
                padding: 8px 16px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.restore_btn.clicked.connect(self.restore_files)
        self.restore_btn.hide()
        header_layout.addWidget(self.restore_btn)
        header_layout.addStretch()
        
        title_layout.addLayout(header_layout)
        
        # 子标题固定位置
        subtitle = QLabel("选择文件夹，可以对杂乱的文件夹进行归类整理（AI的响应可能出现问题，请在整理前备份您的文件，防止数据丢失！）")
        subtitle.setStyleSheet("color: #aaaaaa; font-size: 9pt; border: none; background: transparent;")
        subtitle.setFont(QFont("Microsoft YaHei UI", 9))
        title_layout.addWidget(subtitle)
        
        content_layout.addWidget(title_container)
        
        # 添加路径显示标签
        self.path_label = QLabel()
        self.path_label.setStyleSheet("""
            color: #aaaaaa; 
            font-size: 9pt; 
            font-family: "Microsoft YaHei UI";
            border: none; 
            background: transparent;
            padding: 8px 12px;
            background-color: #2d2d2d;
            border-radius: 4px;
        """)
        self.path_label.setWordWrap(True)
        content_layout.addWidget(self.path_label)
        
        # 添加拖放区域
        self.drop_area = DropArea()
        self.drop_area.dropped.connect(self.set_source_dir)
        self.drop_area.clicked.connect(self.select_source_directory)  # 连接点击信号
        content_layout.addWidget(self.drop_area)
        
        # 添加按钮容器
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 5, 0, 5)  # 减小上下边距
        button_layout.setSpacing(12)  # 增加按钮间距
        
        # 添加选择文件夹按钮
        self.select_folder_btn = QPushButton('选择源文件夹')
        self.select_folder_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 5px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.select_folder_btn.clicked.connect(self.select_source_directory)
        button_layout.addWidget(self.select_folder_btn)
        
        # 添加选择输出文件夹按钮
        self.select_output_btn = QPushButton('选择输出文件夹')
        self.select_output_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 5px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        self.select_output_btn.clicked.connect(self.select_output_directory)
        button_layout.addWidget(self.select_output_btn)
        
        button_layout.addStretch()
        content_layout.addWidget(button_container)
        
        # 添加提示词输入框
        prompt_container = QFrame()
        prompt_container.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border-radius: 8px;
                padding: 5px;
                max-height: 160px;
            }
        """)
        prompt_layout = QVBoxLayout(prompt_container)
        prompt_layout.setSpacing(8)  # 减小内部间距
        
        # 提示词标签
        prompt_label = QLabel("AI提示词（可选）：")
        prompt_label.setStyleSheet("color: #ffffff; font-size: 9pt; border: none; background: transparent;")
        prompt_label.setFont(QFont("Microsoft YaHei UI", 9))
        prompt_layout.addWidget(prompt_label)
        
        # 提示词输入框
        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText("在这里输入提示词，将影响AI的整理决策...")
        self.prompt_input.setStyleSheet("""
            QTextEdit {
                background-color: #333333;
                color: #ffffff;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 5px;
                min-height: 10px;
                max-height: 40px;
                font-size: 9pt;
            }
            QTextEdit:focus {
                border: 1px solid #4CAF50;
            }
        """)
        self.prompt_input.setFont(QFont("Microsoft YaHei UI", 9))
        prompt_layout.addWidget(self.prompt_input)
        
        content_layout.addWidget(prompt_container)
        
        # 创建文件列表（初始隐藏）
        self.file_list_widget = QListWidget()
        self.file_list_widget.setFont(QFont("Microsoft YaHei UI", 9))
        self.file_list_widget.setMinimumHeight(600)  # 设置最小高度
        self.file_list_widget.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
            }
            QListWidget::item {
                background-color: #333333;
                border-radius: 4px;
                margin: 2px 0;
                padding: 8px;
            }
            QListWidget::item:hover {
                background-color: #3d3d3d;
            }
        """)
        self.file_list_widget.hide()
        content_layout.addWidget(self.file_list_widget)
        
        # 添加进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 4px;
                text-align: center;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 4px;
            }
        """)
        self.progress_bar.hide()
        content_layout.addWidget(self.progress_bar)
        
        # 添加弹性空间
        # content_layout.addStretch()
        
        # 设置滚动区域的内容
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
        
        # 创建底部固定按钮区域
        bottom_frame = QFrame()
        bottom_frame.setStyleSheet("""
            QFrame {
                background-color: #1e1e1e;
                border-top: 1px solid #333333;
            }
        """)
        bottom_layout = QHBoxLayout(bottom_frame)
        bottom_layout.setContentsMargins(20, 10, 20, 10)
        bottom_layout.setSpacing(10)
        
        # 添加取消和开始按钮
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setMinimumWidth(100)
        self.cancel_btn.hide()
        self.cancel_btn.clicked.connect(self.cancel_organize)
        bottom_layout.addWidget(self.cancel_btn)
        
        self.start_btn = QPushButton("整理文件")
        self.start_btn.setObjectName("greenButton")
        self.start_btn.setMinimumWidth(100)
        self.start_btn.clicked.connect(self.start_organize)
        bottom_layout.addWidget(self.start_btn)
        
        main_layout.addWidget(bottom_frame)
        
    def set_source_dir(self, path):
        self.source_dir = path
        self.update_file_list()
        self.update_path_label()
        # 更新按钮文字
        self.select_folder_btn.setText("更改源文件夹")
        
    def update_path_label(self):
        text = ""
        if self.source_dir:
            text += f"源文件夹: {self.source_dir}\n"
        if self.output_dir:
            text += f"输出文件夹: {self.output_dir}"
        self.path_label.setText(text)

    def update_file_list(self):
        self.file_list_widget.clear()
        if self.source_dir:
            # 隐藏初始拖放视图，显示文件列表
            self.drop_area.hide()
            self.file_list_widget.show()
            
            # 获取子文件夹处理模式
            try:
                self.config.read('config.ini', encoding='utf-8')
                subfolder_mode = self.config.get('Settings', 'subfolder_mode', fallback='whole')
            except Exception:
                subfolder_mode = 'whole'  # 默认使用解体模式
            
            # 创建已显示的文件夹集合，用于避免重复显示
            displayed_folders = set()
            
            for root, dirs, files in os.walk(self.source_dir):
                # 相对路径（相对于源目录）
                rel_path = os.path.relpath(root, self.source_dir)
                
                # 如果不是源目录本身，并且不是以"."开头的隐藏目录
                is_subfolder = (rel_path != "." and not rel_path.startswith("."))
                
                # 根据子文件夹处理模式决定显示方式
                if is_subfolder and subfolder_mode != 'extract_all':
                    # 对于非解体模式，显示文件夹
                    if root not in displayed_folders:
                        displayed_folders.add(root)
                        self._add_folder_item(root, rel_path)
                else:
                    # 解体模式或源目录本身，显示所有文件
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_file_path = os.path.relpath(full_path, self.source_dir)
                        self._add_file_item(full_path, rel_file_path)
    
    def _add_file_item(self, full_path, relative_path):
        """添加文件项到列表"""
        # 创建自定义widget来显示文件信息
        item_widget = QWidget()
        item_layout = QVBoxLayout(item_widget)
        item_layout.setSpacing(4)
        item_layout.setContentsMargins(10, 8, 10, 8)
        
        # 文件名和状态的容器
        name_container = QWidget()
        name_layout = QHBoxLayout(name_container)
        name_layout.setContentsMargins(0, 0, 0, 0)
        name_layout.setSpacing(10)
        
        # 文件名（作为链接）
        name_label = QLabel(os.path.basename(relative_path))
        name_label.setFont(QFont("Microsoft YaHei UI", 11))
        name_label.setStyleSheet("""
            color: #4CAF50; 
            border: none; 
            background: transparent;
            text-decoration: underline;
        """)
        name_label.setCursor(Qt.PointingHandCursor)
        name_label.setToolTip("点击打开文件")
        
        # 使用lambda创建点击事件处理器，确保每个标签都有自己的文件路径
        def create_click_handler(file_path):
            def handler(event):
                QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
            return handler
        
        name_label.mousePressEvent = create_click_handler(full_path)
        name_layout.addWidget(name_label)
        
        # 状态标签（初始隐藏）
        status_label = QLabel()
        status_label.setFont(QFont("Microsoft YaHei UI", 9))
        status_label.setStyleSheet("color: #4CAF50; border: none; background: transparent;")
        status_label.hide()  # 初始隐藏
        status_label.setToolTip("")  # 初始化工具提示
        name_layout.addWidget(status_label)
        name_layout.addStretch()
        
        item_layout.addWidget(name_container)
        
        # 完整路径信息（作为链接）
        path_label = QLabel(full_path)
        path_label.setFont(QFont("Microsoft YaHei UI", 9))
        path_label.setStyleSheet("""
            color: #888888; 
            border: none; 
            background: transparent;
            text-decoration: underline;
        """)
        path_label.setCursor(Qt.PointingHandCursor)
        path_label.setWordWrap(True)
        path_label.setToolTip("点击打开所在文件夹")
        
        # 为路径标签创建点击事件处理器
        def create_folder_click_handler(file_path):
            def handler(event):
                QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(file_path)))
            return handler
        
        path_label.mousePressEvent = create_folder_click_handler(full_path)
        item_layout.addWidget(path_label)
        
        # 创建列表项并设置自定义widget
        item = QListWidgetItem()
        item_widget.adjustSize()
        item.setSizeHint(item_widget.sizeHint())
        self.file_list_widget.addItem(item)
        self.file_list_widget.setItemWidget(item, item_widget)

    def _add_folder_item(self, folder_path, relative_path):
        """添加文件夹项到列表"""
        # 创建自定义widget来显示文件夹信息
        item_widget = QWidget()
        item_layout = QVBoxLayout(item_widget)
        item_layout.setSpacing(4)
        item_layout.setContentsMargins(10, 8, 10, 8)
        
        # 文件夹名和状态的容器
        name_container = QWidget()
        name_layout = QHBoxLayout(name_container)
        name_layout.setContentsMargins(0, 0, 0, 0)
        name_layout.setSpacing(10)
        
        # 文件夹图标
        folder_icon = QLabel("📁")
        folder_icon.setFont(QFont("Segoe UI Emoji", 14))
        name_layout.addWidget(folder_icon)
        
        # 文件夹名（作为链接）
        name_label = QLabel(os.path.basename(folder_path))
        name_label.setFont(QFont("Microsoft YaHei UI", 11, QFont.Bold))
        name_label.setStyleSheet("""
            color: #4169E1; 
            border: none; 
            background: transparent;
            text-decoration: underline;
        """)
        name_label.setCursor(Qt.PointingHandCursor)
        name_label.setToolTip("点击打开文件夹")
        
        # 添加点击事件处理器
        def create_click_handler(folder_path):
            def handler(event):
                QDesktopServices.openUrl(QUrl.fromLocalFile(folder_path))
            return handler
        
        name_label.mousePressEvent = create_click_handler(folder_path)
        name_layout.addWidget(name_label)
        
        # 状态标签（初始隐藏）
        status_label = QLabel("子文件夹")
        status_label.setFont(QFont("Microsoft YaHei UI", 9))
        status_label.setStyleSheet("color: #888888; border: none; background: transparent;")
        name_layout.addWidget(status_label)
        name_layout.addStretch()
        
        item_layout.addWidget(name_container)
        
        # 统计文件夹内容
        file_count = 0
        for _, _, files in os.walk(folder_path):
            file_count += len(files)
        
        # 路径和文件统计信息
        info_text = f"{folder_path}\n包含 {file_count} 个文件"
        path_label = QLabel(info_text)
        path_label.setFont(QFont("Microsoft YaHei UI", 9))
        path_label.setStyleSheet("color: #888888; border: none; background: transparent;")
        path_label.setWordWrap(True)
        item_layout.addWidget(path_label)
        
        # 创建列表项并设置自定义widget
        item = QListWidgetItem()
        item_widget.adjustSize()
        item.setSizeHint(item_widget.sizeHint())
        self.file_list_widget.addItem(item)
        self.file_list_widget.setItemWidget(item, item_widget)

    def get_language_setting(self):
        """从配置文件获取语言设置"""
        try:
            self.config.read('config.ini', encoding='utf-8')
            language = self.config.get('Settings', 'language', fallback='中文')
            return 'zh' if language == '中文' else 'en'
        except Exception:
            return 'zh'  # 默认使用中文
            
    def start_organize(self):
        if not self.source_dir:
            self.logger.log_warning("用户未选择源文件夹")
            QMessageBox.warning(self, "警告", "请先选择要整理的文件夹")
            return
            
        if not self.output_dir:
            self.logger.log_warning("用户未选择输出文件夹")
            QMessageBox.warning(self, "警告", "请先选择输出文件夹")
            return
            
        # 如果按钮文字是"确认整理"，说明是确认阶段
        if self.start_btn.text() == "确认整理":
            # 重置按钮样式和文字
            self.start_btn.setText("整理文件")
            self.start_btn.setStyleSheet("")
            self.start_btn.setObjectName("greenButton")
            # 执行文件移动
            self.move_files(self.organize_result)
            return
            
        # 检查是否存在缓存文件
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    if cache_data and 'files' in cache_data:
                        reply = QMessageBox.question(
                            self, 
                            "确认", 
                            "检测到存在上次的整理结果缓存，继续整理将覆盖缓存并失去一键还原功能。\n是否继续？",
                            QMessageBox.Yes | QMessageBox.No,
                            QMessageBox.No  # 默认选择"否"
                        )
                        if reply == QMessageBox.No:
                            return
            except Exception as e:
                self.logger.log_error(f"读取缓存文件失败：{str(e)}")
            
        # 创建并启动分析线程
        self.organize_thread = OrganizeThread(self.source_dir, self.output_dir)
        self.organize_thread.progress.connect(self.update_progress)
        self.organize_thread.finished.connect(self.show_confirm_dialog)
        self.organize_thread.error.connect(self.organize_error)
        
        # 获取提示词
        prompt = self.prompt_input.toPlainText().strip()
        if prompt:
            self.organize_thread.set_prompt(prompt)
        
        self.is_organizing = True
        self.progress_bar.show()
        self.progress_bar.setRange(0, 0)  # 设置为循环进度条
        self.start_btn.hide()
        self.cancel_btn.show()
        
        self.organize_thread.start()
        
    def update_progress(self, message, progress=None):
        # 打印消息便于调试
        print(f"进度消息: {message}, 传入进度: {progress}")

        # 更新进度条和消息 - 优先使用API直接传递的进度
        if progress is not None and progress >= 0:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(progress)
        elif message == MessageType.GENERATING_DECISION:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
        elif message == MessageType.DECISION_GENERATED:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
        elif message == MessageType.RETRY_BATCH:
            pass
        elif message == MessageType.FILE_MOVED:
            parts = message.split("文件 ")[1].split(" 已移动到：")
            if len(parts) == 2:
                file_path = parts[0]
                target_path = parts[1]
                self.update_file_target_path(file_path, target_path)
        elif message == MessageType.ANALYZING:
            file_path = message.split("：")[1] if "：" in message else ""
            if file_path:
                self.update_file_analysis_status(file_path, "分析中", "#FFA500")
        elif message == MessageType.FILE_NEED_ANALYSIS:
            file_path = message.split("：")[1] if "：" in message else ""
            if file_path:
                self.update_file_analysis_status(file_path, "待分析", "#3498DB")
        elif message == MessageType.CACHED_ANALYSIS:
            file_path = message.split("：")[1] if "：" in message else ""
            if file_path:
                self.update_file_analysis_status(file_path, "已分析", "#4CAF50")
        elif message == MessageType.CACHED_DECISION:
            parts = message.split("：")[1].split(" -> ") if "：" in message else ["", ""]
            if len(parts) == 2:
                file_path = parts[0]
                target_path = parts[1]
                self.update_file_cache_status(file_path, target_path)
        elif message == MessageType.ALL_CACHED_DECISION:
            self.setWindowTitle(f"智能文件整理工具 - 全部使用缓存整理方案！")
        elif message == MessageType.GENERATING_DECISION_PROGRESS:
            pass
        elif "完成第" in message and "批" in message:
            try:
                parts = message.split("完成第")[1].split("批")[0]
                current_batch = int(parts.split("/")[0])
                total_batches = int(parts.split("/")[1])
                batch_progress = int((current_batch / total_batches) * 100)
                self.progress_bar.setRange(0, 100)
                self.progress_bar.setValue(batch_progress)
            except Exception as e:
                print(f"解析批次完成进度失败: {e}")
        elif "重试当前批次" in message:
            pass
        elif "连接失败" in message or "分析过程出现错误" in message:
            self.progress_bar.setRange(0, 0)
        elif "使用缓存的整理方案" in message:
            parts = message.split("：")[1].split(" -> ") if "：" in message else ["", ""]
            if len(parts) == 2:
                file_path = parts[0]
                target_path = parts[1]
                self.update_file_cache_status(file_path, target_path)

        # 更新GUI中的状态信息显示
        status_text = None
        if message == MessageType.ANALYZING:
            status_text = "分析中..."
        elif message == MessageType.CACHED_ANALYSIS:
            status_text = "使用缓存分析..."
        elif message == MessageType.CACHED_DECISION:
            status_text = "使用缓存整理方案..."
        elif message == MessageType.ALL_CACHED_DECISION:
            status_text = "全部使用缓存整理方案！"
        elif message == MessageType.GENERATING_DECISION:
            status_text = "生成整理方案中..."
        elif message == MessageType.GENERATING_DECISION_PROGRESS:
            status_text = "正在生成整理方案..."
        elif "完成第" in message and "批" in message:
            status_text = f"完成批次 {message.split('完成第')[1]}"
        elif message == MessageType.DECISION_GENERATED:
            status_text = "整理方案生成完成!"
        elif message == MessageType.RETRY_BATCH:
            status_text = "正在重试..."
        
        # 如果有状态文本要显示，更新窗口标题
        if status_text:
            self.setWindowTitle(f"智能文件整理工具 - {status_text}")
            
        # 更新进度文本（如果有进度值）
        if progress is not None and progress >= 0:
            percent_text = f"{progress}%"
            self.progress_bar.setFormat(f"{status_text if status_text else ''} {percent_text}")
    
    def update_file_analysis_status(self, file_path, status_text, color="#4CAF50"):
        """更新文件的分析状态显示"""
        if not file_path:
            return
            
        for i in range(self.file_list_widget.count()):
            item = self.file_list_widget.item(i)
            widget = self.file_list_widget.itemWidget(item)
            if widget:
                name_container = widget.layout().itemAt(0).widget()
                status_label = name_container.layout().itemAt(1).widget()
                path_label = widget.layout().itemAt(1).widget()
                current_path = path_label.text().split('\n')[0].replace('当前位置：', '').replace('原路径：', '')
                
                if current_path == file_path:
                    # 更新状态标签
                    status_label.setText(status_text)
                    status_label.setStyleSheet(f"color: {color}; border: none; background: transparent;")
                    status_label.show()
                    break
    
    def update_file_target_path(self, file_path, target_path):
        """更新文件的目标路径显示"""
        if not file_path:
            return
            
        for i in range(self.file_list_widget.count()):
            item = self.file_list_widget.item(i)
            widget = self.file_list_widget.itemWidget(item)
            if widget:
                name_container = widget.layout().itemAt(0).widget()
                path_label = widget.layout().itemAt(1).widget()
                current_path = path_label.text().split('\n')[0].replace('当前位置：', '').replace('原路径：', '')
                
                if current_path == file_path:
                    # 更新路径标签
                    path_text = f"当前位置：{current_path}\n将移动到：{target_path}"
                    path_label.setText(path_text)
                    path_label.setMinimumHeight(60)  # 确保有足够的高度显示两行
                    # 调整整个item的大小
                    widget.adjustSize()
                    item.setSizeHint(widget.sizeHint())
                    break
    
    def update_file_cache_status(self, file_path, target_path=None):
        """更新文件的缓存状态显示"""
        if not file_path:
            return
            
        # 计算已使用缓存的文件数
        cached_count = 0
        total_count = self.file_list_widget.count()
        
        for i in range(total_count):
            item = self.file_list_widget.item(i)
            widget = self.file_list_widget.itemWidget(item)
            if widget:
                name_container = widget.layout().itemAt(0).widget()
                status_label = name_container.layout().itemAt(1).widget()
                path_label = widget.layout().itemAt(1).widget()
                current_path = path_label.text().split('\n')[0].replace('当前位置：', '').replace('原路径：', '')
                
                if status_label.text() == "使用缓存":
                    cached_count += 1
                    
                if current_path == file_path:
                    # 标记当前文件为使用缓存
                    status_label.setText("使用缓存")
                    status_label.setStyleSheet("color: #4CAF50; border: none; background: transparent;")
                    status_label.show()
                    
                    # 如果提供了目标路径，更新文件路径显示
                    if target_path:
                        path_text = f"当前位置：{current_path}\n将移动到：{target_path}"
                        path_label.setText(path_text)
                        path_label.setMinimumHeight(60)
                        widget.adjustSize()
                        item.setSizeHint(widget.sizeHint())
                    
                    cached_count += 1
        
        # 更新窗口标题中的缓存计数
        if cached_count > 0:
            self.setWindowTitle(f"智能文件整理工具 - 使用缓存：{cached_count}/{total_count}文件")
            
    def show_confirm_dialog(self, result):
        self.organize_result = result
        self.is_organizing = False
        self.progress_bar.hide()
        self.cancel_btn.hide()
        
        # 更新文件列表显示移动目标
        self.update_file_list_with_result(result)
        
        # 更新开始按钮为确认按钮
        self.start_btn.setText("确认整理")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFA500;  /* 橙色 */
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #FF8C00;  /* 深橙色 */
            }
        """)
        self.start_btn.show()
        
        # 显示分类统计
        if isinstance(result, dict) and 'files' in result:
            categories = {}
            for file_info in result['files']:
                category = os.path.dirname(file_info['new_path'])
                if category:
                    categories[category] = categories.get(category, 0) + 1
            
            # 更新窗口标题显示分类统计
            category_text = " | ".join([f"{cat.strip('/')}: {count}个文件" for cat, count in categories.items()])
            self.setWindowTitle(f"智能文件整理工具 - {category_text}")

    def update_file_list_with_result(self, result):
        if not isinstance(result, dict) or 'files' not in result:
            return
            
        # 创建文件路径映射
        file_info_map = {f['original_path']: f for f in result['files']}
        
        for i in range(self.file_list_widget.count()):
            item = self.file_list_widget.item(i)
            widget = self.file_list_widget.itemWidget(item)
            if widget:
                name_container = widget.layout().itemAt(0).widget()
                path_label = widget.layout().itemAt(1).widget()
                current_path = path_label.text().split('\n')[0].replace('当前位置：', '')
                
                if current_path in file_info_map:
                    file_info = file_info_map[current_path]
                    # 更新路径标签，使用更大的垂直间距
                    path_text = f"当前位置：{current_path}\n将移动到：{file_info['new_path']}"
                    path_label.setText(path_text)
                    path_label.setMinimumHeight(60)  # 确保有足够的高度显示两行
                    # 调整整个item的大小
                    widget.adjustSize()
                    new_height = widget.sizeHint().height() + 20  # 添加额外的垂直空间
                    item.setSizeHint(widget.sizeHint())

    def move_files(self, result):
        if not isinstance(result, dict) or 'files' not in result:
            QMessageBox.critical(self, "错误", "整理结果格式错误")
            return
            
        self.is_organizing = True
        self.progress_bar.show()
        self.progress_bar.setRange(0, 0)
        self.cancel_btn.show()
        
        # 创建移动线程
        self.move_thread = MoveFilesThread(self.source_dir, self.output_dir, result['files'])
        self.move_thread.progress.connect(self.update_progress)
        self.move_thread.finished.connect(self.move_finished)
        self.move_thread.error.connect(self.organize_error)
        self.move_thread.start()
        
    def move_finished(self, is_move_mode):
        self.is_organizing = False
        self.progress_bar.hide()
        self.cancel_btn.hide()
        self.start_btn.show()
        
        # 仅在移动模式下显示还原按钮并保存缓存
        if is_move_mode:
            self.restore_btn.show()
            self.save_organize_cache()
        
        operation_text = "移动" if is_move_mode else "复制"
        QMessageBox.information(self, "完成", f"文件{operation_text}完成！")
        
    def restore_files(self):
        if not self.organize_result or not isinstance(self.organize_result, dict) or 'files' not in self.organize_result:
            return
            
        reply = QMessageBox.question(self, "确认", "确定要还原所有文件到原始位置吗？",
                                   QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.is_organizing = True
            self.progress_bar.show()
            self.progress_bar.setRange(0, 100)
            self.cancel_btn.show()
            self.restore_btn.hide()
            
            # 创建还原线程
            self.restore_thread = RestoreFilesThread(self.source_dir, self.output_dir, self.organize_result['files'])
            self.restore_thread.progress.connect(self.update_progress)
            self.restore_thread.finished.connect(self.restore_finished)
            self.restore_thread.error.connect(self.organize_error)
            self.restore_thread.start()

    def restore_finished(self):
        self.is_organizing = False
        self.progress_bar.hide()
        self.cancel_btn.hide()
        self.start_btn.show()
        self.restore_btn.hide()  # 隐藏还原按钮
        self.clear_organize_cache()  # 清除缓存文件
        QMessageBox.information(self, "完成", "文件已还原到原始位置！")
        self.update_file_list()
        
    def cancel_organize(self):
        if self.is_organizing:
            reply = QMessageBox.question(self, "确认", "确定要取消整理吗？",
                                       QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.is_organizing = False
                self.progress_bar.hide()
                self.file_list_widget.hide()
                self.cancel_btn.hide()
                self.start_btn.show()
                self.source_dir = ""
                self.output_dir = ""
                self.file_list_widget.clear()
                
    def organize_error(self, error_msg):
        self.logger.log_error(f"整理过程中出现错误：{error_msg}")
        self.is_organizing = False
        self.progress_bar.hide()
        self.cancel_btn.hide()
        self.start_btn.show()
        QMessageBox.critical(self, "错误", f"整理过程中出现错误：{error_msg}")

    def update_all_analyzing_files_to_analyzed(self):
        """将所有显示为正在分析的文件状态更新为已分析"""
        for i in range(self.file_list_widget.count()):
            item = self.file_list_widget.item(i)
            widget = self.file_list_widget.itemWidget(item)
            if widget:
                name_container = widget.layout().itemAt(0).widget()
                status_label = name_container.layout().itemAt(1).widget()
                
                # 如果状态是"正在分析"或"待分析"，更新为"已分析"
                if status_label.text() in ["正在分析", "待分析"]:
                    status_label.setText("已分析")
                    status_label.setStyleSheet("color: #4CAF50; border: none; background: transparent;")
                    status_label.show()

    def select_source_directory(self):
        """选择源文件夹"""
        directory = QFileDialog.getExistingDirectory(self, "选择要整理的文件夹")
        if directory:
            self.set_source_dir(directory)
        
    def select_output_directory(self):
        """选择输出文件夹"""
        directory = QFileDialog.getExistingDirectory(self, "选择输出文件夹")
        if directory:
            self.output_dir = directory
            self.update_path_label()

    def check_restore_cache(self):
        """检查是否有可还原的缓存文件"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    if cache_data and 'files' in cache_data:
                        self.organize_result = cache_data
                        self.restore_btn.show()
                        self.logger.log_info("检测到可还原的缓存文件")
        except Exception as e:
            self.logger.log_error(f"读取缓存文件失败：{str(e)}")
            
    def save_organize_cache(self):
        """保存整理结果到缓存文件"""
        try:
            if self.organize_result:
                with open(self.cache_file, 'w', encoding='utf-8') as f:
                    json.dump(self.organize_result, f, ensure_ascii=False, indent=2)
                self.logger.log_info("已保存整理结果到缓存文件")
        except Exception as e:
            self.logger.log_error(f"保存缓存文件失败：{str(e)}")
            
    def clear_organize_cache(self):
        """清除整理结果缓存文件"""
        try:
            if os.path.exists(self.cache_file):
                os.remove(self.cache_file)
                self.logger.log_info("已清除整理结果缓存文件")
        except Exception as e:
            self.logger.log_error(f"清除缓存文件失败：{str(e)}") 