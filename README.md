# GitHub 开源浏览器

一款基于 PyQt6 的桌面应用，用于浏览和发现 GitHub 上的优质开源项目。

## 功能特性

- **项目发现**：搜索 GitHub 开源项目，浏览 Trending 热门榜单
- **智能翻译**：支持腾讯云、DeepL、Google Cloud、OpenAI 兼容接口等多翻译源
- **翻译质量保护**：Markdown 占位保护机制，代码块、URL、HTML 标签在翻译过程中不会被破坏
- **收藏管理**：收藏感兴趣的项目，支持标签分类
- **下载历史**：记录下载过的资源，方便回溯
- **镜像加速**：自动检测并选择最快的 GitHub 镜像源
- **插件扩展**：支持用户自定义翻译插件

## 快速开始

### 环境要求

- Python 3.10+
- Windows 10/11

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行程序

```bash
python run_app.py --run
```

### 打包为 exe

```bash
python run_app.py --buildexe
```

打包需要独立的 PyInstaller 环境，详见 [RUN_GUIDE.md](RUN_GUIDE.md)。

## 项目结构

```
github-open-source-browser/
├── run_app.py                          # 启动与打包脚本
├── requirements.txt                    # 运行依赖
├── GitHub开源浏览器.spec               # PyInstaller 打包规格
├── create_icon.py                      # 图标生成脚本
└── github_open_source_browser/         # 核心源码
    ├── main.py                         # 主程序（UI + 业务逻辑）
    ├── database.py                     # SQLite 数据库层
    ├── translator.py                   # 翻译模块（占位保护 + TC3 签名）
    ├── plugins.py                      # 插件管理器
    └── app.ico                         # 应用图标
```

## 技术栈

- **UI 框架**：PyQt6
- **数据存储**：SQLite（WAL 模式）
- **翻译服务**：腾讯云机器翻译（TC3 签名）、DeepL、Google Cloud Translation、OpenAI 兼容接口
- **网络请求**：requests
- **打包工具**：PyInstaller

## 翻译配置

程序支持多种翻译源，在设置页面配置：

| 翻译源 | 配置项 |
|--------|--------|
| 腾讯云 | SecretId + SecretKey（每月免费 500 万字符） |
| DeepL | API Key |
| Google Cloud | API Key |
| OpenAI 兼容 | API URL + API Key（支持 DeepSeek、通义千问等） |

## 开发说明

翻译相关逻辑已独立到 `translator.py` 模块，便于维护：

- `protect_markdown_blocks()` — 翻译前占位保护
- `restore_markdown_blocks()` — 翻译后还原
- `tc3_authorization()` — 腾讯云 TC3 签名计算

翻译缓存策略：
- TTL：30 天自动过期
- 总量上限：3000 条或 30MB，超限自动清理最旧 20%

## 许可证

MIT License
