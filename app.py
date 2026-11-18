"""SEO 学习可视化系统入口。

启动：``python app.py``
生产：``gunicorn -w 2 -b 0.0.0.0:5000 app:app``
"""

from seo_app import create_app

app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
