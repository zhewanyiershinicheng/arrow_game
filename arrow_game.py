# -*- coding: utf-8 -*-
"""一箭又一箭 — 箭头解谜小游戏

规则：点击箭头，若其前进方向到棋盘边界之间无其他箭头，则飞出并消除；
若被阻挡，则消耗一次可失误次数。可失误次数为 0 后再错，本关失败。
地图按关卡难度随机生成，并用逆序构造 + 求解器保证有解。

"""

from __future__ import annotations

import array
import math
import os
import random
import sys
import threading
import time as _time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Tuple

import pygame

# ---------------------------------------------------------------------------
# 窗口 / 栅格
# ---------------------------------------------------------------------------
WINDOW_W, WINDOW_H = 900, 720
FPS = 60
CELL = 68
GRID_N = 5
TOTAL_LEVELS = 4
MISSES_PER_LEVEL = 3

# ---------------------------------------------------------------------------
# Stellar Light 设计令牌
# ---------------------------------------------------------------------------
C_BG = (244, 246, 248)          # #F4F6F8
C_BG_DOT = (228, 233, 239)      # 点阵
C_CARD = (255, 255, 255)        # #FFFFFF
C_CARD_SOFT = (248, 250, 252)   # #F8FAFC
C_BORDER = (229, 234, 240)      # #E5EAF0
C_BORDER_STRONG = (203, 213, 225)
C_INK = (31, 41, 55)            # #1F2937
C_MUTED = (107, 114, 128)       # #6B7280
C_FAINT = (156, 163, 175)
C_PRIMARY = (59, 130, 246)      # #3B82F6
C_PRIMARY_SOFT = (235, 242, 255)  # #EBF2FF
C_PRIMARY_DEEP = (37, 99, 235)
C_SUCCESS = (34, 197, 94)       # #22C55E
C_SUCCESS_SOFT = (240, 253, 244)
C_WARN = (245, 158, 11)         # #F59E0B
C_WARN_SOFT = (255, 251, 235)
C_DANGER = (239, 68, 68)        # #EF4444
C_DANGER_SOFT = (254, 242, 242)
C_SHADOW = (15, 23, 42)

# 箭头（浅底加深，保证对比度）
ARROW_COLORS = {
    0: (245, 158, 11),   # 上 琥珀
    1: (14, 165, 233),   # 下 天蓝
    2: (139, 92, 246),   # 左 紫
    3: (234, 88, 12),    # 右 橙红
}
ARROW_STROKE = (55, 65, 81)

DIR_NAME = {0: "上", 1: "下", 2: "左", 3: "右"}
DIR_DELTA = {0: (-1, 0), 1: (1, 0), 2: (0, -1), 3: (0, 1)}
DIR_CHAR = {0: "U", 1: "D", 2: "L", 3: "R"}
CHAR_DIR = {"U": 0, "D": 1, "L": 2, "R": 3}
CN_NUM = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]

HUD_H = 88
BOTTOM_H = 76
BANNER_H = 40
BOARD_AREA_TOP = HUD_H + BANNER_H + 10
BOARD_AREA_BOTTOM = WINDOW_H - BOTTOM_H - 10

FLY_SPEED = 1100.0
BUMP_AMPLITUDE = 16.0
BUMP_DURATION = 0.55
SHAKE_AMPLITUDE = 7.0

RESULT_PANEL_W = 460
RESULT_PANEL_H = 430
RADIUS = 12
RADIUS_SM = 8
RADIUS_BTN = 10
TRANS_OUT = 0.16
TRANS_IN = 0.20

# 逻辑配色别名（测试兼容）
COLOR_BG = C_BG
COLOR_TEXT = C_INK
COLOR_TEXT_DIM = C_MUTED
COLOR_ACCENT = C_PRIMARY
COLOR_SUCCESS = C_SUCCESS
COLOR_DANGER = C_DANGER
COLOR_WARN = C_WARN
MISSES_LABEL = "可失误"


class State(Enum):
    MENU = auto()
    MODE_RULES = auto()   # 高难模式规则说明弹窗
    PLAYING = auto()
    WIN = auto()
    FAIL = auto()
    ALL_CLEAR = auto()


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------
@dataclass
class Arrow:
    row: int
    col: int
    direction: int
    alive: bool = True
    anim: str = ""
    anim_t: float = 0.0
    ox: float = 0.0
    oy: float = 0.0
    alpha: float = 255.0
    flash: float = 0.0
    scale: float = 1.0
    enter: float = 0.0  # 0→1 入场进度


@dataclass
class FloatText:
    text: str
    x: float
    y: float
    color: Tuple[int, int, int]
    t: float = 0.0
    life: float = 0.9
    size: int = 18


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    color: Tuple[int, int, int]
    size: float = 3.0
    kind: str = "spark"  # spark | ring | confetti
    rot: float = 0.0
    vr: float = 0.0


@dataclass
class Button:
    rect: pygame.Rect
    label: str
    action: str
    color: Tuple[int, int, int] = C_PRIMARY
    hover: bool = False
    kind: str = "primary"  # primary | secondary | danger | warn
    hover_t: float = 0.0   # 悬停插值 0→1
    press: float = 0.0     # 按压 0→1→0
    enter: float = 0.0     # 入场 0→1


@dataclass
class Game:
    state: State = State.MENU
    level_index: int = 0
    rows: int = GRID_N
    cols: int = GRID_N
    arrows: List[Arrow] = field(default_factory=list)
    misses_left: int = MISSES_PER_LEVEL
    misses_max: int = MISSES_PER_LEVEL
    buttons: List[Button] = field(default_factory=list)
    floats: List[FloatText] = field(default_factory=list)
    particles: List[Particle] = field(default_factory=list)
    shake: float = 0.0
    hit_flash: float = 0.0
    banner: str = ""
    banner_timer: float = 0.0
    board_origin: Tuple[int, int] = (0, 0)
    pending_fail: bool = False
    pending_win: bool = False
    level_name: str = ""
    level_desc: str = ""
    level_grid: List[str] = field(default_factory=list)
    arrow_count: int = 0
    level_enter: float = 0.0   # 关卡入场 0→1
    modal_t: float = 0.0       # 结果弹层入场
    screen_t: float = 1.0      # 当前界面内容入场
    trans_dir: int = 0         # 0无 1淡出 2淡入
    trans_t: float = 0.0
    trans_pending: Optional[str] = None
    r_edge: bool = False
    key_r_down: bool = False
    # 计时与星级评价（整局）
    run_time: float = 0.0
    level_time: float = 0.0
    run_total_misses: int = 0
    run_had_fail: bool = False
    stars: int = 0
    final_time: float = 0.0
    stars_reveal: float = 0.0
    hard_mode: bool = False
    rules_t: float = 0.0          # 高难规则弹窗入场 0→1
    star_burst: float = 0.0       # 星星高亮闪光
    # 每颗星：弹出进度 / 摆动 / 落定
    star_anim: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    star_pop: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    star_wob: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    # 星星依次弹出动画（0..1 每颗独立进度）
    star_anim: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    star_t: float = 0.0
    # 关卡入场横幅动画
    banner_scale: float = 1.0
    banner_offset_y: float = 0.0
    # 星级依次入场动画
    stars_reveal: float = 0.0   # 0→ 超过3
    # 入场横幅动画进度
    banner_age: float = 0.0
    banner_life: float = 0.0
    banner_kind: str = "info"   # info | level

    def alive_arrows(self) -> List[Arrow]:
        return [a for a in self.arrows if a.alive]


# ---------------------------------------------------------------------------
# 音效 / BGM（本地 assets/sfx，缺失时自动生成）
# ---------------------------------------------------------------------------
_SFX_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "sfx")
_SOUNDS: dict = {}
_sound_ready = False
_sound_failed = False
_bgm_path: Optional[str] = None
_bgm_on = False
_muted = False
_SFX_VOL = 0.55
_BGM_VOL = 0.20

class AudioAssetsMissingError(Exception):
    def __init__(self, missing):
        self.missing = missing
        super().__init__(f"缺少音频资源: {', '.join(missing)}")

def _ensure_audio_assets() -> str:
    """确保 assets/sfx 下有 wav"""
    os.makedirs(_SFX_DIR, exist_ok=True)
    needed = [
        "click.wav", "start.wav", "fly.wav", "bump.wav",
        "clear.wav", "win.wav", "fail.wav", "stars.wav", "star_pop.wav", "bgm.wav",
    ]
    missing = [n for n in needed if not os.path.isfile(os.path.join(_SFX_DIR, n))]
    if missing:
        raise AudioAssetsMissingError(missing)
    return _SFX_DIR


def init_sounds() -> bool:
    """初始化混音器并加载音效/BGM。失败时静默降级。"""
    global _sound_ready, _SOUNDS, _sound_failed, _bgm_path
    if _sound_ready:
        return True
    if os.environ.get("ARROW_GAME_SILENT") == "1":
        _sound_failed = True
        return False
    try:
        if not pygame.mixer.get_init():
            # 先声明参数，降低 Windows 上探测声卡卡死概率
            try:
                pygame.mixer.pre_init(22050, -16, 2, 512)
            except Exception:
                pass
            pygame.mixer.init(22050, -16, 2, 512)
        _ensure_audio_assets()
        names = ["click", "start", "fly", "bump", "clear", "win", "fail", "stars", "star_pop"]
        _SOUNDS = {}
        for name in names:
            path = os.path.join(_SFX_DIR, f"{name}.wav")
            if os.path.isfile(path):
                try:
                    snd = pygame.mixer.Sound(path)
                    snd.set_volume(_SFX_VOL)
                    _SOUNDS[name] = snd
                except Exception:
                    continue
        bgm = os.path.join(_SFX_DIR, "bgm.wav")
        if os.path.isfile(bgm):
            _bgm_path = bgm
        _sound_ready = len(_SOUNDS) > 0 or bool(_bgm_path)
        _sound_failed = not _sound_ready
        return _sound_ready
    except Exception:
        _SOUNDS = {}
        _bgm_path = None
        _sound_ready = False
        _sound_failed = True
        return False


def start_sounds_async() -> None:
    """窗口打开后初始化音频；主线程内限时尝试，避免卡死。"""
    global _sound_failed
    if os.environ.get("ARROW_GAME_SILENT") == "1":
        _sound_failed = True
        return
    # 不再默认强制 dummy；若显式要求静音才跳过
    if os.environ.get("ARROW_GAME_ENABLE_SOUND") == "0":
        _sound_failed = True
        return

    def _worker():
        init_sounds()

    th = threading.Thread(target=_worker, daemon=True)
    th.start()
    th.join(timeout=1.8)
    if th.is_alive() and not _sound_ready:
        # 初始化疑似阻塞：后续不再重试
        _sound_failed = True


def play_sound(name: str) -> None:
    """播放音效；未就绪/静音时立即返回，不触发 mixer.init。"""
    global _sound_failed
    if _muted or _sound_failed or not _sound_ready:
        return
    snd = _SOUNDS.get(name)
    if snd is None:
        return
    try:
        snd.play()
    except Exception:
        _sound_failed = True


