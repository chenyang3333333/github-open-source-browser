import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ICON_PATH = ROOT / 'github_open_source_browser' / 'app.ico'
SPEC_PATH = ROOT / 'GitHub开源浏览器.spec'
BUILD_ENV_ROOT = Path(r'D:\开发环境\github-open-source-browser-build')
BUILD_PYTHON = BUILD_ENV_ROOT / 'Scripts' / 'python.exe'
MIN_PYINSTALLER_VERSION = (6, 22, 0)


def run_app():
    subprocess.run([sys.executable, '-m', 'github_open_source_browser'], cwd=ROOT, check=True)


def _resolve_build_python():
    if not BUILD_PYTHON.is_file():
        raise FileNotFoundError(
            f'找不到兼容的打包环境：{BUILD_PYTHON}。'
            f'请先在 {BUILD_ENV_ROOT} 中安装 PyInstaller 6.22.2。'
        )
    return BUILD_PYTHON


def _get_pyinstaller_version(build_python):
    result = subprocess.run(
        [str(build_python), '-m', 'PyInstaller', '--version'],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
    )
    version_text = result.stdout.strip().splitlines()[-1]
    try:
        return tuple(int(part) for part in version_text.split('.')[:3])
    except ValueError as exc:
        raise RuntimeError(f'无法识别 PyInstaller 版本：{version_text}') from exc


def build_exe():
    if not ICON_PATH.is_file():
        raise FileNotFoundError(f'找不到应用图标：{ICON_PATH}')
    if not SPEC_PATH.is_file():
        raise FileNotFoundError(f'找不到正式打包规格：{SPEC_PATH}')

    build_python = _resolve_build_python()
    pyinstaller_version = _get_pyinstaller_version(build_python)
    if pyinstaller_version < MIN_PYINSTALLER_VERSION:
        required = '.'.join(str(part) for part in MIN_PYINSTALLER_VERSION)
        actual = '.'.join(str(part) for part in pyinstaller_version)
        raise RuntimeError(f'PyInstaller 版本过低：当前为 {actual}，至少需要 {required}')

    dist_dir = ROOT / 'dist'
    build_dir = ROOT / 'build'
    subprocess.run(
        [
            str(build_python),
            '-m',
            'PyInstaller',
            '--noconfirm',
            '--clean',
            '--distpath',
            str(dist_dir),
            '--workpath',
            str(build_dir),
            str(SPEC_PATH),
        ],
        cwd=ROOT,
        check=True,
    )

    exe_src = dist_dir / 'GitHub开源浏览器.exe'
    exe_dst = ROOT / 'GitHub开源浏览器.exe'
    if not exe_src.is_file():
        raise FileNotFoundError(f'打包完成但没有找到输出文件：{exe_src}')

    try:
        shutil.copy2(exe_src, exe_dst)
    except PermissionError as exc:
        raise PermissionError(
            f'无法替换正在使用中的程序：{exe_dst}。请先关闭旧程序后重新打包。'
        ) from exc
    finally:
        shutil.rmtree(dist_dir, ignore_errors=True)
        shutil.rmtree(build_dir, ignore_errors=True)

    print(f'打包完成：{exe_dst}')


def main():
    parser = argparse.ArgumentParser(description='桌面程序启动与打包脚本')
    parser.add_argument('--run', action='store_true', help='运行桌面程序')
    parser.add_argument('--buildexe', action='store_true', help='使用兼容环境生成 exe')
    args = parser.parse_args()

    if args.run:
        run_app()
    elif args.buildexe:
        build_exe()
    else:
        run_app()


if __name__ == '__main__':
    main()
