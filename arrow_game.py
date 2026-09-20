# -*- coding: utf-8 -*-
"""一箭又一箭 — 箭头解谜小游戏

规则：点击箭头，若其前进方向到棋盘边界之间无其他箭头，则飞出并消除；
若被阻挡，则消耗一次可失误次数。可失误次数为 0 后再错，本关失败。
地图按关卡难度随机生成，并用逆序构造 + 求解器保证有解。

"""

from __future__ import annotations

import math
import os
import random
import sys
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
RESULT_PANEL_H = 400
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

    def alive_arrows(self) -> List[Arrow]:
        return [a for a in self.arrows if a.alive]


# ---------------------------------------------------------------------------
# 玩法：生成 / 判定（逻辑不变）
# ---------------------------------------------------------------------------
def arrow_count_for_level(index: int) -> int:
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
        free_cells = free_cells[: min(36, len(free_cells))]
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
        pool = [item for item in best if item[0] >= max(0, top - 1)][:12]
        _, r, c, d = random.choice(pool)
        placed.append(Arrow(row=r, col=c, direction=d))
        occupied.add((r, c))
    return grid_from_arrows(placed, rows, cols)


def generate_solvable_grid(level_index: int, rows: int = GRID_N, cols: int = GRID_N) -> Tuple[List[str], int]:
    target = min(arrow_count_for_level(level_index), rows * cols)
    for n, tries in [(target, 100), (target - 1, 40), (max(4, target - 2), 20)]:
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
    grid, arrow_n = generate_solvable_grid(index)
    rows, cols, arrows = parse_level(grid)
    game.level_index = index
    game.rows = rows
    game.cols = cols
    game.arrows = arrows
    game.level_grid = grid
    game.arrow_count = arrow_n
    game.level_name = level_title(index)
    game.level_desc = f"随机地图 · {arrow_n} 箭头 · 可失误 {MISSES_PER_LEVEL} 次"
    game.misses_max = MISSES_PER_LEVEL
    game.misses_left = MISSES_PER_LEVEL
    game.floats.clear()
    game.particles.clear()
    game.shake = 0.0
    game.hit_flash = 0.0
    game.banner = f"{game.level_name} · {arrow_n} 支箭头"
    game.banner_timer = 1.3
    game.pending_fail = False
    game.pending_win = False
    game.modal_t = 0.0
    game.level_enter = 0.0
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
    a = max(0, min(255, int(alpha * (arrow.alpha / 255.0 if arrow.anim else 1.0))))
    if arrow.anim == "flying":
        a = max(0, min(255, int(alpha)))

    # 飞出拖尾
    if arrow.anim == "flying" and a > 8:
        layer = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
        for i in range(1, 5):
            k = i / 5.0
            gx = cx - arrow.ox * k * 0.55
            gy = cy - arrow.oy * k * 0.55
            gpoly = arrow_polygon(arrow.direction, gx, gy, scale * (1.0 - 0.12 * i))
            ga = int(a * (0.35 - i * 0.06))
            if ga <= 0:
                continue
            pygame.draw.polygon(layer, (*color, ga), gpoly)
        surf.blit(layer, (0, 0))

    if a >= 250:
        shadow = [(x + 1.5, y + 2) for x, y in poly]
        sh = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
        pygame.draw.polygon(sh, (*C_SHADOW, 40), shadow)
        surf.blit(sh, (0, 0))
        pygame.draw.polygon(surf, color, poly)
        pygame.draw.polygon(surf, ARROW_STROKE, poly, max(1, int(2 * scale)))
        # 碰撞高亮描边
        if arrow.flash > 0.35:
            pygame.draw.polygon(surf, C_DANGER, poly, 2)
    else:
        layer = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
        pygame.draw.polygon(layer, (*color, a), poly)
        pygame.draw.polygon(layer, (*ARROW_STROKE, a), poly, max(1, int(2 * scale)))
        surf.blit(layer, (0, 0))