def play_bgm() -> None:
    global _bgm_on, _sound_failed
    if _muted or _sound_failed or not _bgm_path:
        return
    try:
        if not pygame.mixer.get_init():
            return
        pygame.mixer.music.load(_bgm_path)
        pygame.mixer.music.set_volume(_BGM_VOL)
        pygame.mixer.music.play(-1)
        _bgm_on = True
    except Exception:
        _bgm_on = False


def stop_bgm() -> None:
    global _bgm_on
    try:
        pygame.mixer.music.stop()
    except Exception:
        pass
    _bgm_on = False


def set_muted(flag: bool) -> None:
    global _muted
    _muted = flag
    try:
        if flag:
            pygame.mixer.music.set_volume(0.0)
        else:
            pygame.mixer.music.set_volume(_BGM_VOL if _bgm_on else 0.0)
            if not _bgm_on:
                play_bgm()
    except Exception:
        pass


def toggle_mute() -> bool:
    set_muted(not _muted)
    return _muted


def format_mmss(seconds: float) -> str:
    s = max(0, int(seconds))
    return f"{s // 60:02d}:{s % 60:02d}"


def compute_stars(total_misses: int, had_fail: bool) -> int:
    """剧情模式（四关全通）星级。"""
    if had_fail:
        return 1
    if total_misses <= 0:
        return 3
    if total_misses <= 4:
        return 2
    return 1


def compute_stars_hard(misses: int, elapsed: float) -> int:
    """高难模式：三星零失误且<60s；二星失误≤3且<60s；否则一星。"""
    under = elapsed < 60.0
    if misses <= 0 and under:
        return 3
    if misses <= 3 and under:
        return 2
    return 1


# ---------------------------------------------------------------------------
# 玩法：生成 / 判定（逻辑不变）
# ---------------------------------------------------------------------------
def arrow_count_for_level(index: int, hard: bool = False) -> int:
    if hard:
        return GRID_N * GRID_N  # 铺满整个棋盘
    return 5 + index * 2


def level_title(index: int) -> str:
    cn = CN_NUM[index] if index < len(CN_NUM) else str(index + 1)
    return f"第{cn}关"


def parse_level(grid: List[str]) -> Tuple[int, int, List[Arrow]]:
    rows = len(grid)
    cols = max(len(r) for r in grid) if grid else GRID_N
    arrows: List[Arrow] = []
    for r, line in enumerate(grid):
        for c, ch in enumerate(line):
            if ch in CHAR_DIR:
                arrows.append(Arrow(row=r, col=c, direction=CHAR_DIR[ch]))
    return rows, cols, arrows


def is_blocked(arrows: List[Arrow], target: Arrow, rows: int, cols: int) -> bool:
    dr, dc = DIR_DELTA[target.direction]
    r, c = target.row + dr, target.col + dc
    alive = {(a.row, a.col) for a in arrows if a.alive and a is not target}
    while 0 <= r < rows and 0 <= c < cols:
        if (r, c) in alive:
            return True
        r += dr
        c += dc
    return False


def solve_level(grid: List[str]) -> Optional[List[Tuple[int, int, int]]]:
    rows, cols, arrows = parse_level(grid)

    class _A:
        def __init__(self, row, col, direction, alive=True):
            self.row = row
            self.col = col
            self.direction = direction
            self.alive = alive

    objs = [_A(a.row, a.col, a.direction) for a in arrows]
    order: List[Tuple[int, int, int]] = []
    progress = True
    while any(o.alive for o in objs):
        if not progress:
            return None
        progress = False
        for o in objs:
            if not o.alive:
                continue
            if not is_blocked(objs, o, rows, cols):
                o.alive = False
                order.append((o.row, o.col, o.direction))
                progress = True
                break
    return order


def grid_from_arrows(arrows: List[Arrow], rows: int, cols: int) -> List[str]:
    board = [["." for _ in range(cols)] for _ in range(rows)]
    for a in arrows:
        board[a.row][a.col] = DIR_CHAR[a.direction]
    return ["".join(row) for row in board]


def _path_contains(blocker: Arrow, target: Arrow, rows: int, cols: int) -> bool:
    dr, dc = DIR_DELTA[target.direction]
    r, c = target.row + dr, target.col + dc
    while 0 <= r < rows and 0 <= c < cols:
        if r == blocker.row and c == blocker.col:
            return True
        r += dr
        c += dc
    return False


def _try_reverse_construct(rows: int, cols: int, n: int) -> Optional[List[str]]:
    occupied = set()
    placed: List[Arrow] = []
    all_cells = [(r, c) for r in range(rows) for c in range(cols)]
    if n > len(all_cells):
        n = len(all_cells)
    for _ in range(n):
        free_cells = [(r, c) for r, c in all_cells if (r, c) not in occupied]
        random.shuffle(free_cells)
        free_cells = free_cells[: min(20, len(free_cells))]
        dirs = [0, 1, 2, 3]
        random.shuffle(dirs)
        best: List[Tuple[int, int, int, int]] = []
        for r, c in free_cells:
            for d in dirs:
                trial = Arrow(row=r, col=c, direction=d)
                if is_blocked(placed, trial, rows, cols):
                    continue
                score = 0
                for p in placed:
                    if _path_contains(trial, p, rows, cols):
                        score += 2
                    if _path_contains(p, trial, rows, cols):
                        score += 1
                best.append((score, r, c, d))
        if not best:
            return None
        best.sort(key=lambda x: x[0], reverse=True)
        top = best[0][0]
        pool = [item for item in best if item[0] >= max(0, top - 1)][:8]
        _, r, c, d = random.choice(pool)
        placed.append(Arrow(row=r, col=c, direction=d))
        occupied.add((r, c))
    return grid_from_arrows(placed, rows, cols)


def generate_solvable_grid(
    level_index: int,
    rows: int = GRID_N,
    cols: int = GRID_N,
    hard: bool = False,
) -> Tuple[List[str], int]:
    target = min(arrow_count_for_level(level_index, hard=hard), rows * cols)
    if hard:
        # 铺满棋盘：优先满格，失败再降
        tries_list = [(target, 30), (target - 1, 12), (20, 10), (16, 8)]
    else:
        tries_list = [(target, 24), (target - 1, 12), (max(4, target - 2), 8)]
    for n, tries in tries_list:
        if n < 4:
            continue
        for _ in range(tries):
            grid = _try_reverse_construct(rows, cols, n)
            if not grid:
                continue
            order = solve_level(grid)
            total = sum(ch in CHAR_DIR for row in grid for ch in row)
            if order and len(order) == total:
                return grid, total
    fallback = ["R.R..", "..U..", ".....", "L...D", "....."]
    return fallback, sum(ch in CHAR_DIR for row in fallback for ch in row)


def load_level(game: Game, index: int) -> None:
    hard = bool(getattr(game, "hard_mode", False))
    grid, arrow_n = generate_solvable_grid(index, hard=hard)
    rows, cols, arrows = parse_level(grid)
    game.level_index = index
    game.rows = rows
    game.cols = cols
    game.arrows = arrows
    game.level_grid = grid
    game.arrow_count = arrow_n
    if hard:
        game.level_name = "高难挑战"
        game.level_desc = f"高难 · 满盘 {arrow_n} 箭 · 目标 < 60s"
    else:
        game.level_name = level_title(index)
        game.level_desc = f"随机地图 · {arrow_n} 箭头 · 可失误 {MISSES_PER_LEVEL} 次"
    game.misses_max = MISSES_PER_LEVEL
    game.misses_left = MISSES_PER_LEVEL
    game.floats.clear()
    game.particles.clear()
    game.shake = 0.0
    game.hit_flash = 0.0
    banner_txt = f"高难挑战 · {arrow_n} 支箭头" if hard else f"{game.level_name} · {arrow_n} 支箭头"
    set_banner(game, banner_txt, 1.4)
    game.pending_fail = False
    game.pending_win = False
    game.modal_t = 0.0
    game.level_enter = 0.0
    game.level_time = 0.0
    game.stars_reveal = 0.0
    game.state = State.PLAYING
    # 错落入场：按格子距离设置延迟
    for a in game.arrows:
        a.enter = 0.0
        a.scale = 0.3
        a.alpha = 0.0
    layout_board(game)


