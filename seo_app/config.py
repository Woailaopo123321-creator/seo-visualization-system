"""应用配置。"""


class Config:
    """默认配置。JSON 中文输出在应用工厂里关闭 ASCII 转义。"""

    TESTING = False


class TestConfig(Config):
    """pytest 使用的配置。"""

    TESTING = True
