"""页面和 JSON 接口。"""

from .api import api_bp
from .pages import pages_bp

__all__ = ["api_bp", "pages_bp"]