def layout_board(game: Game) -> None:
    board_w = game.cols * CELL
    board_h = game.rows * CELL
    area_h = BOARD_AREA_BOTTOM - BOARD_AREA_TOP
    ox = (WINDOW_W - board_w) // 2
    oy = BOARD_AREA_TOP + max(0, (area_h - board_h) // 2)
    game.board_origin = (ox, oy)


def cell_rect(game: Game, row: int, col: int) -> pygame.Rect:
    ox, oy = game.board_origin
    return pygame.Rect(ox + col * CELL, oy + row * CELL, CELL, CELL)


# ---------------------------------------------------------------------------
# 字体
# ---------------------------------------------------------------------------
_font_cache = {}


def get_font(size: int, bold: bool = False) -> pygame.font.Font:
    if not pygame.font.get_init():
        pygame.font.init()
    key = (size, bold)
    if key in _font_cache:
        return _font_cache[key]
    font = None
    font_files = (
        [r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\msyh.ttc"]
        if bold
        else [
            r"C:\Windows\Fonts\msyh.ttc",
            r"C:\Windows\Fonts\msyhbd.ttc",
            r"C:\Windows\Fonts\simhei.ttf",
            r"C:\Windows\Fonts\Deng.ttf",
        ]
    )
    for path in font_files:
        try:
            if os.path.isfile(path):
                font = pygame.font.Font(path, size)
                break
        except Exception:
            continue
    if font is None:
        font = pygame.font.Font(None, size)
    try:
        font.set_bold(bold)
    except Exception:
        pass
    _font_cache[key] = font
    return font


def draw_text(
    surf: pygame.Surface,
    text: str,
    x: int,
    y: int,
    size: int,
    color=C_INK,
    center: bool = False,
    bold: bool = False,
) -> pygame.Rect:
    font = get_font(size, bold)
    img = font.render(text, True, color)
    rect = img.get_rect()
    if center:
        rect.center = (x, y)
    else:
        rect.topleft = (x, y)
    surf.blit(img, rect)
    return rect


def draw_text_center(surf, text, cx, cy, size, color=C_INK, bold=False) -> pygame.Rect:
    return draw_text(surf, text, cx, cy, size, color, center=True, bold=bold)


# ---------------------------------------------------------------------------
# Stellar 绘制原语（卡片阴影 / 点阵 / 胶囊）
# ---------------------------------------------------------------------------
_dot_cache: dict = {}
_shadow_cache: dict = {}


def draw_dot_grid(surf: pygame.Surface) -> None:
    """浅色文档站式点阵底纹。"""
    key = (surf.get_width(), surf.get_height())
    layer = _dot_cache.get(key)
    if layer is None:
        layer = pygame.Surface(key, pygame.SRCALPHA)
        for x in range(24, key[0], 22):
            for y in range(24, key[1], 22):
                layer.set_at((x, y), (*C_BG_DOT, 90))
        _dot_cache[key] = layer
    surf.blit(layer, (0, 0))


def draw_card(
    surf: pygame.Surface,
    rect: pygame.Rect,
    fill=C_CARD,
    border=C_BORDER,
    radius: int = RADIUS,
    shadow: bool = True,
) -> None:
    if shadow:
        key = (rect.w, rect.h, radius)
        sh = _shadow_cache.get(key)
        if sh is None:
            pad = 6
            sh = pygame.Surface((rect.w + pad * 2, rect.h + pad * 2), pygame.SRCALPHA)
            for i in range(4, 0, -1):
                alpha = 10 + i * 4
                r = pygame.Rect(pad - i, pad - i + 2, rect.w + i * 2, rect.h + i * 2)
                pygame.draw.rect(sh, (*C_SHADOW, alpha), r, border_radius=radius + i)
            _shadow_cache[key] = sh
        surf.blit(sh, (rect.x - 6, rect.y - 6))
    pygame.draw.rect(surf, fill, rect, border_radius=radius)
    if border:
        pygame.draw.rect(surf, border, rect, width=1, border_radius=radius)


def draw_pill(
    surf: pygame.Surface,
    rect: pygame.Rect,
    fill,
    border=None,
) -> None:
    pygame.draw.rect(surf, fill, rect, border_radius=rect.h // 2)
    if border:
        pygame.draw.rect(surf, border, rect, width=1, border_radius=rect.h // 2)


def mix(c1, c2, t: float):
    t = max(0.0, min(1.0, t))
    return (
        int(c1[0] * (1 - t) + c2[0] * t),
        int(c1[1] * (1 - t) + c2[1] * t),
        int(c1[2] * (1 - t) + c2[2] * t),
    )


# ---------------------------------------------------------------------------
# 箭头绘制
# ---------------------------------------------------------------------------
def arrow_polygon(direction: int, cx: float, cy: float, scale: float = 1.0) -> List[Tuple[float, float]]:
    s = 16 * scale
    local = [
        (-s * 1.05, -s * 0.28),
        (s * 0.15, -s * 0.28),
        (s * 0.15, -s * 0.62),
        (s * 1.05, 0.0),
        (s * 0.15, s * 0.62),
        (s * 0.15, s * 0.28),
        (-s * 1.05, s * 0.28),
    ]

    def rot(pt, d):
        x, y = pt
        if d == 3:
            return x, y
        if d == 2:
            return -x, -y
        if d == 0:
            return y, -x
        return -y, x

    return [(cx + x, cy + y) for (x, y) in (rot(p, direction) for p in local)]


def draw_arrow(surf: pygame.Surface, arrow: Arrow, rect: pygame.Rect, alpha: float = 255.0) -> None:
    cx = rect.centerx + arrow.ox
    cy = rect.centery + arrow.oy
    color = ARROW_COLORS[arrow.direction]
    if arrow.flash > 0:
        color = mix(color, C_DANGER, min(1.0, arrow.flash))
    scale = max(0.15, arrow.scale)
    poly = arrow_polygon(arrow.direction, cx, cy, scale)
    a = max(0, min(255, int(alpha)))
    if arrow.anim == "flying":
        a = max(0, min(255, int(arrow.alpha)))

    # 飞出拖尾（小表面，避免每帧全屏透明层）
    if arrow.anim == "flying" and a > 8:
        pad = int(80 * scale) + 20
        tw = int(abs(arrow.ox) + pad * 2)
        th = int(abs(arrow.oy) + pad * 2)
        tw = max(48, min(tw, WINDOW_W))
        th = max(48, min(th, WINDOW_H))
        ox0 = int(min(cx, cx - arrow.ox) - pad)
        oy0 = int(min(cy, cy - arrow.oy) - pad)
        layer = pygame.Surface((tw, th), pygame.SRCALPHA)
        for i in range(1, 4):
            k = i / 4.0
            gx = cx - arrow.ox * k * 0.5 - ox0
            gy = cy - arrow.oy * k * 0.5 - oy0
            gpoly = arrow_polygon(arrow.direction, gx, gy, scale * (1.0 - 0.12 * i))
            ga = int(a * (0.35 - i * 0.07))
            if ga <= 0:
                continue
            pygame.draw.polygon(layer, (*color, ga), gpoly)
        surf.blit(layer, (ox0, oy0))

    if a >= 250:
        shadow = [(x + 1.5, y + 2) for x, y in poly]
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        sx0 = int(min(xs) - 4)
        sy0 = int(min(ys) - 4)
        sw = int(max(xs) - min(xs) + 8)
        shh = int(max(ys) - min(ys) + 8)
        if sw > 0 and shh > 0:
            sh = pygame.Surface((sw, shh), pygame.SRCALPHA)
            local = [(x - sx0, y - sy0) for x, y in shadow]
            pygame.draw.polygon(sh, (*C_SHADOW, 40), local)
            surf.blit(sh, (sx0, sy0))
        pygame.draw.polygon(surf, color, poly)
        pygame.draw.polygon(surf, ARROW_STROKE, poly, max(1, int(2 * scale)))
        if arrow.flash > 0.35:
            pygame.draw.polygon(surf, C_DANGER, poly, 2)
    elif a > 4:
        layer = pygame.Surface((int(rect.w * scale) + 12, int(rect.h * scale) + 12), pygame.SRCALPHA)
        lx0 = int(cx - layer.get_width() / 2)
        ly0 = int(cy - layer.get_height() / 2)
        local = [(x - lx0, y - ly0) for x, y in poly]
        pygame.draw.polygon(layer, (*color, a), local)
        pygame.draw.polygon(layer, (*ARROW_STROKE, a), local, max(1, int(2 * scale)))
        surf.blit(layer, (lx0, ly0))


def spawn_sparks(game: Game, x: float, y: float, color, n: int = 10, speed: float = 160.0) -> None:
    if len(game.particles) > 90:
        return
    for _ in range(min(n, 12)):
        ang = random.uniform(0, math.tau)
        sp = random.uniform(speed * 0.45, speed)
        life = random.uniform(0.25, 0.45)
        game.particles.append(
            Particle(
                x=x,
                y=y,
                vx=math.cos(ang) * sp,
                vy=math.sin(ang) * sp,
                life=life,
                max_life=life,
                color=color,
                size=random.uniform(2.0, 4.0),
                kind="spark",
            )
        )


def spawn_ring(game: Game, x: float, y: float, color, life: float = 0.4) -> None:
    if len(game.particles) > 90:
        return
    game.particles.append(
        Particle(x=x, y=y, vx=0, vy=0, life=life, max_life=life, color=color, size=8, kind="ring")
    )


def spawn_confetti(game: Game, cx: float, cy: float, n: int = 36) -> None:
    palette = [C_PRIMARY, C_SUCCESS, C_WARN, (139, 92, 246), (14, 165, 233), (234, 88, 12)]
    for _ in range(min(n, 28)):
        ang = random.uniform(-math.pi, 0)
        sp = random.uniform(120, 280)
        life = random.uniform(0.6, 1.1)
        game.particles.append(
            Particle(
                x=cx + random.uniform(-40, 40),
                y=cy + random.uniform(-20, 20),
                vx=math.cos(ang) * sp,
                vy=math.sin(ang) * sp - random.uniform(40, 100),
                life=life,
                max_life=life,
                color=random.choice(palette),
                size=random.uniform(3.5, 6.5),
                kind="confetti",
                rot=random.uniform(0, math.tau),
                vr=random.uniform(-8, 8),
            )
        )


def spawn_trail_sparks(game: Game, arrow: Arrow, rect: pygame.Rect) -> None:
    if arrow.anim != "flying":
        return
    if random.random() > 0.35 or len(game.particles) > 80:
        return
    cx = rect.centerx + arrow.ox
    cy = rect.centery + arrow.oy
    spawn_sparks(game, cx, cy, ARROW_COLORS[arrow.direction], n=1, speed=60)


# ---------------------------------------------------------------------------
# 按钮
# ---------------------------------------------------------------------------
def make_button(rect, label, action, kind="primary", enter: float = 0.0) -> Button:
    colors = {
        "primary": C_PRIMARY,
        "secondary": C_CARD,
        "danger": C_DANGER,
        "warn": C_WARN,
    }
    return Button(
        rect=rect,
        label=label,
        action=action,
        color=colors.get(kind, C_PRIMARY),
        kind=kind,
        enter=enter,
    )


def result_panel_rect() -> pygame.Rect:
    return pygame.Rect(
        (WINDOW_W - RESULT_PANEL_W) // 2,
        (WINDOW_H - RESULT_PANEL_H) // 2 - 6,
        RESULT_PANEL_W,
        RESULT_PANEL_H,
    )


def menu_rules_panel_rect(card_offset: int = 0) -> pygame.Rect:
    """菜单规则卡片：固定几何，绘制与布局共用。"""
    cx = WINDOW_W // 2
    # y=200..410，为图例与按钮留出下方空间
    return pygame.Rect(cx - 300, 200 + card_offset, 600, 210)


def mode_rules_panel_rect(scale: float = 1.0) -> pygame.Rect:
    """高难规则弹窗：文案区 + 底部按钮，总高约 340。"""
    pw, ph = int(500 * scale), int(340 * scale)
    return pygame.Rect((WINDOW_W - pw) // 2, (WINDOW_H - ph) // 2 - 6, pw, ph)


def menu_legend_y() -> int:
    return menu_rules_panel_rect(0).bottom + 12


def rebuild_buttons(game: Game) -> None:
    game.buttons.clear()
    cx = WINDOW_W // 2

    def add(rect, label, action, kind="primary"):
        game.buttons.append(make_button(rect, label, action, kind, enter=0.0))

    if game.state == State.MENU:
        # 图例在卡片下方，按钮再往下，避免与图例/卡片重叠
        ly = menu_legend_y()
        btn1_y = ly + 28 + 20
        btn2_y = btn1_y + 48 + 14
        add(pygame.Rect(cx - 130, btn1_y, 260, 48), "开始游戏", "start", "primary")
        add(pygame.Rect(cx - 130, btn2_y, 260, 44), "高难模式", "hard_rules", "danger")

    elif game.state == State.MODE_RULES:
        panel = mode_rules_panel_rect(1.0)
        add(pygame.Rect(cx - 120, panel.bottom - 96, 240, 46), "开始挑战", "hard_start", "danger")
        add(pygame.Rect(cx - 120, panel.bottom - 44, 240, 40), "返回菜单", "menu", "secondary")

    elif game.state == State.PLAYING:
        y = WINDOW_H - BOTTOM_H + 18
        add(pygame.Rect(48, y, 136, 42), "重新开始", "restart", "secondary")
        add(pygame.Rect(200, y, 136, 42), "返回菜单", "menu", "secondary")

    elif game.state == State.WIN:
        panel = result_panel_rect()
        if game.hard_mode:
            add(pygame.Rect(cx - 110, panel.top + 250, 220, 48), "查看评价", "next", "primary")
        else:
            nxt = "下一关" if game.level_index + 1 < TOTAL_LEVELS else "查看结果"
            add(pygame.Rect(cx - 110, panel.top + 250, 220, 48), nxt, "next", "primary")
        add(pygame.Rect(cx - 110, panel.top + 312, 220, 44), "重玩本关", "restart", "secondary")
        add(pygame.Rect(cx - 110, panel.top + 368, 220, 44), "返回菜单", "menu", "secondary")

    elif game.state == State.FAIL:
        panel = result_panel_rect()
        add(pygame.Rect(cx - 110, panel.top + 250, 220, 48), "重新开始", "restart", "danger")
        add(pygame.Rect(cx - 110, panel.top + 312, 220, 44), "返回菜单", "menu", "secondary")

    elif game.state == State.ALL_CLEAR:
        panel = result_panel_rect()
        add(pygame.Rect(cx - 110, panel.top + 280, 220, 48), "再玩一遍", "start", "primary")
        add(pygame.Rect(cx - 110, panel.top + 342, 220, 44), "返回菜单", "menu", "secondary")


def draw_button(surf: pygame.Surface, btn: Button) -> None:
    # 入场 + 悬停抬升 + 按压缩放
    enter = ease_out_back(btn.enter) if btn.enter < 1.0 else 1.0
    enter = max(0.0, min(1.05, enter))
    lift = 3.5 * btn.hover_t
    press = btn.press
    scale = (1.0 + 0.035 * btn.hover_t - 0.07 * press) * (0.92 + 0.08 * enter)
    dy = -lift + (1.0 - enter) * 14
    alpha = int(255 * max(0.0, min(1.0, enter)))

    bw = max(8, int(btn.rect.w * scale))
    bh = max(8, int(btn.rect.h * scale))
    r = pygame.Rect(
        btn.rect.centerx - bw // 2,
        int(btn.rect.centery - bh // 2 + dy),
        bw,
        bh,
    )

    if alpha < 8:
        return
    need_fade = alpha < 250
    if need_fade:
        layer = pygame.Surface((r.w + 16, r.h + 16), pygame.SRCALPHA)
        target = layer
        origin_x, origin_y = r.x - 8, r.y - 8
        r_draw = pygame.Rect(8, 8, r.w, r.h)
    else:
        target = surf
        origin_x, origin_y = 0, 0
        r_draw = r

    if btn.kind == "primary":
        fill = mix(C_PRIMARY, C_PRIMARY_DEEP, 0.45 * btn.hover_t + 0.2 * press)
        sh = pygame.Surface((r.w + 12, r.h + 12), pygame.SRCALPHA)
        sh_a = int((30 + 18 * btn.hover_t - 12 * press) * (alpha / 255))
        pygame.draw.rect(
            sh,
            (*C_PRIMARY, max(0, sh_a)),
            pygame.Rect(4, 6 + int(2 * btn.hover_t), r.w, r.h),
            border_radius=RADIUS_BTN,
        )
        if need_fade:
            target.blit(sh, (2, 2))
        else:
            target.blit(sh, (r.x - 4, r.y - 2))
        pygame.draw.rect(target, fill, r_draw, border_radius=RADIUS_BTN)
        draw_text_center(target, btn.label, r_draw.centerx, r_draw.centery, 18, (255, 255, 255), bold=True)
    elif btn.kind == "danger":
        fill = mix(C_DANGER, (185, 28, 28), 0.35 * btn.hover_t + 0.2 * press)
        pygame.draw.rect(target, fill, r_draw, border_radius=RADIUS_BTN)
        draw_text_center(target, btn.label, r_draw.centerx, r_draw.centery, 18, (255, 255, 255), bold=True)
    elif btn.kind == "warn":
        fill = mix(C_WARN, (217, 119, 6), 0.35 * btn.hover_t + 0.2 * press)
        pygame.draw.rect(target, fill, r_draw, border_radius=RADIUS_BTN)
        draw_text_center(target, btn.label, r_draw.centerx, r_draw.centery, 18, (255, 255, 255), bold=True)
    else:
        fill = mix(C_CARD, C_PRIMARY_SOFT, btn.hover_t)
        border = mix(C_BORDER_STRONG, C_PRIMARY, btn.hover_t)
        pygame.draw.rect(target, fill, r_draw, border_radius=RADIUS_BTN)
        pygame.draw.rect(target, border, r_draw, width=1 + int(btn.hover_t), border_radius=RADIUS_BTN)
        text_c = mix(C_INK, C_PRIMARY_DEEP, btn.hover_t)
        draw_text_center(target, btn.label, r_draw.centerx, r_draw.centery, 18, text_c, bold=True)

    if need_fade:
        layer.set_alpha(alpha)
        surf.blit(layer, (origin_x, origin_y))


def draw_stat_pill(surf, label, value, color, x, y, w=128):
    rect = pygame.Rect(x, y, w, 52)
    fill = C_CARD
    border = C_BORDER
    if color == C_DANGER:
        fill = C_DANGER_SOFT
        border = mix(C_BORDER, C_DANGER, 0.35)
    elif color == C_WARN:
        fill = C_WARN_SOFT
        border = mix(C_BORDER, C_WARN, 0.35)
    elif color == C_SUCCESS:
        fill = C_SUCCESS_SOFT
        border = mix(C_BORDER, C_SUCCESS, 0.25)
    elif color == C_PRIMARY:
        fill = C_PRIMARY_SOFT
        border = mix(C_BORDER, C_PRIMARY, 0.3)
    pygame.draw.rect(surf, fill, rect, border_radius=RADIUS_SM)
    pygame.draw.rect(surf, border, rect, width=1, border_radius=RADIUS_SM)
    draw_text_center(surf, label, rect.centerx, y + 14, 12, C_MUTED)
    draw_text_center(surf, value, rect.centerx, y + 36, 20, color, bold=True)
    return rect


# ---------------------------------------------------------------------------
# 界面
# ---------------------------------------------------------------------------
def draw_menu(surf: pygame.Surface, game: Game) -> None:
    surf.fill(C_BG)
    draw_dot_grid(surf)

    # 顶部品牌条
    top = pygame.Rect(0, 0, WINDOW_W, 64)
    pygame.draw.rect(surf, C_CARD, top)
    pygame.draw.line(surf, C_BORDER, (0, 64), (WINDOW_W, 64), 1)
    draw_text(surf, "Arrow Puzzle", 36, 22, 14, C_MUTED)
    draw_text(surf, "Have Fun!", WINDOW_W - 36 - 70, 22, 14, C_PRIMARY, bold=True)

    cx = WINDOW_W // 2
    st = ease_out_cubic(game.screen_t if game.screen_t else 1.0)
    # 标题区
    ty = 118 - int((1 - st) * 24)
    title_a = st
    _draw_text_alpha(surf, "一箭又一箭", cx, ty, 46, C_INK, True, title_a)
    _draw_text_alpha(surf, "点击箭头 · 解开阻挡 · 清空棋盘", cx, ty + 46, 16, C_MUTED, False, title_a)

    acc_w = int(72 * st)
    accent = pygame.Rect(cx - acc_w // 2, 178, acc_w, 4)
    pygame.draw.rect(surf, C_PRIMARY, accent, border_radius=2)

    # 规则卡片（固定几何，与按钮布局一致）
    card_t = ease_out_cubic(max(0.0, (game.screen_t - 0.08) / 0.92)) if game.screen_t else 1.0
    panel = menu_rules_panel_rect(int((1 - card_t) * 18))
    if card_t > 0.02:
        _draw_card_alpha(surf, panel, int(255 * card_t))
        band = pygame.Rect(panel.x, panel.y, panel.w, 4)
        pygame.draw.rect(surf, C_PRIMARY, band, border_radius=2)
        rules = [
            "点击箭头：前方无阻挡时，飞出棋盘并消除",
            "前方有阻挡：碰撞反馈，并消耗一次可失误次数",
            "清空箭头过关；失误归零后再错则本关失败",
            f"剧情 {TOTAL_LEVELS} 关 · 高难满盘 {GRID_N * GRID_N} 箭 · 结算有星级",
            "高难星级看用时与失误，规则见模式说明",
        ]
        line_h = 32
        pad_y = 22
        for i, line in enumerate(rules):
            ny = panel.y + pad_y + i * line_h
            num_rect = pygame.Rect(panel.x + 28, ny, 22, 22)
            pygame.draw.rect(surf, C_PRIMARY_SOFT, num_rect, border_radius=11)
            draw_text_center(surf, str(i + 1), num_rect.centerx, num_rect.centery, 12, C_PRIMARY_DEEP, bold=True)
            draw_text(surf, line, panel.x + 62, ny + 3, 16, C_INK)

    # 方向图例：画在卡片底边之外
    legend_t = ease_out_cubic(max(0.0, (game.screen_t - 0.2) / 0.8)) if game.screen_t else 1.0
    legend_y = menu_legend_y() + int((1 - legend_t) * 6)
    labels = [(0, "上"), (1, "下"), (2, "左"), (3, "右")]
    lx = cx - 176
    for d, name in labels:
        chip = pygame.Rect(lx, legend_y, 82, 28)
        if legend_t > 0.05:
            pygame.draw.rect(surf, C_CARD, chip, border_radius=14)
            pygame.draw.rect(surf, C_BORDER, chip, width=1, border_radius=14)
            poly = arrow_polygon(d, chip.x + 18, chip.centery, 0.42)
            pygame.draw.polygon(surf, ARROW_COLORS[d], poly)
            pygame.draw.polygon(surf, ARROW_STROKE, poly, 1)
            draw_text(surf, name, chip.x + 34, chip.y + 6, 13, C_MUTED)
        lx += 90

    for btn in game.buttons:
        draw_button(surf, btn)

    footer = pygame.Rect(0, WINDOW_H - 48, WINDOW_W, 48)
    pygame.draw.rect(surf, C_CARD, footer)
    pygame.draw.line(surf, C_BORDER, (0, WINDOW_H - 48), (WINDOW_W, WINDOW_H - 48), 1)
    draw_text_center(
        surf,
        "鼠标点击箭头 · R 重开 · M 开关音效 · Esc 返回菜单",
        cx,
        WINDOW_H - 24,
        13,
        C_MUTED,
    )


def _draw_text_alpha(surf, text, cx, cy, size, color, bold, alpha: float) -> None:
    if alpha <= 0.02:
        return
    img = get_font(size, bold).render(text, True, color)
    if alpha < 0.98:
        img.set_alpha(int(255 * alpha))
    rect = img.get_rect(center=(cx, cy))
    surf.blit(img, rect)


def _draw_card_alpha(surf, panel: pygame.Rect, alpha: int) -> None:
    if alpha >= 250:
        draw_card(surf, panel, C_CARD, C_BORDER, RADIUS, True)
        return
    layer = pygame.Surface((panel.w + 12, panel.h + 12), pygame.SRCALPHA)
    pygame.draw.rect(layer, (*C_CARD, alpha), pygame.Rect(6, 6, panel.w, panel.h), border_radius=RADIUS)
    pygame.draw.rect(layer, (*C_BORDER, alpha), pygame.Rect(6, 6, panel.w, panel.h), width=1, border_radius=RADIUS)
    surf.blit(layer, (panel.x - 6, panel.y - 6))


def draw_hud(surf: pygame.Surface, game: Game) -> None:
    bar = pygame.Rect(0, 0, WINDOW_W, HUD_H)
    pygame.draw.rect(surf, C_CARD, bar)
    pygame.draw.line(surf, C_BORDER, (0, HUD_H), (WINDOW_W, HUD_H), 1)

    # 左：关卡标识 + 名称 + 描述
    tag = pygame.Rect(28, 20, 68, 22)
    pygame.draw.rect(surf, C_PRIMARY_SOFT, tag, border_radius=11)
    draw_text_center(surf, "LEVEL", tag.centerx, tag.centery, 10, C_PRIMARY_DEEP, bold=True)
    draw_text(surf, game.level_name, 108, 18, 20, C_INK, bold=True)
    draw_text(surf, game.level_desc, 28, 52, 12, C_MUTED)

    # 右侧统计（先排，避免与计时重叠）
    w = 96
    gap = 8
    right = WINDOW_W - 24
    x3 = right - w
    x2 = x3 - w - gap
    x1 = x2 - w - gap
    alive = len(game.alive_arrows())
    total = len(game.arrows)
    miss_color = (
        C_SUCCESS
        if game.misses_left > 1
        else C_WARN
        if game.misses_left == 1
        else C_DANGER
    )
    draw_stat_pill(surf, "关卡", "高难" if getattr(game, "hard_mode", False) else f"{game.level_index + 1}/{TOTAL_LEVELS}", C_INK, x1, 18, w)
    draw_stat_pill(surf, "剩余箭头", f"{alive}/{total}", C_PRIMARY, x2, 18, w)
    draw_stat_pill(surf, "可失误", f"{game.misses_left}/{game.misses_max}", miss_color, x3, 18, w)

    # 中：计时 — 夹在左侧标题与右侧胶囊之间的空隙，避免重叠
    left_end = 300
    right_start = x1 - 8
    tw = min(220, max(140, right_start - left_end - 12))
    th = 60
    tx = left_end + max(0, (right_start - left_end - tw) // 2)
    ty = (HUD_H - th) // 2
    timer_rect = pygame.Rect(tx, ty, tw, th)
    pulse = 0.5 + 0.5 * math.sin(_time.time() * 2.4)
    t_fill = mix(C_PRIMARY_SOFT, C_CARD, 0.3 + 0.2 * pulse)
    pygame.draw.rect(surf, t_fill, timer_rect, border_radius=RADIUS_SM)
    pygame.draw.rect(
        surf,
        mix(C_PRIMARY, C_PRIMARY_DEEP, 0.15 * pulse),
        timer_rect,
        width=2,
        border_radius=RADIUS_SM,
    )
    mid = timer_rect.centerx
    if getattr(game, "hard_mode", False):
        draw_text_center(surf, "高难 · 用时", mid, ty + 12, 11, C_PRIMARY_DEEP, bold=True)
        elapsed = game.level_time
        under = elapsed < 60.0
        color = C_SUCCESS if under else C_DANGER
        draw_text_center(surf, format_mmss(elapsed), mid, ty + 34, 24, color, bold=True)
        draw_text_center(surf, "目标 < 01:00", mid, ty + 54, 10, C_MUTED)
    else:
        draw_text_center(surf, "本关 / 总用时", mid, ty + 12, 11, C_PRIMARY_DEEP, bold=True)
        draw_text_center(surf, format_mmss(game.level_time), mid - 40, ty + 38, 20, C_INK, bold=True)
        draw_text_center(surf, "/", mid, ty + 38, 14, C_MUTED)
        draw_text_center(surf, format_mmss(game.run_time), mid + 40, ty + 38, 20, C_PRIMARY_DEEP, bold=True)


def draw_board(surf: pygame.Surface, game: Game) -> None:
    ox, oy = game.board_origin
    pad = 16
    panel = pygame.Rect(ox - pad, oy - pad - 8, game.cols * CELL + pad * 2, game.rows * CELL + pad * 2 + 8)
    draw_card(surf, panel, C_CARD, C_BORDER, RADIUS, True)

    # 棋盘标签（位于格子上方，不重叠）
    title = pygame.Rect(panel.x + 16, panel.y + 8, 72, 20)
    pygame.draw.rect(surf, C_PRIMARY_SOFT, title, border_radius=10)
    draw_text_center(surf, "棋盘", title.centerx, title.centery, 11, C_PRIMARY_DEEP, bold=True)

    mouse = pygame.mouse.get_pos()
    input_locked = game.pending_fail or game.pending_win or game.state != State.PLAYING

    for r in range(game.rows):
        for c in range(game.cols):
            rect = cell_rect(game, r, c)
            fill = C_CARD_SOFT
            border = C_BORDER
            if (not input_locked) and rect.collidepoint(mouse):
                fill = C_PRIMARY_SOFT
                border = mix(C_BORDER, C_PRIMARY, 0.45)
            pygame.draw.rect(surf, fill, rect, border_radius=RADIUS_SM)
            pygame.draw.rect(surf, border, rect, width=1, border_radius=RADIUS_SM)

    for arrow in game.arrows:
        if not arrow.alive:
            if arrow.anim != "flying" or arrow.alpha <= 5:
                continue
        rect = cell_rect(game, arrow.row, arrow.col)
        draw_arrow(surf, arrow, rect, alpha=arrow.alpha)
        spawn_trail_sparks(game, arrow, rect)

    draw_particles(surf, game)

    for ft in game.floats:
        life_k = 1.0 - (ft.t / ft.life) if ft.life else 1.0
        size = ft.size if hasattr(ft, "size") else 18
        text_surf = get_font(size, True).render(ft.text, True, ft.color)
        outline = get_font(size, True).render(ft.text, True, (255, 255, 255))
        tr = text_surf.get_rect(center=(int(ft.x), int(ft.y)))
        # 轻微放大入场
        pop = 1.0 + 0.12 * max(0.0, 1.0 - ft.t / 0.15)
        if pop != 1.0:
            text_surf = pygame.transform.rotozoom(text_surf, 0, pop)
            outline = pygame.transform.rotozoom(outline, 0, pop)
            tr = text_surf.get_rect(center=(int(ft.x), int(ft.y)))
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            surf.blit(outline, tr.move(dx, dy))
        if life_k < 1.0:
            text_surf.set_alpha(int(255 * min(1.0, life_k * 1.4)))
        surf.blit(text_surf, tr)


def draw_banner(surf: pygame.Surface, game: Game) -> None:
    """提示横幅：仅保留底部细条（小号），不再绘制大号弹层。"""
    timer = getattr(game, "banner_timer", 0.0)
    if timer <= 0:
        return
    label = getattr(game, "banner", "") or ""
    if not label:
        return
    duration = getattr(game, "banner_duration", 1.3) or 1.3
    progress = 1.0 - min(1.0, timer / duration)
    if progress < 0.2:
        pop = progress / 0.2
        a = int(230 * ease_out_cubic(pop))
        dy = -8 * (1.0 - ease_out_cubic(pop))
    elif progress > 0.8:
        out = (1.0 - progress) / 0.2
        a = int(220 * out)
        dy = -6 * (1.0 - out)
    else:
        a = 220
        dy = 0
    if a <= 6:
        return
    bar_h = 30
    bar_w = 420
    cx = WINDOW_W // 2
    cy = HUD_H + 18 + int(dy)
    bar = pygame.Rect(cx - bar_w // 2, cy - bar_h // 2, bar_w, bar_h)
    layer = pygame.Surface((bar_w + 6, bar_h + 6), pygame.SRCALPHA)
    pygame.draw.rect(layer, (*C_CARD, min(a, 230)), pygame.Rect(3, 3, bar_w, bar_h), border_radius=bar_h // 2)
    pygame.draw.rect(
        layer, (*C_BORDER, min(a, 220)), pygame.Rect(3, 3, bar_w, bar_h), width=1, border_radius=bar_h // 2
    )
    pygame.draw.circle(layer, (*C_PRIMARY, min(a, 255)), (16, bar_h // 2 + 3), 4)
    surf.blit(layer, (bar.x - 3, bar.y - 3))
    img = get_font(14, True).render(label, True, C_INK)
    if a < 250:
        img.set_alpha(min(255, a))
    surf.blit(img, img.get_rect(center=(bar.centerx + 6, bar.centery)))


def set_banner(game: Game, text: str, duration: float = 1.3, kind: str = "info") -> None:
    game.banner = text
    game.banner_timer = duration
    game.banner_age = 0.0
    game.banner_duration = duration
    game.banner_life = duration
    game.banner_kind = kind


def draw_bottom_bar(surf: pygame.Surface, game: Game) -> None:
    bar = pygame.Rect(0, WINDOW_H - BOTTOM_H, WINDOW_W, BOTTOM_H)
    pygame.draw.rect(surf, C_CARD, bar)
    pygame.draw.line(surf, C_BORDER, (0, WINDOW_H - BOTTOM_H), (WINDOW_W, WINDOW_H - BOTTOM_H), 1)
    for btn in game.buttons:
        draw_button(surf, btn)
    hint = pygame.Rect(WINDOW_W - 300, WINDOW_H - BOTTOM_H + 20, 260, 36)
    pygame.draw.rect(surf, C_CARD_SOFT, hint, border_radius=RADIUS_SM)
    pygame.draw.rect(surf, C_BORDER, hint, width=1, border_radius=RADIUS_SM)
    draw_text_center(surf, "点击箭头 · R 重开 · Esc 菜单", hint.centerx, hint.centery, 13, C_MUTED)


def draw_result(surf: pygame.Surface, game: Game, kind: str) -> None:
    # 半透明浅遮罩（随弹层淡入）
    mt = ease_out_cubic(game.modal_t if game.modal_t else 1.0)
    overlay = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
    overlay.fill((244, 246, 248, int(200 * mt)))
    surf.blit(overlay, (0, 0))
    draw_particles(surf, game)

    base = result_panel_rect()
    # 弹层缩放入场
    s = 0.88 + 0.12 * ease_out_back(game.modal_t if game.modal_t else 1.0)
    if game.modal_t <= 0:
        s = 1.0
    pw, ph = int(base.w * s), int(base.h * s)
    panel = pygame.Rect(base.centerx - pw // 2, base.centery - ph // 2, pw, ph)
    draw_card(surf, panel, C_CARD, C_BORDER, RADIUS, True)
    cx = panel.centerx
    top = panel.top

    if kind == "win":
        band = pygame.Rect(panel.x, panel.y, panel.w, 5)
        pygame.draw.rect(surf, C_SUCCESS, band, border_radius=2)
        badge = pygame.Rect(cx - 40, top + 36, 80, 28)
        pygame.draw.rect(surf, C_SUCCESS_SOFT, badge, border_radius=14)
        draw_text_center(surf, "CLEAR", badge.centerx, badge.centery, 12, C_SUCCESS, bold=True)
        draw_text_center(surf, "通关！", cx, top + 90, 40, C_INK, bold=True)
        draw_text_center(surf, game.level_name, cx, top + 132, 18, C_INK)
        if getattr(game, "hard_mode", False):
            draw_text_center(surf, f"高难 · {game.arrow_count} 箭 · 用时 {format_mmss(game.level_time)}", cx, top + 164, 15, C_MUTED)
            draw_text_center(surf, f"失误 {game.run_total_misses} 次", cx, top + 190, 15, C_MUTED)
        else:
            draw_text_center(surf, f"本关 {game.arrow_count} 支箭头已全部清除", cx, top + 164, 15, C_MUTED)
            draw_text_center(
                surf,
                f"剩余可失误：{game.misses_left} / {game.misses_max}",
                cx,
                top + 190,
                15,
                C_MUTED,
            )
    elif kind == "fail":
        band = pygame.Rect(panel.x, panel.y, panel.w, 5)
        pygame.draw.rect(surf, C_DANGER, band, border_radius=2)
        badge = pygame.Rect(cx - 40, top + 36, 80, 28)
        pygame.draw.rect(surf, C_DANGER_SOFT, badge, border_radius=14)
        draw_text_center(surf, "FAILED", badge.centerx, badge.centery, 12, C_DANGER, bold=True)
        draw_text_center(surf, "挑战失败", cx, top + 90, 40, C_INK, bold=True)
        draw_text_center(surf, game.level_name, cx, top + 132, 18, C_INK)
        draw_text_center(surf, "Game Over", cx, top + 164, 15, C_MUTED)
        left = len(game.alive_arrows())
        draw_text_center(surf, f"仍有 {left} 个箭头未清除", cx, top + 190, 15, C_MUTED)
    else:
        band = pygame.Rect(panel.x, panel.y, panel.w, 5)
        pygame.draw.rect(surf, C_PRIMARY, band, border_radius=2)
        badge = pygame.Rect(cx - 48, top + 24, 96, 26)
        hard = bool(getattr(game, "hard_mode", False))
        badge_label = "HARD CLEAR" if hard else "ALL CLEAR"
        badge_w = 108 if hard else 96
        badge = pygame.Rect(cx - badge_w // 2, top + 24, badge_w, 26)
        pygame.draw.rect(surf, C_DANGER_SOFT if hard else C_PRIMARY_SOFT, badge, border_radius=13)
        draw_text_center(surf, badge_label, badge.centerx, badge.centery, 11, C_DANGER if hard else C_PRIMARY_DEEP, bold=True)
        title = "高难通关！" if hard else "全部通关！"
        draw_text_center(surf, title, cx, top + 72, 34, C_INK, bold=True)

        stars = game.stars if game.stars else (
            compute_stars_hard(game.run_total_misses, game.final_time or game.level_time)
            if hard
            else compute_stars(game.run_total_misses, game.run_had_fail)
        )
        star_y = top + 122
        reveal = getattr(game, "stars_reveal", 1.0)
        anims = getattr(game, "star_anim", [1.0, 1.0, 1.0])
        pops = getattr(game, "star_pop", [0.0, 0.0, 0.0])
        wobs = getattr(game, "star_wob", [0.0, 0.0, 0.0])
        for i in range(3):
            sx = cx + (i - 1) * 50
            local = max(0.0, min(1.0, (reveal - 0.35 - i * 0.28) / 0.32))
            if i < len(anims):
                local = max(local, anims[i])
            pop = pops[i] if i < len(pops) else 0.0
            wob = wobs[i] if i < len(wobs) else 0.0
            if local <= 0.02:
                pygame.draw.circle(surf, (229, 234, 240), (sx, star_y), 13)
                pygame.draw.circle(surf, (203, 213, 225), (sx, star_y), 13, 2)
                continue
            filled = i < stars
            # 旋转摆动 + 弹性缩放
            spin = wob * 18 if wob < 1 else 0.0
            base_r = 17
            if local < 1.0:
                r = max(4, int(base_r * ease_out_back(local)))
            else:
                r = base_r
                if pop > 0:
                    r = int(base_r * (1.0 + 0.22 * pop))
            # 轻微垂直摆动
            yy = star_y + int(math.sin(wob * math.pi * 2) * 3 * (1.0 - min(1.0, wob)))
            glow = pop if filled else 0.0
            draw_star(surf, sx, yy, r, filled, glow=glow)
            # 空星出现时的淡入圈
            if not filled and local < 1.0:
                pass
        # 星级文案（星星出完后淡入）
        label_k = max(0.0, min(1.0, (reveal - 1.05) / 0.35))
        if hard:
            star_label = {3: "神速无误 · 三星", 2: "达标通关 · 二星", 1: "再战一次 · 一星"}.get(stars, "")
        else:
            star_label = {3: "完美通关 · 三星", 2: "表现优秀 · 二星", 1: "继续加油 · 一星"}.get(stars, "")
        if label_k > 0.02:
            _draw_text_alpha(surf, star_label, cx, star_y + 38, 17, C_INK, True, label_k)
        meta_k = max(0.0, min(1.0, (reveal - 1.25) / 0.35))
        if meta_k > 0.02:
            if hard:
                _draw_text_alpha(
                    surf,
                    f"用时 {format_mmss(game.final_time or game.level_time)}  ·  失误 {game.run_total_misses} 次  ·  目标 < 01:00",
                    cx,
                    star_y + 66,
                    14,
                    C_MUTED,
                    False,
                    meta_k,
                )
                _draw_text_alpha(surf, "高难模式 · 单关评价", cx, star_y + 90, 13, C_FAINT, False, meta_k)
            else:
                _draw_text_alpha(
                    surf,
                    f"总用时 {format_mmss(game.final_time or game.run_time)}  ·  总失误 {game.run_total_misses} 次",
                    cx,
                    star_y + 66,
                    14,
                    C_MUTED,
                    False,
                    meta_k,
                )
                fail_note = "存在失败重开" if game.run_had_fail else "无失败重开"
                _draw_text_alpha(surf, fail_note, cx, star_y + 90, 13, C_MUTED, False, meta_k)

    for btn in game.buttons:
        draw_button(surf, btn)


def draw_star(surf: pygame.Surface, cx: int, cy: int, radius: int, filled: bool, glow: float = 0.0) -> None:
    """五角星（实心金 / 空心灰），可选外发光。"""
    if filled and glow > 0.05:
        gr = int(radius * (1.35 + 0.45 * glow))
        gs = pygame.Surface((gr * 2 + 8, gr * 2 + 8), pygame.SRCALPHA)
        pygame.draw.circle(gs, (245, 158, 11, int(70 * glow)), (gs.get_width() // 2, gs.get_height() // 2), gr)
        surf.blit(gs, (cx - gs.get_width() // 2, cy - gs.get_height() // 2))
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        r = radius if i % 2 == 0 else radius * 0.45
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    if filled:
        pygame.draw.polygon(surf, (245, 158, 11), pts)
        pygame.draw.polygon(surf, (202, 138, 4), pts, 2)
        # 高光点
        if radius >= 10:
            pygame.draw.circle(surf, (255, 236, 160), (int(cx - radius * 0.25), int(cy - radius * 0.3)), max(2, radius // 6))
    else:
        pygame.draw.polygon(surf, (229, 234, 240), pts)
        pygame.draw.polygon(surf, (156, 163, 175), pts, 2)


def draw_mode_rules(surf: pygame.Surface, game: Game) -> None:
    """高难模式规则弹窗（带动画）。文案与按钮共用同一面板几何。"""
    t = max(0.0, min(1.0, getattr(game, "rules_t", 1.0)))
    ov_a = int(200 * ease_out_cubic(t))
    overlay = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
    overlay.fill((244, 246, 248, ov_a))
    surf.blit(overlay, (0, 0))

    scale = 0.92 + 0.08 * ease_out_back(t)
    panel = mode_rules_panel_rect(scale)
    base = mode_rules_panel_rect(1.0)
    draw_card(surf, panel, C_CARD, C_BORDER, RADIUS, True)
    band = pygame.Rect(panel.x, panel.y, panel.w, 5)
    pygame.draw.rect(surf, C_DANGER, band, border_radius=2)

    cx = base.centerx
    top = base.top
    badge = pygame.Rect(cx - 44, top + 22, 88, 26)
    pygame.draw.rect(surf, C_DANGER_SOFT, badge, border_radius=13)
    draw_text_center(surf, "HARD", badge.centerx, badge.centery, 12, C_DANGER, bold=True)
    draw_text_center(surf, "高难模式规则", cx, top + 68, 26, C_INK, bold=True)

    full_n = GRID_N * GRID_N
    lines = [
        f"仅 1 关 · 箭头铺满棋盘（{GRID_N}×{GRID_N} = {full_n} 支）",
        "随机生成且保证可解 · 计时只计本关",
        "目标 60 秒以内 · 失误机会仍为 3 次",
        "三星：0 失误 且 用时 < 1 分钟",
        "二星：失误 ≤ 3 且 用时 < 1 分钟",
        "一星：用时 ≥ 1 分钟 或 失误 > 3",
    ]
    # 文案区：top+100 起，6 行 × 26px，末行约 top+230
    y0 = top + 100
    for i, line in enumerate(lines):
        alpha = max(0.0, min(1.0, (t - 0.05 * i) / 0.3))
        if alpha < 0.05:
            continue
        color = C_PRIMARY_DEEP if i == 3 else C_INK
        _draw_text_alpha(surf, line, cx, y0 + i * 26, 15, color, i >= 3, alpha)

    for btn in game.buttons:
        draw_button(surf, btn)


# ---------------------------------------------------------------------------
# 交互（逻辑不变；界面切换走 request_action 转场）
# ---------------------------------------------------------------------------
def apply_action(game: Game, action: str) -> None:
    """立即执行界面/关卡动作（供转场结束后与测试调用）。"""
    if action == "start":
        game.hard_mode = False
        game.run_time = 0.0
        game.level_time = 0.0
        game.run_total_misses = 0
        game.run_had_fail = False
        game.stars = 0
        game.final_time = 0.0
        game.stars_reveal = 0.0
        load_level(game, 0)
        rebuild_buttons(game)
        game.screen_t = 0.0
        play_sound("start")
    elif action == "hard_rules":
        game.hard_mode = True
        game.state = State.MODE_RULES
        game.rules_t = 0.0
        rebuild_buttons(game)
        game.screen_t = 0.0
        play_sound("click")
    elif action == "hard_start":
        game.hard_mode = True
        game.run_time = 0.0
        game.level_time = 0.0
        game.run_total_misses = 0
        game.run_had_fail = False
        game.stars = 0
        game.final_time = 0.0
        game.stars_reveal = 0.0
        game.level_index = 0
        load_level(game, 0)
        rebuild_buttons(game)
        game.screen_t = 0.0
        play_sound("start")
    elif action == "restart":
        load_level(game, game.level_index)
        if game.hard_mode:
            game.level_time = 0.0
            game.run_time = 0.0
        rebuild_buttons(game)
        game.screen_t = 0.0
        play_sound("click")
    elif action == "menu":
        game.state = State.MENU
        game.hard_mode = False
        game.floats.clear()
        game.particles.clear()
        game.pending_fail = False
        game.pending_win = False
        game.modal_t = 0.0
        game.hit_flash = 0.0
        game.shake = 0.0
        game.rules_t = 0.0
        rebuild_buttons(game)
        game.screen_t = 0.0
        play_sound("click")
    elif action == "next":
        if game.hard_mode:
            game.state = State.ALL_CLEAR
            game.modal_t = 0.0
            game.final_time = game.level_time
            game.stars = compute_stars_hard(game.run_total_misses, game.final_time)
            game.stars_reveal = 0.0
            game.star_anim = [0.0, 0.0, 0.0]
            game.star_pop = [0.0, 0.0, 0.0]
            game.star_wob = [0.0, 0.0, 0.0]
            game.star_burst = 0.0
            play_sound("stars")
        else:
            nxt = game.level_index + 1
            if nxt < TOTAL_LEVELS:
                load_level(game, nxt)
                play_sound("start")
            else:
                game.state = State.ALL_CLEAR
                game.modal_t = 0.0
                game.final_time = game.run_time
                game.stars = compute_stars(game.run_total_misses, game.run_had_fail)
                game.stars_reveal = 0.0
                game.star_anim = [0.0, 0.0, 0.0]
                game.star_pop = [0.0, 0.0, 0.0]
                game.star_wob = [0.0, 0.0, 0.0]
                game.star_burst = 0.0
                play_sound("stars")
        rebuild_buttons(game)
        game.screen_t = 0.0
    for b in game.buttons:
        b.enter = 0.0
        b.hover_t = 0.0
        b.press = 0.0


def handle_action(game: Game, action: str) -> None:
    """兼容测试/脚本：立即生效。"""
    apply_action(game, action)


def request_action(game: Game, action: str) -> None:
    """用户操作入口：先淡出，再切换界面并淡入。"""
    if game.trans_dir != 0:
        return
    game.trans_dir = 1
    game.trans_t = 0.0
    game.trans_pending = action
    game._trans_age = 0.0


def click_arrow(game: Game, row: int, col: int) -> None:
    if game.state != State.PLAYING or game.pending_fail or game.pending_win:
        return

    target = None
    for a in game.arrows:
        if a.alive and a.row == row and a.col == col:
            target = a
            break
    if target is None or target.anim == "bump":
        return

    if not is_blocked(game.arrows, target, game.rows, game.cols):
        target.alive = False
        target.anim = "flying"
        target.anim_t = 0.0
        target.alpha = 255.0
        target.scale = 1.08
        rect = cell_rect(game, row, col)
        game.floats.append(FloatText("消除", rect.centerx, rect.centery, C_SUCCESS, life=0.75, size=20))
        spawn_sparks(game, rect.centerx, rect.centery, ARROW_COLORS[target.direction], n=14, speed=200)
        spawn_ring(game, rect.centerx, rect.centery, C_SUCCESS, life=0.35)
        game.banner = f"箭头向{DIR_NAME[target.direction]}飞出"
        game.banner_timer = 0.85
        set_banner(game, game.banner, 0.85, kind="info")
        play_sound("fly")
        if not game.alive_arrows():
            game.pending_win = True
            spawn_confetti(game, WINDOW_W // 2, WINDOW_H // 2 - 40, n=40)
            play_sound("clear")
        return

    target.anim = "bump"
    target.anim_t = 0.0
    target.flash = 1.0
    game.shake = SHAKE_AMPLITUDE
    game.hit_flash = 0.55
    rect = cell_rect(game, row, col)
    game.floats.append(FloatText("被阻挡！", rect.centerx, rect.top - 8, C_DANGER, life=0.85, size=20))
    spawn_sparks(game, rect.centerx, rect.centery, C_DANGER, n=12, speed=180)
    spawn_ring(game, rect.centerx, rect.centery, C_DANGER, life=0.45)
    play_sound("bump")

    if game.misses_left <= 0:
        game.floats.append(FloatText("Game Over", rect.centerx, rect.bottom + 10, C_DANGER, life=1.0, size=16))
        game.banner = "失误次数归零，下次失误将导致游戏失败！"
        game.banner_timer = 1.2
        game.pending_fail = True
        game.hit_flash = 0.85
        game.shake = SHAKE_AMPLITUDE * 1.6
        game.run_total_misses += 1
        game.run_had_fail = True
        play_sound("fail")
    else:
        game.misses_left -= 1
        game.run_total_misses += 1
        if game.misses_left == 0:
            game.floats.append(FloatText("最后一次咯~", rect.centerx, rect.bottom + 10, C_WARN, life=1.0, size=16))
            game.banner = "失误次数归零，下次失误将导致游戏失败！"
            set_banner(game, game.banner, 1.0, kind="info")
        else:
            game.floats.append(
                FloatText(f"还可失误 {game.misses_left}", rect.centerx, rect.bottom + 10, C_WARN, life=0.9, size=16)
            )
            game.banner = f"前方有阻挡（还可失误 {game.misses_left} 次）"
            set_banner(game, game.banner, 1.0, kind="info")
        game.banner_timer = 1.0


def on_mouse_down(game: Game, pos: Tuple[int, int]) -> None:
    for btn in game.buttons:
        if btn.rect.collidepoint(pos):
            btn.press = 1.0
            play_sound("click")
            request_action(game, btn.action)
            return
    if game.state == State.PLAYING and not game.pending_fail and not game.pending_win and game.trans_dir == 0:
        for a in game.arrows:
            if not a.alive:
                continue
            if cell_rect(game, a.row, a.col).collidepoint(pos):
                click_arrow(game, a.row, a.col)
                break


def ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def ease_out_back(t: float) -> float:
    t = max(0.0, min(1.0, t))
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def math_damp(x: float) -> float:
    return math.exp(-4.0 * x) * math.sin(14.0 * x)


def update_particles(game: Game, dt: float) -> None:
    if len(game.particles) > 120:
        game.particles = game.particles[-120:]
    alive_p: List[Particle] = []
    for p in game.particles:
        p.life -= dt
        if p.life <= 0:
            continue
        if p.kind == "ring":
            p.size += 220 * dt
        else:
            p.vy += 420 * dt
            p.vx *= 0.98
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.rot += p.vr * dt
        alive_p.append(p)
    game.particles = alive_p


def draw_particles(surf: pygame.Surface, game: Game) -> None:
    if not game.particles:
        return
    # 仅在粒子包围盒绘制，避免每帧全屏透明层
    min_x = min(p.x - p.size * 2 for p in game.particles)
    max_x = max(p.x + p.size * 2 for p in game.particles)
    min_y = min(p.y - p.size * 2 for p in game.particles)
    max_y = max(p.y + p.size * 2 for p in game.particles)
    x0 = max(0, int(min_x) - 4)
    y0 = max(0, int(min_y) - 4)
    x1 = min(WINDOW_W, int(max_x) + 4)
    y1 = min(WINDOW_H, int(max_y) + 4)
    w, h = x1 - x0, y1 - y0
    if w <= 0 or h <= 0:
        return
    layer = pygame.Surface((w, h), pygame.SRCALPHA)
    for p in game.particles:
        k = max(0.0, p.life / p.max_life) if p.max_life else 0
        if p.kind == "ring":
            a = int(160 * k)
            if a <= 0:
                continue
            pygame.draw.circle(layer, (*p.color, a), (int(p.x - x0), int(p.y - y0)), int(p.size), 3)
        elif p.kind == "confetti":
            a = int(220 * k)
            if a <= 0:
                continue
            w2, h2 = p.size, p.size * 0.55
            pts = []
            for dx, dy in ((-w2, -h2), (w2, -h2), (w2, h2), (-w2, h2)):
                ca, sa = math.cos(p.rot), math.sin(p.rot)
                pts.append((p.x + dx * ca - dy * sa - x0, p.y + dx * sa + dy * ca - y0))
            pygame.draw.polygon(layer, (*p.color, a), pts)
        else:
            a = int(200 * k)
            if a <= 0:
                continue
            r = max(1.0, p.size * (0.4 + 0.6 * k))
            pygame.draw.circle(layer, (*p.color, a), (int(p.x - x0), int(p.y - y0)), int(r))
    surf.blit(layer, (x0, y0))


def update_animations(game: Game, dt: float) -> None:
    update_transition(game, dt)
    update_button_anim(game, dt)

    # 计时：仅在游玩中累加（整局 + 本关）
    if game.state == State.PLAYING and not game.pending_win and game.trans_dir == 0:
        if getattr(game, "hard_mode", False):
            game.level_time += dt
            game.run_time = game.level_time  # 高难只计本关
        else:
            game.run_time += dt
            game.level_time += dt

    if game.shake > 0:
        game.shake = max(0.0, game.shake - dt * 22)
    if game.hit_flash > 0:
        game.hit_flash = max(0.0, game.hit_flash - dt * 2.4)
    if game.banner_timer > 0:
        game.banner_timer = max(0.0, game.banner_timer - dt)
        game.banner_age += dt
    elif game.banner_age > 0:
        # 出场动画收尾
        game.banner_age += dt
        if game.banner_age >= (game.banner_life + 0.2):
            game.banner_age = 0.0
            game.banner_timer = 0.0

    # 星级依次入场
    if game.state == State.ALL_CLEAR:
        game.stars_reveal = min(3.2, game.stars_reveal + dt * 2.4)
    else:
        game.stars_reveal = 0.0

    # 关卡入场
    if game.state == State.PLAYING and game.level_enter < 1.0:
        game.level_enter = min(1.0, game.level_enter + dt * 2.2)
        for i, a in enumerate(game.arrows):
            if not a.alive:
                continue
            delay = (a.row + a.col) * 0.045 + (i % 5) * 0.02
            t = max(0.0, min(1.0, (game.level_enter * 0.9 - delay) / 0.35))
            if t <= 0:
                a.scale = 0.25
                a.alpha = 0
            else:
                a.scale = 0.25 + 0.75 * ease_out_back(t)
                a.alpha = 255 * ease_out_cubic(t)
    elif game.state == State.PLAYING:
        for a in game.arrows:
            if a.alive and a.anim not in ("flying", "bump"):
                a.scale = 1.0
                a.alpha = 255.0

    # 结果弹层入场 + 星星序列揭示（更细的弹出/摆动/闪光）
    if game.state in (State.WIN, State.FAIL, State.ALL_CLEAR):
        game.modal_t = min(1.0, game.modal_t + dt * 3.2)
    else:
        game.modal_t = 0.0

    if game.state == State.MODE_RULES:
        game.rules_t = min(1.0, game.rules_t + dt * 2.8)
    elif game.state != State.MODE_RULES:
        # 保持规则动画进度，便于再次打开
        pass

    if game.state == State.ALL_CLEAR:
        game.stars_reveal = min(3.5, game.stars_reveal + dt * 1.55)
        while len(game.star_anim) < 3:
            game.star_anim.append(0.0)
            game.star_pop.append(0.0)
            game.star_wob.append(0.0)
        for i in range(3):
            # 延迟 0.35 + i*0.28，动画时长 0.32
            local = (game.stars_reveal - 0.35 - i * 0.28) / 0.32
            if local > 0:
                prev = game.star_anim[i]
                game.star_anim[i] = min(1.0, max(prev, local))
                # 弹出完成后 0.25s 内摆动衰减 + 闪光
                if game.star_anim[i] >= 1.0 and game.star_wob[i] < 1.0:
                    game.star_wob[i] = min(1.0, game.star_wob[i] + dt * 3.2)
                if prev < 1.0 <= game.star_anim[i]:
                    game.star_pop[i] = 1.0
                    game.star_burst = max(game.star_burst, 0.6)
                    play_sound("star_pop")
        for i in range(3):
            if game.star_pop[i] > 0:
                game.star_pop[i] = max(0.0, game.star_pop[i] - dt * 2.2)
        if game.star_burst > 0:
            game.star_burst = max(0.0, game.star_burst - dt * 1.4)
    else:
        if game.state != State.MODE_RULES:
            game.stars_reveal = 0.0
        for i in range(3):
            if i < len(game.star_anim):
                pass
        # 进入 ALL_CLEAR 时在 apply_action 重置

    new_floats = []
    for ft in game.floats:
        ft.t += dt
        ft.y -= 42 * dt
        if ft.t < ft.life:
            new_floats.append(ft)
    game.floats = new_floats
    update_particles(game, dt)

    for a in game.arrows:
        if a.anim == "flying":
            a.anim_t += dt
            dr, dc = DIR_DELTA[a.direction]
            # 先慢后快再匀速
            t = a.anim_t
            dist = FLY_SPEED * (t * t * 0.55 + t * 0.45)
            a.ox = dc * dist
            a.oy = dr * dist
            a.scale = 1.08 + 0.25 * min(1.0, t * 2.0)
            a.alpha = max(0.0, 255 - dist * 0.32)
            if a.alpha <= 2 or a.anim_t > 0.9:
                a.anim = ""
                a.ox = a.oy = 0
                a.alpha = 0
                a.scale = 1.0
        elif a.anim == "bump":
            a.anim_t += dt
            dr, dc = DIR_DELTA[a.direction]
            t = a.anim_t
            if t >= BUMP_DURATION:
                a.anim = ""
                a.ox = a.oy = 0
                a.flash = 0.0
                a.scale = 1.0
            else:
                phase = t / BUMP_DURATION
                if phase < 0.32:
                    k = phase / 0.32
                    dist = BUMP_AMPLITUDE * ease_out_cubic(k)
                    a.scale = 1.0 + 0.12 * k
                else:
                    back = (phase - 0.32) / 0.68
                    dist = BUMP_AMPLITUDE * (1 - back) * math_damp(back)
                    a.scale = 1.0 + 0.12 * (1 - back)
                a.ox = dc * dist
                a.oy = dr * dist
                wobble = 5.0 * (1 - phase) * math.sin(phase * math.pi * 6)
                a.ox += -dr * wobble
                a.oy += dc * wobble
                a.flash = max(0.0, 1.0 - phase * 1.15)
        else:
            a.flash = max(0.0, a.flash - dt * 2.2)

    if game.pending_fail and game.state == State.PLAYING:
        if not any(a.anim == "bump" for a in game.arrows):
            game.pending_fail = False
            game.state = State.FAIL
            game.modal_t = 0.0
            game.run_had_fail = True
            rebuild_buttons(game)

    if game.pending_win and game.state == State.PLAYING:
        if not any(a.anim == "flying" for a in game.arrows):
            game.pending_win = False
            game.state = State.WIN
            game.modal_t = 0.0
            play_sound("win")
            rebuild_buttons(game)


def handle_r_key(game: Game) -> None:
    """R：菜单/规则页开始；游戏中/胜负界面重开；全通关后重新开始。"""
    if game.trans_dir != 0:
        return
    if game.state == State.MENU:
        request_action(game, "start")
    elif game.state == State.MODE_RULES:
        request_action(game, "hard_start")
    elif game.state in (State.PLAYING, State.WIN, State.FAIL):
        request_action(game, "restart")
    elif game.state == State.ALL_CLEAR:
        request_action(game, "hard_start" if game.hard_mode else "start")


def poll_hotkeys(game: Game, keys) -> None:
    """每帧轮询 R：兼容中文输入法吞掉 KEYDOWN 的情况。"""
    r_now = bool(keys[pygame.K_r])
    if r_now and not game.key_r_down:
        game.key_r_down = True
        handle_r_key(game)
    elif not r_now:
        game.key_r_down = False


def update_button_anim(game: Game, dt: float) -> None:
    for b in game.buttons:
        b.enter = min(1.0, b.enter + dt * 4.5)
        target = 1.0 if b.hover else 0.0
        b.hover_t += (target - b.hover_t) * min(1.0, dt * 14.0)
        if b.press > 0:
            b.press = max(0.0, b.press - dt * 7.0)


def update_transition(game: Game, dt: float) -> None:
    # 保证转场一定推进，避免极小 dt 卡死
    step = max(dt, 1.0 / 90.0)
    if game.trans_dir == 1:
        game.trans_t += step / TRANS_OUT
        if game.trans_t >= 1.0:
            action = game.trans_pending or "menu"
            game.trans_pending = None
            try:
                apply_action(game, action)
            except Exception:
                # 生成关卡等失败时回菜单，避免卡死
                game.state = State.MENU
                rebuild_buttons(game)
            game.trans_dir = 2
            game.trans_t = 0.0
            game.screen_t = 0.0
    elif game.trans_dir == 2:
        game.trans_t += step / TRANS_IN
        if game.trans_t >= 1.0:
            game.trans_dir = 0
            game.trans_t = 0.0
    # 界面内容入场
    if game.trans_dir == 0:
        game.screen_t = min(1.0, game.screen_t + step * 2.8)
    elif game.trans_dir == 2:
        game.screen_t = min(1.0, game.screen_t + step * 3.5)


def draw_transition_overlay(surf: pygame.Surface, game: Game) -> None:
    if game.trans_dir == 0:
        return
    if game.trans_dir == 1:
        t = ease_out_cubic(min(1.0, game.trans_t))
        a = int(230 * t)
    else:
        t = ease_out_cubic(min(1.0, game.trans_t))
        a = int(230 * (1.0 - t))
    if a <= 0:
        return
    ov = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
    ov.fill((*C_BG, a))
    surf.blit(ov, (0, 0))
    # 转场时的品牌短线
    if game.trans_dir == 1:
        cx = WINDOW_W // 2
        w = int(40 + 80 * min(1.0, game.trans_t))
        bar = pygame.Rect(cx - w // 2, WINDOW_H // 2 - 2, w, 4)
        pygame.draw.rect(surf, C_PRIMARY, bar, border_radius=2)


def safe_pygame_boot() -> None:
    """只初始化显示/字体；音频单独限时初始化，避免卡死。"""
    if os.environ.get("ARROW_GAME_SILENT") != "1":
        # 不强制 dummy，让真实声卡可用；若 init 失败再降级
        pass
    else:
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    pygame.display.init()
    pygame.font.init()
    try:
        pygame.key.set_repeat(0, 0)
    except Exception:
        pass


def main() -> None:
    if os.environ.get("ARROW_GAME_HEADLESS") == "1":
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

    safe_pygame_boot()
    pygame.display.set_caption("一箭又一箭")
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    clock = pygame.time.Clock()
    game = Game()
    rebuild_buttons(game)
    # 窗口就绪后限时初始化音频，并播放 BGM
    start_sounds_async()
    play_bgm()

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        if dt <= 0:
            dt = 1.0 / FPS
        if dt > 0.1:
            dt = 0.1  # 防止挂起后一帧过大导致逻辑异常

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE and game.state != State.MENU:
                    request_action(game, "menu")
                elif event.key == pygame.K_m:
                    muted = toggle_mute()
                    set_banner(game, "已静音" if muted else "音效已开启", 0.9)
                elif event.key == pygame.K_r:
                    if not game.key_r_down:
                        game.key_r_down = True
                        handle_r_key(game)
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_r:
                    game.key_r_down = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                on_mouse_down(game, event.pos)
            elif event.type == pygame.MOUSEMOTION:
                for btn in game.buttons:
                    btn.hover = btn.rect.collidepoint(event.pos)

        poll_hotkeys(game, pygame.key.get_pressed())
        update_animations(game, dt)

        # 转场保险：若长时间卡在转场中，强制完成
        if game.trans_dir != 0:
            game._trans_age = getattr(game, "_trans_age", 0.0) + dt
            if game._trans_age > 2.5:
                action = game.trans_pending or "menu"
                game.trans_pending = None
                try:
                    apply_action(game, action)
                except Exception:
                    game.state = State.MENU
                    rebuild_buttons(game)
                game.trans_dir = 0
                game.trans_t = 0.0
                game._trans_age = 0.0
        else:
            game._trans_age = 0.0

        enter_y = 0
        if game.trans_dir == 2:
            enter_y = int((1.0 - ease_out_cubic(min(1.0, game.trans_t))) * 18)
        elif game.trans_dir == 0:
            enter_y = int((1.0 - ease_out_cubic(min(1.0, game.screen_t))) * 10)

        if game.state == State.MENU:
            draw_menu(screen, game)
        elif game.state == State.MODE_RULES:
            draw_menu(screen, game)
            draw_mode_rules(screen, game)
        elif game.state in (State.PLAYING, State.WIN, State.FAIL):
            world = pygame.Surface((WINDOW_W, WINDOW_H))
            world.fill(C_BG)
            draw_dot_grid(world)
            draw_hud(world, game)
            draw_banner(world, game)
            draw_board(world, game)
            draw_bottom_bar(world, game)
            offset = (0, enter_y)
            if game.shake > 0:
                offset = (
                    offset[0] + random.randint(-int(game.shake), int(game.shake)),
                    offset[1] + random.randint(-int(game.shake), int(game.shake)),
                )
            screen.fill(C_BG)
            screen.blit(world, offset)
            if game.hit_flash > 0:
                flash = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
                flash.fill((*C_DANGER, int(70 * game.hit_flash)))
                screen.blit(flash, (0, 0))
            if game.state == State.WIN:
                draw_result(screen, game, "win")
            elif game.state == State.FAIL:
                draw_result(screen, game, "fail")
        else:
            screen.fill(C_BG)
            draw_dot_grid(screen)
            draw_result(screen, game, "clear")

        draw_transition_overlay(screen, game)
        pygame.display.flip()
        try:
            pygame.event.pump()
        except Exception:
            pass

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
