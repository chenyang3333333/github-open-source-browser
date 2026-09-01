import math
import struct
import zlib
from pathlib import Path

输出路径 = Path('github_open_source_browser/app.ico')
尺寸列表 = (16, 32, 48, 256)


def 像素颜色(x, y, 大小):
    # 使用四倍采样生成简单的抗锯齿图标。
    采样数 = 4
    半径 = 大小 * 0.18
    背景颜色 = (9, 105, 218, 255)
    白色 = (255, 255, 255, 255)
    透明 = (0, 0, 0, 0)
    总颜色 = [0, 0, 0, 0]
    for 采样_y in range(采样数):
        for 采样_x in range(采样数):
            点_x = x + (采样_x + 0.5) / 采样数
            点_y = y + (采样_y + 0.5) / 采样数
            到左 = 点_x
            到右 = 大小 - 点_x
            到上 = 点_y
            到下 = 大小 - 点_y
            在圆角矩形内 = min(到左, 到右, 到上, 到下) >= 0
            if 在圆角矩形内:
                角点_x = max(半径 - 到左, 0, 半径 - 到右)
                角点_y = max(半径 - 到上, 0, 半径 - 到下)
                if 角点_x * 角点_x + 角点_y * 角点_y > 半径 * 半径:
                    在圆角矩形内 = False
            颜色 = 透明
            if 在圆角矩形内:
                颜色 = 背景颜色
                圆心_x = 大小 * 0.46
                圆心_y = 大小 * 0.43
                外半径 = 大小 * 0.235
                内半径 = 大小 * 0.145
                距离 = math.hypot(点_x - 圆心_x, 点_y - 圆心_y)
                if 内半径 <= 距离 <= 外半径:
                    颜色 = 白色
                elif 点_x >= 大小 * 0.57 and 点_x <= 大小 * 0.80 and 点_y >= 大小 * 0.60 and 点_y <= 大小 * 0.83:
                    直线距离 = abs((点_y - 大小 * 0.60) - (点_x - 大小 * 0.57)) / math.sqrt(2)
                    if 直线距离 <= 大小 * 0.06:
                        颜色 = 白色
            for 索引 in range(4):
                总颜色[索引] += 颜色[索引]
    return tuple(round(颜色 / (采样数 * 采样数)) for 颜色 in 总颜色)


def 生成_png(大小):
    行数据 = bytearray()
    for y in range(大小):
        行数据.append(0)
        for x in range(大小):
            行数据.extend(像素颜色(x, y, 大小))

    def 数据块(类型, 内容):
        return struct.pack('>I', len(内容)) + 类型 + 内容 + struct.pack('>I', zlib.crc32(类型 + 内容) & 0xFFFFFFFF)

    头部 = struct.pack('>IIBBBBB', 大小, 大小, 8, 6, 0, 0, 0)
    return b'\x89PNG\r\n\x1a\n' + 数据块(b'IHDR', 头部) + 数据块(b'IDAT', zlib.compress(bytes(行数据), 9)) + 数据块(b'IEND', b'')


图像数据 = [生成_png(大小) for 大小 in 尺寸列表]
文件头 = struct.pack('<HHH', 0, 1, len(图像数据))
目录 = bytearray()
偏移量 = 6 + 16 * len(图像数据)
for 大小, 数据 in zip(尺寸列表, 图像数据):
    宽高字节 = 0 if 大小 == 256 else 大小
    目录.extend(struct.pack('<BBBBHHII', 宽高字节, 宽高字节, 0, 0, 1, 32, len(数据), 偏移量))
    偏移量 += len(数据)

输出路径.write_bytes(文件头 + bytes(目录) + b''.join(图像数据))
print(f'已生成图标：{输出路径.resolve()}')
