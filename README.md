<h1 align="center">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/discover.png">
      <img alt="GitHub 开源项目浏览器" src="docs/screenshots/discover.png" width="800">
    </picture>
    <br>
    GitHub 开源项目浏览器
    <br>
    <small>发现、浏览、翻译 GitHub 优质开源项目</small>
</h1>

<p align="center">
    <a href="https://www.python.org/downloads/" alt="Python version">
        <img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white"></a>
    <a href="https://pypi.org/project/PyQt6/" alt="PyQt6">
        <img src="https://img.shields.io/badge/PyQt6-6.5+-green?logo=qt&logoColor=white"></a>
    <a href="https://github.com/chenyang3333333/github-open-source-browser/blob/main/LICENSE" alt="License">
        <img src="https://img.shields.io/badge/License-MIT-yellow.svg"></a>
    <a href="https://github.com/chenyang3333333/github-open-source-browser/stargazers" alt="Stars">
        <img src="https://img.shields.io/github/stars/chenyang3333333/github-open-source-browser?style=social"></a>
    <a href="https://github.com/chenyang3333333/github-open-source-browser/network/members" alt="Forks">
        <img src="https://img.shields.io/github/forks/chenyang3333333/github-open-source-browser?style=social"></a>
</p>

<p align="center">
    <a href="#-快速开始"><strong>快速开始</strong></a>
    · <a href="#-界面截图"><strong>界面截图</strong></a>
    · <a href="#-功能特性"><strong>功能特性</strong></a>
    · <a href="#-配置说明"><strong>配置说明</strong></a>
    · <a href="#-技术栈"><strong>技术栈</strong></a>
</p>

---

一个基于 **Python + PyQt6** 的桌面应用，帮助你快速发现、浏览 GitHub 上的优质开源项目。支持按星星数量排序的「发现」页、GitHub 官方「趋势热榜」、领域分类浏览、多引擎智能翻译（项目名/简介/README）、离线缓存与收藏管理。

> **版本 v2.7.0** | 一个库，零妥协。极速加载，实时翻译，本地缓存。由开源爱好者为开源爱好者构建，每个人都能找到适合自己的功能。

```bash
# 直接运行（推荐）
下载 GitHub开源浏览器.exe，双击即可运行

# 或者源码运行
pip install -r requirements.txt
python run_app.py --run
```

---

## 🖥️ 界面截图

<table>
  <tr>
    <td width="50%">
      <h3>发现页</h3>
      <p>按星星排序 + 滚动加载更多 + 多引擎智能翻译</p>
      <img src="docs/screenshots/discover.png" alt="发现页" width="100%">
    </td>
    <td width="50%">
      <h3>趋势热榜</h3>
      <p>GitHub 官方排名 + 涨跌标记 + 中文翻译</p>
      <img src="docs/screenshots/trending.png" alt="趋势热榜" width="100%">
    </td>
  </tr>
  <tr>
    <td width="50%">
      <h3>项目详情</h3>
      <p>README 中文翻译 + 克隆/下载/收藏</p>
      <img src="docs/screenshots/detail.png" alt="项目详情" width="100%">
    </td>
    <td width="50%">
      <h3>设置</h3>
      <p>翻译引擎 / 主题 / 语言 / 镜像加速</p>
      <img src="docs/screenshots/settings.png" alt="设置" width="100%">
    </td>
  </tr>
</table>

---

## ✨ 功能特性

### 🔍 发现开源项目（按星星排序，无上限加载）

- 🚀 启动自动从 GitHub Search API 拉取高星项目，**统一按星星数量降序**展示；星星为 0 或相同的项目按最近更新时间降序兜底。
- 📜 **滚动到底自动加载更多**：每页 50 条、无数量上限，直到 API 返回空数据或请求失败才停止，追加数据与已有列表排序完美衔接。
- 🏷️ **领域分类浏览**：内置 AI、前端、后端、移动端、DevOps、安全等分类，按语言映射重新搜索，只显示该领域项目并按星星排序。

### 🔥 趋势热榜（GitHub 官方 Trending）

- 📊 抓取 `github.com/trending` 官方榜单，展示当日/本周/本月新增星星、排名涨跌（🔺/🔻/🆕 标记）。
- 🔄 列表项翻译完成后**保留官方排名与涨跌前缀**，不会再被翻译结果覆盖成乱序。
- 🗂️ 选中分类 → 按分类语言重新抓取对应 Trending 页面并合并去重，按今日新增星星重排名次。

