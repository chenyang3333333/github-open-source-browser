# GitHub 开源浏览器 — 启动与打包指南

## 快速启动

### 运行程序（开发模式）

```bash
python run_app.py --run
```

或直接：

```bash
python run_app.py
```

默认行为即运行桌面程序。

### 打包为 exe

```bash
python run_app.py --buildexe
```

打包完成后，exe 文件会输出到项目根目录：`GitHub开源浏览器.exe`

---

## 环境要求

### 运行环境

- Python 3.10+
- 依赖包：`pip install -r requirements.txt`

### 打包环境

打包需要独立的虚拟环境，路径固定为：

```
D:\开发环境\github-open-source-browser-build
```

**创建打包环境：**

```bash
python -m venv D:\开发环境\github-open-source-browser-build
D:\开发环境\github-open-source-browser-build\Scripts\pip install pyinstaller>=6.22.0
```

打包脚本会自动检测该环境中的 PyInstaller 版本，低于 6.22.0 会报错。

---

## 文件结构

```
github-open-source-browser/
├── run_app.py                          # 启动与打包脚本
├── requirements.txt                    # 运行依赖
├── GitHub开源浏览器.spec               # PyInstaller 打包规格
├── create_icon.py                      # 图标生成脚本
└── github_open_source_browser/         # 核心源码
    ├── __init__.py
    ├── __main__.py
    ├── main.py                         # 主程序（UI + 业务逻辑）
    ├── database.py                     # SQLite 数据库层
    ├── translator.py                   # 翻译模块（占位保护 + TC3 签名）
    ├── plugins.py                      # 插件管理器
    └── app.ico                         # 应用图标
```

---

## 常见问题

### 打包时报错"找不到兼容的打包环境"

检查 `D:\开发环境\github-open-source-browser-build` 是否存在且包含 PyInstaller。

### 打包时报错"PyInstaller 版本过低"

升级打包环境中的 PyInstaller：

```bash
D:\开发环境\github-open-source-browser-build\Scripts\pip install --upgrade pyinstaller>=6.22.0
```

### 打包时报错"无法替换正在使用中的程序"

关闭正在运行的 `GitHub开源浏览器.exe` 后重新打包。
