import configparser
import os

# 配置文件路径
CONFIG_FILE = 'config.ini'

# 创建配置解析器
config = configparser.ConfigParser()

def create_default_config():
    """创建默认配置"""
    config['API'] = {
        'API_KEY': 'sk_test_1234567890',
        'API_URL': 'https://api.siliconflow.cn/v1'
    }
    
    config['Settings'] = {
        'file_operation': 'copy',
        'image_analysis_model': 'Pro/Qwen/Qwen2-VL-7B-Instruct',
        'file_analysis_model': 'deepseek-ai/DeepSeek-R1-Distill-Qwen-7B',
        'decision_model': 'deepseek-ai/DeepSeek-R1-Distill-Qwen-32B',
        'enable_video_analysis': 'false',
        'video_analysis_model': 'Pro/Qwen/Qwen2-VL-7B-Instruct',
        'language': '中文',
        'subfolder_mode': 'whole',  # 默认整体处理
        'thread_count': '8'  # 添加默认线程数设置
    }
    
    # 写入配置文件
    with open(CONFIG_FILE, 'w', encoding='utf-8') as configfile:
        config.write(configfile)

def load_config():
    """加载配置文件"""
    if not os.path.exists(CONFIG_FILE):
        create_default_config()
    
    # 读取配置文件
    config.read(CONFIG_FILE, encoding='utf-8')
    
    # API设置
    API_TYPE = config.get('API', 'api_type', fallback='OpenAI API')
    API_KEY = config.get('API', 'api_key', fallback='')
    API_URL = config.get('API', 'api_url', fallback='')
    
    # 基本设置
    LANGUAGE = config.get('Settings', 'language', fallback='中文')
    FILE_OPERATION = config.get('Settings', 'file_operation', fallback='copy')
    SUBFOLDER_MODE = config.get('Settings', 'subfolder_mode', fallback='whole')
    
    # 模型设置
    IMAGE_MODEL = config.get('Settings', 'image_analysis_model', fallback='Pro/Qwen/Qwen2-VL-7B-Instruct')
    FILE_MODEL = config.get('Settings', 'file_analysis_model', fallback='deepseek-ai/DeepSeek-R1-Distill-Qwen-7B')
    DECISION_MODEL = config.get('Settings', 'decision_model', fallback='deepseek-ai/DeepSeek-R1-Distill-Qwen-32B')
    
    # 视频分析设置
    ENABLE_VIDEO_ANALYSIS = config.getboolean('Settings', 'enable_video_analysis', fallback=False)
    VIDEO_MODEL = config.get('Settings', 'video_analysis_model', fallback='Pro/Qwen/Qwen2-VL-7B-Instruct')
    
    # 性能设置
    THREAD_COUNT = config.getint('Settings', 'thread_count', fallback=8)
    
    return {
        'API_TYPE': API_TYPE,
        'API_KEY': API_KEY,
        'API_URL': API_URL,
        'FILE_OPERATION': FILE_OPERATION,
        'IMAGE_MODEL': IMAGE_MODEL,
        'FILE_MODEL': FILE_MODEL,
        'DECISION_MODEL': DECISION_MODEL,
        'ENABLE_VIDEO_ANALYSIS': ENABLE_VIDEO_ANALYSIS,
        'VIDEO_MODEL': VIDEO_MODEL,
        'LANGUAGE': LANGUAGE,
        'SUBFOLDER_MODE': SUBFOLDER_MODE,
        'THREAD_COUNT': THREAD_COUNT  # 添加到返回字典中
    }

# 加载配置
config_dict = load_config()

# 导出配置变量
API_TYPE = config_dict['API_TYPE']
API_KEY = config_dict['API_KEY']
API_URL = config_dict['API_URL']
FILE_OPERATION = config_dict['FILE_OPERATION']
IMAGE_MODEL = config_dict['IMAGE_MODEL']
FILE_MODEL = config_dict['FILE_MODEL']
DECISION_MODEL = config_dict['DECISION_MODEL']
ENABLE_VIDEO_ANALYSIS = config_dict['ENABLE_VIDEO_ANALYSIS']
VIDEO_MODEL = config_dict['VIDEO_MODEL']
LANGUAGE = config_dict['LANGUAGE']
SUBFOLDER_MODE = config_dict['SUBFOLDER_MODE']
THREAD_COUNT = config_dict['THREAD_COUNT']  # 导出线程数变量

# 子文件夹处理模式常量
SUBFOLDER_MODE_WHOLE = 'whole'  # 整个处理：将子文件夹作为整体进行分类
SUBFOLDER_MODE_EXTRACT_ALL = 'extract_all'  # 全部解体：将文件夹中所有文件视为独立文件
SUBFOLDER_MODE_EXTRACT_PARTIAL = 'extract_partial'  # 部分提取：分析文件夹结构，提取格格不入的文件