def spawn_sparks(game: Game, x: float, y: float, color, n: int = 10, speed: float = 160.0) -> None:
    for _ in range(n):
        ang = random.uniform(0, math.tau)
        sp = random.uniform(speed * 0.45, speed)
        life = random.uniform(0.25, 0.55)
        game.particles.append(
            Particle(
                x=x,
                y=y,
                vx=math.cos(ang) * sp,
                vy=math.sin(ang) * sp,
                life=life,
                max_life=life,
                color=color,
                size=random.uniform(2.0, 4.2),
                kind="spark",
            )
        )


def spawn_ring(game: Game, x: float, y: float, color, life: float = 0.4) -> None:
    game.particles.append(
        Particle(x=x, y=y, vx=0, vy=0, life=life, max_life=life, color=color, size=8, kind="ring")
    )


def spawn_confetti(game: Game, cx: float, cy: float, n: int = 36) -> None:
    palette = [C_PRIMARY, C_SUCCESS, C_WARN, (139, 92, 246), (14, 165, 233), (234, 88, 12)]
    for _ in range(n):
        ang = random.uniform(-math.pi, 0)
        sp = random.uniform(120, 320)
        life = random.uniform(0.7, 1.4)
        game.particles.append(
            Particle(
                x=cx + random.uniform(-40, 40),
                y=cy + random.uniform(-20, 20),
                vx=math.cos(ang) * sp,
                vy=math.sin(ang) * sp - random.uniform(40, 120),
                life=life,
                max_life=life,
                color=random.choice(palette),
                size=random.uniform(3.5, 7.0),
                kind="confetti",
                rot=random.uniform(0, math.tau),
                vr=random.uniform(-8, 8),
            )
        )


def spawn_trail_sparks(game: Game, arrow: Arrow, rect: pygame.Rect) -> None:
    if arrow.anim != "flying":
        return
    if random.random() > 0.45:
        return
    cx = rect.centerx + arrow.ox
    cy = rect.centery + arrow.oy
    spawn_sparks(game, cx, cy, ARROW_COLORS[arrow.direction], n=2, speed=70)


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