### 🌐 多引擎智能翻译（无需科学上网）

项目名称、简介、README 一键翻译成中文，回退链自动切换，总有一款可用：

| 引擎 | 特点 | 需要 |
|------|------|------|
| **LLM 大模型** | 翻译质量最高 | OpenAI 兼容接口 |
| **腾讯云 TMT** | 国内直连、免费额度 | API Key |
| **Edge 微软翻译** | 免 Key、国内直连 | 无 |
| **Google / DeepL** | 免费 | 可访问外网 |
| **本地术语词典** | 1900+ 条，最终兜底，永不失败 | 无 |

- 💾 翻译结果走 **SQLite 缓存**（30 天 TTL），二次打开秒开、不重复请求 API。
- ⚡ 切换视图自动取消在途翻译，线程池不拥堵。

### ⚙️ 其他能力

- 📖 **项目详情页**：README 中文翻译、语言/Stars/Forks/更新日期、作者、下载镜像加速。
- ⭐ **收藏夹 / 浏览历史 / 本地搜索**：数据保存在本地 SQLite，可离线回顾。
- 🎨 **深色浅色主题**、中英文界面、窗口缩放自适应。
- 🔒 **敏感配置本地加密**：GitHub Token、翻译 Key 使用 Windows DPAPI 加密落盘，内存保持明文。
- 🪞 **镜像加速**：内置多个 GitHub 镜像源，解决国内访问慢的问题。
- 🔌 **插件系统**：支持自定义插件扩展功能。

---

## 🚀 快速开始

### 方式一：直接运行（推荐）

下载 `GitHub开源浏览器.exe`，双击即可运行。首次启动自动加载数据（约 10~15 秒），无需安装 Python。

### 方式二：源码运行

```bash
# 环境要求：Python 3.11+，PyQt6
git clone https://github.com/chenyang3333333/github-open-source-browser.git
cd github-open-source-browser
pip install -r requirements.txt
python run_app.py --run
```

### 打包 exe（可选）

```bash
python run_app.py --buildexe
```

---

## ⚙️ 配置说明

首次运行后，配置文件与数据库保存在：

```
%APPDATA%\GitHubOpenSourceBrowser\
├── config.json            # 用户配置（Token/密钥经 DPAPI 加密）
├── app.db                 # 收藏/历史/翻译缓存等
└── translation_cache.json # 翻译缓存副本
```

可在设置界面配置：翻译引擎与回退链、翻译目标语言、GitHub Token、每页加载数量、主题与界面语言等。

---

## 📁 项目结构

```
github_open_source_browser/
├── app.py                 # 应用入口
├── config.py              # 配置读写与 DPAPI 加密
├── database.py            # SQLite 数据库操作
├── translator.py          # 翻译管理器
├── plugins.py             # 插件系统
├── ui/
│   ├── main_window.py     # 主界面与全部交互逻辑
│   ├── settings_dialog.py # 设置对话框
│   ├── theme.py           # 主题管理
│   ├── loading.py         # 加载动画
│   └── enhancements.py    # UI 增强组件
├── services/
│   ├── github_service.py  # GitHub API / Trending 抓取
│   ├── translation_service.py # 多引擎翻译 + 回退链
│   └── http_client.py     # HTTP 客户端封装
└── i18n/                  # 中英文界面文案
    ├── zh_CN.json
    └── en_US.json
```

---

## 🛠️ 技术栈

| 组件 | 技术 |
|------|------|
| **界面** | Python 3.11 + PyQt6 |
| **网络** | Requests + 自定义 HTTP 客户端 |
| **存储** | SQLite（收藏/历史/翻译缓存） |
| **打包** | PyInstaller |
| **翻译** | OpenAI 兼容接口、腾讯云 TMT、Edge 微软、Google、DeepL、本地词典 |
| **数据源** | GitHub REST API / Search API / Trending 页面解析 |
| **加密** | Windows DPAPI（敏感配置本地加密） |

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建你的特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交你的改动 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开一个 Pull Request

---

## 📄 许可

本项目采用 [MIT 许可证](LICENSE) - 详见 LICENSE 文件。

仅供学习交流使用。项目数据来源于 GitHub 官方公开接口，请遵守 [GitHub 服务条款](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service)。

---

<p align="center">
    <b>如果觉得有用，请给个 ⭐ Star 支持一下！</b>
</p>
