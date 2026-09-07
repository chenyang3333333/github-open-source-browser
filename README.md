# GitHub 开源项目浏览器

一个基于 **Python + PyQt6** 的桌面应用，帮助你快速发现、浏览 GitHub 上的优质开源项目。支持按星星数量排序的「发现」页、GitHub 官方「趋势热榜」、领域分类浏览、多引擎智能翻译（项目名/简介/README）、离线缓存与收藏管理。

> 版本 v2.7.0 ｜ 开发日志见 [开发日志.md](./开发日志.md)

---

## 功能特性

### 🚀 发现开源项目（按星星排序，无上限加载）
- 启动自动从 GitHub Search API 拉取高星项目，**统一按星星数量降序**展示；星星为 0 或相同的项目按最近更新时间降序兜底。
- **滚动到底自动加载更多**：每页 50 条、无数量上限，直到 API 返回空数据或请求失败才停止，追加数据与已有列表排序完美衔接。

### 🔥 趋势热榜（GitHub 官方 Trending）
- 抓取 `github.com/trending` 官方榜单，展示当日/本周/本月新增星星、排名涨跌（🔺/🔻/🆕 标记）。
- 列表项翻译完成后**保留官方排名与涨跌前缀**，不会再被翻译结果覆盖成乱序。

### 🗂 领域分类浏览
- 内置 AI、前端、后端、移动端、DevOps、安全等分类：
  - **发现页**选中带语言映射的分类（如 AI → Python / Jupyter Notebook）→ 按 `language:A OR language:B` 重新搜索，只显示该领域项目并按星星排序（自动忽略顶部语言下拉，避免条件冲突）。
  - **趋势热榜**选中分类 → 按分类语言重新抓取对应 Trending 页面并合并去重，按今日新增星星重排名次。
  - 无语言映射的分类（如安全）自动本地过滤兜底，刷新后分类筛选仍然生效。

### 🌐 多引擎智能翻译（无需科学上网）
项目名称、简介、README 一键翻译成中文，回退链自动切换，总有一款可用：
- **LLM 大模型**（OpenAI 兼容接口，翻译质量最高）
- **腾讯云 TMT**（国内直连、免费额度）
- **Edge 微软翻译**（免 Key、国内直连）
- **Google / DeepL**（免费、需可访问外网）
- **本地术语词典**（1900+ 条，最终兜底，永不失败）

翻译结果走 **SQLite 缓存**（30 天 TTL），二次打开秒开、不重复请求 API；切换视图自动取消在途翻译，线程池不拥堵。

### ⚙️ 其他能力
- **项目详情页**：README 中文翻译、语言/Stars/Forks/更新日期、作者、下载镜像加速。
- **收藏夹 / 浏览历史 / 本地搜索**：数据保存在本地 SQLite，可离线回顾。
- **深色浅色主题**、中英文界面、窗口缩放自适应。
- **敏感配置本地加密**：GitHub Token、翻译 Key 使用 Windows DPAPI 加密落盘，内存保持明文。

---

## 界面截图

### 发现页（按星星排序 + 滚动加载更多）
![发现页](docs/screenshots/discover.png)

### 趋势热榜（官方排名 + 涨跌标记 + 中文翻译）
![趋势热榜](docs/screenshots/trending.png)

### 项目详情（README 中文翻译）
![项目详情](docs/screenshots/detail.png)

### 设置（翻译引擎 / 主题 / 语言）
![设置](docs/screenshots/settings.png)

---

## 快速开始

### 方式一：直接运行（推荐）
下载 `GitHub开源浏览器.exe`，双击即可运行。首次启动自动加载数据（约 10~15 秒），无需安装 Python。

### 方式二：源码运行
```bash
# 环境要求：Python 3.11+，PyQt6
pip install -r requirements.txt
python run_app.py --run
```

### 打包 exe（可选）
```bash
python run_app.py --buildexe
```

---

## 配置说明

首次运行后，配置文件与数据库保存在：
```
%APPDATA%\GitHubOpenSourceBrowser\
├── config.json            # 用户配置（Token/密钥经 DPAPI 加密）
├── app.db                 # 收藏/历史/翻译缓存等
└── translation_cache.json # 翻译缓存副本
```

可在设置界面配置：翻译引擎与回退链、翻译目标语言、GitHub Token、每页加载数量、主题与界面语言等。

---

## 项目结构

```
github_open_source_browser/
├── app.py                 # 应用入口
├── config.py              # 配置读写与 DPAPI 加密
├── main_window.py 入口     # 主窗口（发现/热榜/历史/仪表盘）
├── ui/
│   ├── main_window.py     # 主界面与全部交互逻辑
│   ├── settings_dialog.py # 设置对话框
│   └── widgets/           # 自定义组件
├── services/
│   ├── github_service.py  # GitHub API / Trending 抓取
│   ├── translation_service.py # 多引擎翻译 + 回退链
│   ├── translator.py      # 各翻译引擎实现 + 本地词典
│   └── ...
├── i18n/                  # 中英文界面文案
└── resources/             # 图标等资源
```

## 技术栈

- Python 3.11 + PyQt6（界面）、Requests（网络）、SQLite（存储）、PyInstaller（打包）
- GitHub REST API / Search API / Trending 页面解析
- 翻译：OpenAI 兼容接口、腾讯云 TMT、Edge 微软、Google、DeepL、本地词典

## 许可

仅供学习交流使用。项目数据来源于 GitHub 官方公开接口，请遵守 GitHub 服务条款。
