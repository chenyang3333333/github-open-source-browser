# GitHub 开源浏览器

一款桌面应用程序，用于浏览 GitHub 热门开源项目，支持多语言翻译和项目收藏功能。

## 功能特性

- 浏览 GitHub 趋势项目和分类项目
- 多翻译服务支持（腾讯云、DeepL、Google、OpenAI 兼容接口、本地离线）
- 批量并发翻译优化（4线程）
- 本地翻译词典（1600+ 技术术语）
- 项目收藏和下载历史
- README 翻译和预览
- 多目标语言支持（简体中文、繁体中文、英语、日语、韩语等）

## 运行方式

### 源码运行

```bash
python run_app.py --run
```

### 打包 exe

```bash
python run_app.py --buildexe
```

## 依赖

- Python 3.11+
- PyQt6 >= 6.6.0
- requests >= 2.31.0
- markdown >= 3.5.2
- deep-translator >= 1.11.4
- beautifulsoup4 >= 4.12.0

## 项目结构

```
github-open-source-browser/
├── github_open_source_browser/    # 源代码
│   ├── __init__.py
│   ├── __main__.py
│   ├── app.ico
│   ├── database.py
│   ├── main.py
│   ├── plugins.py
│   └── translator.py
├── .gitignore
├── GitHub开源浏览器.spec          # 打包配置
├── requirements.txt               # 依赖列表
├── README.md
└── run_app.py                     # 启动/打包脚本
```

## 翻译服务配置

在设置中可配置以下翻译服务：

- **自动选择**：使用本地离线翻译
- **腾讯云翻译**：需要 SecretId 和 SecretKey
- **DeepL**：需要 API 密钥
- **Google Cloud**：需要 API 密钥
- **OpenAI 兼容接口**：支持 OpenAI、DeepSeek 等服务

## 许可证

MIT License
