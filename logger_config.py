import logging
import os
import sys
# from pythonjsonlogger import jsonlogger # 移除此行，不再使用

# 定义日志文件路径
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "app.log")

def setup_logging():
    """
    设置应用程序的日志。
    日志将输出到控制台和文件，并使用普通文本格式。
    """
    # 确保日志目录存在
    os.makedirs(LOG_DIR, exist_ok=True)

    # 创建一个标准的日志格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(name)s - %(message)s' # 简化格式，移除了processd和threadd
    )

    # 获取根记录器
    # logging.basicConfig() 已经设置了一个默认的Handler
    # 移除所有现有的handler，避免重复日志输出
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # 设置根记录器的级别
    logging.root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    
    # 文件处理器
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=10 * 1024 * 1024, # 10 MB
        backupCount=5, # 保留5个备份文件
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logging.root.addHandler(file_handler)

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logging.root.addHandler(console_handler)

    # 捕获警告和异常
    logging.captureWarnings(True)

    # 示例日志
    # logging.info("日志系统初始化完成。")
    # logging.debug("这是一个调试信息。")
    # logging.warning("这是一个警告信息。")
    # logging.error("这是一个错误信息。")
    # try:
    #     1 / 0
    # except ZeroDivisionError:
    #     logging.exception("发生了一个异常！")

# 在模块导入时自动设置日志
if __name__ == '__main__':
    setup_logging()
    logging.info("日志系统在独立运行时初始化完成。")
    logging.warning("这是一个测试警告。")
    try:
        raise ValueError("这是一个测试错误。")
    except ValueError:
        logging.exception("捕获到测试异常。")
