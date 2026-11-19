"""
生成离线仪表盘快照：mobile_dashboard_offline.html

用法：
    python scripts/export_offline.py [--base-url http://127.0.0.1:5000] [--out mobile_dashboard_offline.html]

读取与运行中服务相同的数据文件（SEO_DATA_FILE），渲染 /dashboard，
把 CSS / JS / 图标全部内联，生成一个可直接双击打开、可发给别人的单文件 HTML。
页面内链接会指向 --base-url（服务运行时点击可跳转回系统）。
"""

import argparse
import base64
import datetime as dt
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def export_offline(app, base_url: str = "http://127.0.0.1:5000") -> str:
    """渲染仪表盘并内联 CSS / JS / 图标，返回单文件 HTML（站内链接改为绝对地址）"""
    base_url = base_url.rstrip("/")
    with app.test_client() as client:
        html = client.get("/dashboard").get_data(as_text=True)
    static = app.static_folder

    def read(name):
        with open(os.path.join(static, name), "r", encoding="utf-8") as f:
            return f.read()

    html = re.sub(r'<link rel="stylesheet" href="/static/app\.css(\?v=\d+)?">',
                  lambda m: "<style>\n" + read("app.css") + "\n</style>", html)
    html = re.sub(r'<script src="/static/common\.js(\?v=\d+)?"></script>',
                  lambda m: "<script>\n" + read("common.js") + "\n</script>", html)
    icon = base64.b64encode(read("favicon.svg").encode()).decode()
    html = re.sub(r'href="/static/favicon\.svg(\?v=\d+)?"', f'href="data:image/svg+xml;base64,{icon}"', html)
    html = re.sub(r'(href|action)="/(?!/)', lambda m: f'{m.group(1)}="{base_url}/', html)
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    banner = (f'<div class="callout warn" style="font-size:12px;text-align:center">'
              f'📦 离线快照 · 生成于 {stamp} · 数据不会自动更新；运行 <code>python scripts/export_offline.py</code> 重新生成</div>')
    html = re.sub(r'<main class="app-main"[^>]*>', lambda m: m.group(0) + "\n" + banner, html, count=1)
    # 离线文件中写操作不可用，隐藏「添加任务」按钮
    html = html.replace("</head>", "<style>.add-btn{display:none}</style>\n</head>", 1)
    return html


def main() -> None:
    parser = argparse.ArgumentParser(description="生成离线仪表盘快照")
    parser.add_argument("--base-url", default="http://127.0.0.1:5000")
    parser.add_argument("--out", default=os.path.join(ROOT, "mobile_dashboard_offline.html"))
    args = parser.parse_args()
    from app import create_app
    html = export_offline(create_app(), args.base_url)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"已生成 {args.out}（{len(html) // 1024} KB）")


if __name__ == "__main__":
    main()
