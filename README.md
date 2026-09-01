# GitHub 开源浏览器

一款专为中文用户设计的 GitHub 开源项目浏览桌面应用，帮助开发者更便捷地发现、翻译和管理感兴趣的开源项目。

## 适用人群

- **中文开发者**：英文阅读有障碍，希望快速了解 GitHub 热门项目
- **开源爱好者**：想要发现和收藏优质开源项目
- **技术学习者**：寻找学习资源和项目灵感
- **团队协作**：需要快速评估和分享开源项目

## 主要功能

### 1. 项目浏览

- **趋势热榜**：查看 GitHub 每日/每周/每月热门项目
- **分类筛选**：按前端、后端、AI、移动开发、运维等分类浏览
- **编程语言**：按 Python、JavaScript、Rust 等语言筛选
- **项目详情**：查看 Star 数、Fork 数、描述、README 等完整信息

### 2. 智能翻译

- **多翻译服务支持**：
  - 本地离线翻译（1600+ 技术术语词典）
  - 腾讯云翻译
  - DeepL 翻译
  - Google Cloud 翻译
  - OpenAI 兼容接口（支持 DeepSeek、通义千问等）
- **批量并发翻译**：4 线程并发，快速翻译项目列表
- **Markdown 保护**：翻译时保留代码块、链接、格式
- **术语保护**：自动识别并保护技术术语（API、Repository 等）
- **多目标语言**：支持简体中文、繁体中文、英语、日语、韩语、法语、德语、西班牙语

### 3. 项目管理

- **收藏功能**：一键收藏感兴趣的项目
- **下载历史**：记录已下载的项目
- **本地数据库**：SQLite 存储，数据持久化

### 4. README 预览

- **Markdown 渲染**：完整渲染项目 README
- **图片加载**：支持加载 README 中的图片
- **翻译对照**：原文/译文切换查看

### 5. 用户体验

- **响应式布局**：支持窗口缩放
- **深色/浅色主题**：跟随系统或手动切换
- **启动优化**：可选跳过启动自动加载
- **代理支持**：支持系统代理和自定义代理

## 安装运行

### 方式一：直接运行 exe

下载 `GitHub开源浏览器.exe`，双击运行即可。

### 方式二：源码运行

```bash
# 安装依赖
pip install -r requirements.txt

# 运行程序
python run_app.py --run
```

### 方式三：打包 exe

```bash
python run_app.py --buildexe
```

## 翻译服务配置

在设置中可配置翻译服务：

| 服务 | 配置项 | 说明 |
|------|--------|------|
| 自动选择 | 无 | 使用本地离线翻译 |
| 腾讯云翻译 | SecretId, SecretKey | 需要腾讯云账号 |
| DeepL | API 密钥 | 支持免费/付费版 |
| Google Cloud | API 密钥 | 需要启用翻译 API |
| OpenAI 兼容 | API 地址, 密钥, 模型 | 支持 OpenAI、DeepSeek 等 |

## 技术栈

- **UI 框架**：PyQt6
- **网络请求**：requests
- **Markdown 渲染**：markdown
- **翻译服务**：deep-translator
- **HTML 解析**：beautifulsoup4
- **数据库**：SQLite

## 项目结构

```
github-open-source-browser/
├── github_open_source_browser/    # 源代码
│   ├── __init__.py
│   ├── __main__.py
│   ├── app.ico                    # 应用图标
│   ├── database.py                # 数据库操作
│   ├── main.py                    # 主程序逻辑
│   ├── plugins.py                 # 插件系统
│   └── translator.py              # 翻译模块
├── .gitignore
├── GitHub开源浏览器.spec          # PyInstaller 打包配置
├── requirements.txt               # Python 依赖
├── README.md                      # 项目说明
└── run_app.py                     # 启动/打包脚本
```

## 更新日志

### v2.1.0 (2026-09-01)

- 批量翻译并发优化（4 线程）
- 本地翻译词典扩充至 1600+ 术语
- 清理目录结构，移除不必要的文件
- 添加项目 README

### v2.0.0

- 多翻译服务支持
- 翻译缓存和重试机制
- Markdown 占位保护
- 术语表保护

## 许可证

MIT License

## 联系方式

如有问题或建议，欢迎提交 Issue。