def rebuild_buttons(game: Game) -> None:
    game.buttons.clear()
    cx = WINDOW_W // 2

    def add(rect, label, action, kind="primary"):
        game.buttons.append(make_button(rect, label, action, kind, enter=0.0))

    if game.state == State.MENU:
        add(pygame.Rect(cx - 120, 488, 240, 52), "开始游戏", "start", "primary")

    elif game.state == State.PLAYING:
        y = WINDOW_H - BOTTOM_H + 18
        add(pygame.Rect(48, y, 136, 42), "重新开始", "restart", "secondary")
        add(pygame.Rect(200, y, 136, 42), "返回菜单", "menu", "secondary")

    elif game.state == State.WIN:
        panel = result_panel_rect()
        nxt = "下一关" if game.level_index + 1 < TOTAL_LEVELS else "查看结果"
        add(pygame.Rect(cx - 110, panel.top + 230, 220, 48), nxt, "next", "primary")
        add(pygame.Rect(cx - 110, panel.top + 290, 220, 44), "重玩本关", "restart", "secondary")
        add(pygame.Rect(cx - 110, panel.top + 344, 220, 44), "返回菜单", "menu", "secondary")

    elif game.state == State.FAIL:
        panel = result_panel_rect()
        add(pygame.Rect(cx - 110, panel.top + 230, 220, 48), "重新开始", "restart", "danger")
        add(pygame.Rect(cx - 110, panel.top + 290, 220, 44), "返回菜单", "menu", "secondary")

    elif game.state == State.ALL_CLEAR:
        panel = result_panel_rect()
        add(pygame.Rect(cx - 110, panel.top + 230, 220, 48), "再玩一遍", "start", "primary")
        add(pygame.Rect(cx - 110, panel.top + 290, 220, 44), "返回菜单", "menu", "secondary")


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
    target = surf
    layer = None
    if need_fade:
        layer = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
        target = layer

    if btn.kind == "primary":
        fill = mix(C_PRIMARY, C_PRIMARY_DEEP, 0.45 * btn.hover_t + 0.2 * press)
        sh = pygame.Surface((r.w + 12, r.h + 12), pygame.SRCALPHA)
        sh_a = int((30 + 18 * btn.hover_t - 12 * press) * (alpha / 255))
        pygame.draw.rect(sh, (*C_PRIMARY, max(0, sh_a)), pygame.Rect(4, 6 + int(2 * btn.hover_t), r.w, r.h), border_radius=RADIUS_BTN)
        target.blit(sh, (r.x - 4, r.y - 2))
        pygame.draw.rect(target, fill, r, border_radius=RADIUS_BTN)
        draw_text_center(target, btn.label, r.centerx, r.centery, 18, (255, 255, 255), bold=True)
    elif btn.kind == "danger":
        fill = mix(C_DANGER, (185, 28, 28), 0.35 * btn.hover_t + 0.2 * press)
        pygame.draw.rect(target, fill, r, border_radius=RADIUS_BTN)
        draw_text_center(target, btn.label, r.centerx, r.centery, 18, (255, 255, 255), bold=True)
    elif btn.kind == "warn":
        fill = mix(C_WARN, (217, 119, 6), 0.35 * btn.hover_t + 0.2 * press)
        pygame.draw.rect(target, fill, r, border_radius=RADIUS_BTN)
        draw_text_center(target, btn.label, r.centerx, r.centery, 18, (255, 255, 255), bold=True)
    else:
        fill = mix(C_CARD, C_PRIMARY_SOFT, btn.hover_t)
        border = mix(C_BORDER_STRONG, C_PRIMARY, btn.hover_t)
        pygame.draw.rect(target, fill, r, border_radius=RADIUS_BTN)
        pygame.draw.rect(target, border, r, width=1 + int(btn.hover_t), border_radius=RADIUS_BTN)
        text_c = mix(C_INK, C_PRIMARY_DEEP, btn.hover_t)
        draw_text_center(target, btn.label, r.centerx, r.centery, 18, text_c, bold=True)

    if layer is not None:
        layer.set_alpha(alpha)
        surf.blit(layer, (0, 0))


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
    # 标题区（入场轻微上移+淡入）
    ty = 140 - int((1 - st) * 28)
    title_a = st
    _draw_text_alpha(surf, "一箭又一箭", cx, ty, 48, C_INK, True, title_a)
    _draw_text_alpha(surf, "点击箭头 · 解开阻挡 · 清空棋盘", cx, ty + 48, 16, C_MUTED, False, title_a)

    # 主强调线
    acc_w = int(72 * st)
    accent = pygame.Rect(cx - acc_w // 2, 210, acc_w, 4)
    pygame.draw.rect(surf, C_PRIMARY, accent, border_radius=2)

    # 规则卡片
    card_t = ease_out_cubic(max(0.0, (game.screen_t - 0.08) / 0.92)) if game.screen_t else 1.0
    panel = pygame.Rect(cx - 300, 240 + int((1 - card_t) * 18), 600, 200)
    if card_t > 0.02:
        _draw_card_alpha(surf, panel, int(255 * card_t))
        band = pygame.Rect(panel.x, panel.y, panel.w, 4)
        pygame.draw.rect(surf, C_PRIMARY, band, border_radius=2)
        rules = [
            "点击箭头：前方无阻挡时，飞出棋盘并消除",
            "前方有阻挡：碰撞反馈，并消耗一次可失误次数",
            "清空箭头过关",
            f"地图每次随机生成，共 {TOTAL_LEVELS} 关",
            f"每关只能失误 {MISSES_PER_LEVEL} 次",
        ]
        for i, line in enumerate(rules):
            num_rect = pygame.Rect(panel.x + 28, panel.y + 28 + i * 32, 22, 22)
            pygame.draw.rect(surf, C_PRIMARY_SOFT, num_rect, border_radius=11)
            draw_text_center(surf, str(i + 1), num_rect.centerx, num_rect.centery, 12, C_PRIMARY_DEEP, bold=True)
            draw_text(surf, line, panel.x + 62, panel.y + 32 + i * 32, 16, C_INK)

    # 方向图例
    legend_t = ease_out_cubic(max(0.0, (game.screen_t - 0.2) / 0.8)) if game.screen_t else 1.0
    labels = [(0, "上"), (1, "下"), (2, "左"), (3, "右")]
    lx = cx - 172
    for d, name in labels:
        chip = pygame.Rect(lx, 456 + int((1 - legend_t) * 10), 80, 28)
        if legend_t > 0.05:
            pygame.draw.rect(surf, C_CARD, chip, border_radius=14)
            pygame.draw.rect(surf, C_BORDER, chip, width=1, border_radius=14)
            poly = arrow_polygon(d, chip.x + 18, chip.centery, 0.42)
            pygame.draw.polygon(surf, ARROW_COLORS[d], poly)
            pygame.draw.polygon(surf, ARROW_STROKE, poly, 1)
            draw_text(surf, name, chip.x + 34, chip.y + 6, 13, C_MUTED)
        lx += 88

    for btn in game.buttons:
        draw_button(surf, btn)

    footer = pygame.Rect(0, WINDOW_H - 48, WINDOW_W, 48)
    pygame.draw.rect(surf, C_CARD, footer)
    pygame.draw.line(surf, C_BORDER, (0, WINDOW_H - 48), (WINDOW_W, WINDOW_H - 48), 1)
    draw_text_center(
        surf,
        "鼠标点击箭头 · 游戏中 R 重开新图 · Esc 返回菜单",
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

    # 左：关卡标识 + 名称
    tag = pygame.Rect(36, 20, 72, 24)
    pygame.draw.rect(surf, C_PRIMARY_SOFT, tag, border_radius=12)
    draw_text_center(surf, "LEVEL", tag.centerx, tag.centery, 11, C_PRIMARY_DEEP, bold=True)
    draw_text(surf, game.level_name, 120, 18, 22, C_INK, bold=True)
    draw_text(surf, game.level_desc, 36, 54, 14, C_MUTED)

    alive = len(game.alive_arrows())
    total = len(game.arrows)
    miss_color = (
        C_SUCCESS
        if game.misses_left > 1
        else C_WARN
        if game.misses_left == 1
        else C_DANGER
    )
    # 右侧三枚胶囊
    w = 118
    gap = 10
    x3 = WINDOW_W - 36 - w
    x2 = x3 - w - gap
    x1 = x2 - w - gap
    draw_stat_pill(surf, "关卡", f"{game.level_index + 1}/{TOTAL_LEVELS}", C_INK, x1, 18, w)
    draw_stat_pill(surf, "剩余箭头", f"{alive}/{total}", C_PRIMARY, x2, 18, w)
    draw_stat_pill(surf, "可失误", f"{game.misses_left}/{game.misses_max}", miss_color, x3, 18, w)


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
    if game.banner_timer <= 0:
        return
    a = min(1.0, game.banner_timer / 0.25)
    bar = pygame.Rect(WINDOW_W // 2 - 220, HUD_H + 8, 440, 32)
    bg = mix(C_BG, C_CARD, 0.92)
    s = pygame.Surface((bar.w, bar.h), pygame.SRCALPHA)
    s.fill((*bg, int(230 * a)))
    surf.blit(s, bar.topleft)
    pygame.draw.rect(surf, C_BORDER, bar, width=1, border_radius=16)
    draw_text_center(surf, game.banner, bar.centerx, bar.centery, 15, C_INK, bold=True)


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
        badge = pygame.Rect(cx - 48, top + 40, 96, 28)
        pygame.draw.rect(surf, C_PRIMARY_SOFT, badge, border_radius=14)
        draw_text_center(surf, "ALL CLEAR", badge.centerx, badge.centery, 12, C_PRIMARY_DEEP, bold=True)
        draw_text_center(surf, "全部通关！", cx, top + 100, 40, C_INK, bold=True)
        draw_text_center(surf, "你已成功解开全部随机关卡", cx, top + 150, 16, C_MUTED)
        draw_text_center(surf, "感谢游玩「一箭又一箭」", cx, top + 180, 15, C_MUTED)

    for btn in game.buttons:
        draw_button(surf, btn)


# ---------------------------------------------------------------------------
# 交互（逻辑不变；界面切换走 request_action 转场）
# ---------------------------------------------------------------------------
def apply_action(game: Game, action: str) -> None:
    """立即执行界面/关卡动作（供转场结束后与测试调用）。"""
    if action == "start":
        load_level(game, 0)
        rebuild_buttons(game)
        game.screen_t = 0.0
    elif action == "restart":
        load_level(game, game.level_index)
        rebuild_buttons(game)
        game.screen_t = 0.0
    elif action == "menu":
        game.state = State.MENU
        game.floats.clear()
        game.particles.clear()
        game.pending_fail = False
        game.pending_win = False
        game.modal_t = 0.0
        game.hit_flash = 0.0
        game.shake = 0.0
        rebuild_buttons(game)
        game.screen_t = 0.0
    elif action == "next":
        nxt = game.level_index + 1
        if nxt < TOTAL_LEVELS:
            load_level(game, nxt)
        else:
            game.state = State.ALL_CLEAR
            game.modal_t = 0.0
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
        if not game.alive_arrows():
            game.pending_win = True
            spawn_confetti(game, WINDOW_W // 2, WINDOW_H // 2 - 40, n=40)
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

    if game.misses_left <= 0:
        game.floats.append(FloatText("Game Over", rect.centerx, rect.bottom + 10, C_DANGER, life=1.0, size=16))
        game.banner = "失误次数归零，下次失误将导致游戏失败！"
        game.banner_timer = 1.2
        game.pending_fail = True
        game.hit_flash = 0.85
        game.shake = SHAKE_AMPLITUDE * 1.6
        spawn_confetti(game, WINDOW_W // 2, WINDOW_H // 2, n=0)
    else:
        game.misses_left -= 1
        if game.misses_left == 0:
            game.floats.append(FloatText("最后一次咯~", rect.centerx, rect.bottom + 10, C_WARN, life=1.0, size=16))
            game.banner = "失误次数归零，下次失误将导致游戏失败！"
        else:
            game.floats.append(
                FloatText(f"还可失误 {game.misses_left}", rect.centerx, rect.bottom + 10, C_WARN, life=0.9, size=16)
            )
            game.banner = f"前方有阻挡（还可失误 {game.misses_left} 次）"
        game.banner_timer = 1.0


def on_mouse_down(game: Game, pos: Tuple[int, int]) -> None:
    for btn in game.buttons:
        if btn.rect.collidepoint(pos):
            btn.press = 1.0
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
    alive_p: List[Particle] = []
    for p in game.particles:
        p.life -= dt
        if p.life <= 0:
            continue
        if p.kind == "ring":
            p.size += 220 * dt
        else:
            p.vy += 420 * dt  # 重力
            p.vx *= 0.98
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.rot += p.vr * dt
        alive_p.append(p)
    game.particles = alive_p


def draw_particles(surf: pygame.Surface, game: Game) -> None:
    if not game.particles:
        return
    layer = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
    for p in game.particles:
        k = max(0.0, p.life / p.max_life) if p.max_life else 0
        if p.kind == "ring":
            a = int(160 * k)
            if a <= 0:
                continue
            pygame.draw.circle(layer, (*p.color, a), (int(p.x), int(p.y)), int(p.size), 3)
        elif p.kind == "confetti":
            a = int(220 * k)
            if a <= 0:
                continue
            w, h = p.size, p.size * 0.55
            pts = []
            for dx, dy in ((-w, -h), (w, -h), (w, h), (-w, h)):
                ca, sa = math.cos(p.rot), math.sin(p.rot)
                pts.append((p.x + dx * ca - dy * sa, p.y + dx * sa + dy * ca))
            pygame.draw.polygon(layer, (*p.color, a), pts)
        else:
            a = int(200 * k)
            if a <= 0:
                continue
            r = max(1.0, p.size * (0.4 + 0.6 * k))
            pygame.draw.circle(layer, (*p.color, a), (int(p.x), int(p.y)), int(r))
    surf.blit(layer, (0, 0))


def update_animations(game: Game, dt: float) -> None:
    update_transition(game, dt)
    update_button_anim(game, dt)

    if game.shake > 0:
        game.shake = max(0.0, game.shake - dt * 22)
    if game.hit_flash > 0:
        game.hit_flash = max(0.0, game.hit_flash - dt * 2.4)
    if game.banner_timer > 0:
        game.banner_timer = max(0.0, game.banner_timer - dt)

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

    # 结果弹层入场
    if game.state in (State.WIN, State.FAIL, State.ALL_CLEAR):
        game.modal_t = min(1.0, game.modal_t + dt * 3.2)
    else:
        game.modal_t = 0.0

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
            rebuild_buttons(game)

    if game.pending_win and game.state == State.PLAYING:
        if not any(a.anim == "flying" for a in game.arrows):
            game.pending_win = False
            game.state = State.WIN
            game.modal_t = 0.0
            rebuild_buttons(game)


def handle_r_key(game: Game) -> None:
    """R：菜单开局；游戏中/胜负界面重开；全通关后重新开始。"""
    if game.trans_dir != 0:
        return
    if game.state == State.MENU:
        request_action(game, "start")
    elif game.state in (State.PLAYING, State.WIN, State.FAIL):
        request_action(game, "restart")
    elif game.state == State.ALL_CLEAR:
        request_action(game, "start")


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
    if game.trans_dir == 1:
        game.trans_t += dt / TRANS_OUT
        if game.trans_t >= 1.0:
            action = game.trans_pending or "menu"
            game.trans_pending = None
            apply_action(game, action)
            game.trans_dir = 2
            game.trans_t = 0.0
            game.screen_t = 0.0
    elif game.trans_dir == 2:
        game.trans_t += dt / TRANS_IN
        if game.trans_t >= 1.0:
            game.trans_dir = 0
            game.trans_t = 0.0
    # 界面内容入场
    if game.trans_dir == 0:
        game.screen_t = min(1.0, game.screen_t + dt * 2.8)
    elif game.trans_dir == 2:
        game.screen_t = min(1.0, game.screen_t + dt * 3.5)


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


def main() -> None:
    if os.environ.get("ARROW_GAME_HEADLESS") == "1":
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

    pygame.init()
    pygame.display.set_caption("一箭又一箭")
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    clock = pygame.time.Clock()
    game = Game()
    rebuild_buttons(game)

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE and game.state != State.MENU:
                    request_action(game, "menu")
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

        # 转场期间内容轻微上移淡入
        enter_y = 0
        if game.trans_dir == 2:
            enter_y = int((1.0 - ease_out_cubic(min(1.0, game.trans_t))) * 18)
        elif game.trans_dir == 0:
            enter_y = int((1.0 - ease_out_cubic(min(1.0, game.screen_t))) * 10)

        if game.state == State.MENU:
            draw_menu(screen, game)
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

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()



if __name__ == "__main__":
    main()
