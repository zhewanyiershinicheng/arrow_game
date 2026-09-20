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
# 常量
# ---------------------------------------------------------------------------
WINDOW_W, WINDOW_H = 900, 720
FPS = 60

CELL = 68
GRID_N = 5
TOTAL_LEVELS = 4
MISSES_PER_LEVEL = 3  # 可失误次数；为 0 后再错才失败

COLOR_BG = (24, 28, 38)
COLOR_PANEL = (36, 42, 56)
COLOR_PANEL_LIGHT = (48, 56, 74)
COLOR_BORDER = (70, 82, 110)
COLOR_TEXT = (236, 240, 248)
COLOR_TEXT_DIM = (140, 150, 170)
COLOR_ACCENT = (86, 156, 255)
COLOR_SUCCESS = (72, 200, 130)
COLOR_DANGER = (240, 96, 96)
COLOR_WARN = (255, 186, 73)
COLOR_GRID = (52, 60, 78)
COLOR_CELL = (40, 46, 60)
COLOR_CELL_HOVER = (52, 62, 84)

ARROW_COLORS = {
    0: (255, 210, 90),
    1: (120, 200, 255),
    2: (180, 140, 255),
    3: (255, 140, 120),
}

DIR_NAME = {0: "上", 1: "下", 2: "左", 3: "右"}
DIR_DELTA = {0: (-1, 0), 1: (1, 0), 2: (0, -1), 3: (0, 1)}
DIR_CHAR = {0: "U", 1: "D", 2: "L", 3: "R"}
CHAR_DIR = {"U": 0, "D": 1, "L": 2, "R": 3}
CN_NUM = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]

HUD_H = 96
BOTTOM_H = 76
BANNER_H = 40
BOARD_AREA_TOP = HUD_H + BANNER_H + 8
BOARD_AREA_BOTTOM = WINDOW_H - BOTTOM_H - 8

FLY_SPEED = 950.0
BUMP_AMPLITUDE = 12.0
BUMP_DURATION = 0.5
SHAKE_AMPLITUDE = 5.0

RESULT_PANEL_W = 480
RESULT_PANEL_H = 420


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


@dataclass
class FloatText:
    text: str
    x: float
    y: float
    color: Tuple[int, int, int]
    t: float = 0.0
    life: float = 0.9


@dataclass
class Button:
    rect: pygame.Rect
    label: str
    action: str
    color: Tuple[int, int, int] = COLOR_ACCENT
    hover: bool = False


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
    shake: float = 0.0
    banner: str = ""
    banner_timer: float = 0.0
    board_origin: Tuple[int, int] = (0, 0)
    pending_fail: bool = False
    pending_win: bool = False
    level_name: str = ""
    level_desc: str = ""
    level_grid: List[str] = field(default_factory=list)
    arrow_count: int = 0

    def alive_arrows(self) -> List[Arrow]:
        return [a for a in self.arrows if a.alive]


# ---------------------------------------------------------------------------
# 关卡逻辑 / 求解
# ---------------------------------------------------------------------------
def arrow_count_for_level(index: int) -> int:
    """难度随箭头数量上升。"""
    return 5 + index * 2  # 5, 7, 9, 11


def level_title(index: int) -> str:
    n = index + 1
    cn = CN_NUM[index] if index < len(CN_NUM) else str(n)
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
    """blocker 是否落在 target 前进路径上。"""
    dr, dc = DIR_DELTA[target.direction]
    r, c = target.row + dr, target.col + dc
    while 0 <= r < rows and 0 <= c < cols:
        if r == blocker.row and c == blocker.col:
            return True
        r += dr
        c += dc
    return False


def _try_reverse_construct(rows: int, cols: int, n: int) -> Optional[List[str]]:
    """逆序构造保证有解的地图。

    按消除顺序的逆序放置箭头：新放的箭头不得被「已放置（更晚消除）」的箭头阻挡。
    这样正向按放置的逆序消除时，每一步前方都无更晚消除的箭头。
    优先选择能挡住已放置箭头的位置，以形成初始阻挡、提高难度。
    """
    occupied = set()
    placed: List[Arrow] = []  # 放置顺序 = 消除顺序的逆（先放的后消）

    all_cells = [(r, c) for r in range(rows) for c in range(cols)]
    if n > len(all_cells):
        n = len(all_cells)

    for _ in range(n):
        free_cells = [(r, c) for r, c in all_cells if (r, c) not in occupied]
        random.shuffle(free_cells)
        # 限制候选规模，避免过慢
        free_cells = free_cells[: min(36, len(free_cells))]
        dirs = [0, 1, 2, 3]
        random.shuffle(dirs)

        best: List[Tuple[int, int, int, int]] = []  # score, r, c, d
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
    """生成指定难度的可解随机地图，返回 (grid, arrow_count)。"""
    target = min(arrow_count_for_level(level_index), rows * cols)
    attempts = [(target, 100), (target - 1, 40), (max(4, target - 2), 20)]
    for n, tries in attempts:
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
    # 极端兜底（应几乎不会走到）
    fallback = [
        "R.R..",
        "..U..",
        ".....",
        "L...D",
        ".....",
    ]
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
    game.level_desc = f"随机地图 · {arrow_n} 支箭头 · 可失误 {MISSES_PER_LEVEL} 次"
    game.misses_max = MISSES_PER_LEVEL
    game.misses_left = MISSES_PER_LEVEL
    game.floats.clear()
    game.shake = 0.0
    game.banner = f"{game.level_name}（{arrow_n} 箭头）"
    game.banner_timer = 1.3
    game.pending_fail = False
    game.pending_win = False
    game.state = State.PLAYING
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
            r"C:\Windows\Fonts\simsun.ttc",
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
    color=COLOR_TEXT,
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


def draw_text_center(
    surf: pygame.Surface,
    text: str,
    cx: int,
    cy: int,
    size: int,
    color=COLOR_TEXT,
    bold: bool = False,
) -> pygame.Rect:
    return draw_text(surf, text, cx, cy, size, color, center=True, bold=bold)


# ---------------------------------------------------------------------------
# 箭头绘制
# ---------------------------------------------------------------------------
def arrow_polygon(direction: int, cx: float, cy: float, scale: float = 1.0) -> List[Tuple[float, float]]:
    s = 17 * scale
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
        t = min(1.0, arrow.flash)
        color = (
            int(color[0] * (1 - t) + COLOR_DANGER[0] * t),
            int(color[1] * (1 - t) + COLOR_DANGER[1] * t),
            int(color[2] * (1 - t) + COLOR_DANGER[2] * t),
        )
    poly = arrow_polygon(arrow.direction, cx, cy)
    shadow = [(x + 2, y + 3) for x, y in poly]
    sh_surf = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
    pygame.draw.polygon(sh_surf, (0, 0, 0, 55), shadow)
    surf.blit(sh_surf, (0, 0))
    a = max(0, min(255, int(alpha)))
    if a >= 255:
        pygame.draw.polygon(surf, color, poly)
        pygame.draw.polygon(surf, (20, 24, 32), poly, 2)
    else:
        layer = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
        pygame.draw.polygon(layer, (*color, a), poly)
        pygame.draw.polygon(layer, (20, 24, 32, a), poly, 2)
        surf.blit(layer, (0, 0))


# ---------------------------------------------------------------------------
# 按钮
# ---------------------------------------------------------------------------
def make_button(rect: pygame.Rect, label: str, action: str, color=COLOR_ACCENT) -> Button:
    return Button(rect=rect, label=label, action=action, color=color)


def result_panel_rect() -> pygame.Rect:
    return pygame.Rect(
        (WINDOW_W - RESULT_PANEL_W) // 2,
        (WINDOW_H - RESULT_PANEL_H) // 2 - 8,
        RESULT_PANEL_W,
        RESULT_PANEL_H,
    )


def rebuild_buttons(game: Game) -> None:
    game.buttons.clear()
    cx = WINDOW_W // 2

    if game.state == State.MENU:
        game.buttons.append(make_button(pygame.Rect(cx - 120, 470, 240, 54), "开始游戏", "start", COLOR_ACCENT))

    elif game.state == State.PLAYING:
        y = WINDOW_H - BOTTOM_H + 18
        game.buttons.append(make_button(pygame.Rect(48, y, 140, 42), "重新开始", "restart", COLOR_WARN))
        game.buttons.append(make_button(pygame.Rect(208, y, 140, 42), "返回菜单", "menu", COLOR_PANEL_LIGHT))

    elif game.state == State.WIN:
        panel = result_panel_rect()
        nxt = "下一关" if game.level_index + 1 < TOTAL_LEVELS else "查看结果"
        game.buttons.append(make_button(pygame.Rect(cx - 120, panel.top + 240, 240, 50), nxt, "next", COLOR_SUCCESS))
        game.buttons.append(make_button(pygame.Rect(cx - 120, panel.top + 304, 240, 44), "重玩本关", "restart", COLOR_PANEL_LIGHT))
        game.buttons.append(make_button(pygame.Rect(cx - 120, panel.top + 358, 240, 44), "返回菜单", "menu", COLOR_PANEL_LIGHT))

    elif game.state == State.FAIL:
        panel = result_panel_rect()
        game.buttons.append(make_button(pygame.Rect(cx - 120, panel.top + 240, 240, 50), "重新开始", "restart", COLOR_DANGER))
        game.buttons.append(make_button(pygame.Rect(cx - 120, panel.top + 304, 240, 44), "返回菜单", "menu", COLOR_PANEL_LIGHT))

    elif game.state == State.ALL_CLEAR:
        panel = result_panel_rect()
        game.buttons.append(make_button(pygame.Rect(cx - 120, panel.top + 240, 240, 50), "再玩一遍", "start", COLOR_SUCCESS))
        game.buttons.append(make_button(pygame.Rect(cx - 120, panel.top + 304, 240, 44), "返回菜单", "menu", COLOR_PANEL_LIGHT))


def draw_button(surf: pygame.Surface, btn: Button) -> None:
    bg = btn.color
    if btn.hover:
        bg = tuple(min(255, c + 28) for c in bg)
    pygame.draw.rect(surf, bg, btn.rect, border_radius=10)
    pygame.draw.rect(surf, COLOR_BORDER, btn.rect, width=2, border_radius=10)
    draw_text_center(surf, btn.label, btn.rect.centerx, btn.rect.centery, 20, COLOR_TEXT, bold=True)


# ---------------------------------------------------------------------------
# 界面绘制
# ---------------------------------------------------------------------------
def draw_panel(surf: pygame.Surface, rect: pygame.Rect, fill=COLOR_PANEL) -> None:
    pygame.draw.rect(surf, fill, rect, border_radius=12)
    pygame.draw.rect(surf, COLOR_BORDER, rect, width=2, border_radius=12)


def draw_menu(surf: pygame.Surface, game: Game) -> None:
    for x in range(0, WINDOW_W, 48):
        pygame.draw.line(surf, (30, 34, 46), (x, 0), (x, WINDOW_H), 1)
    for y in range(0, WINDOW_H, 48):
        pygame.draw.line(surf, (30, 34, 46), (0, y), (WINDOW_W, y), 1)

    cx = WINDOW_W // 2
    draw_text_center(surf, "一箭又一箭", cx, 120, 54, COLOR_ACCENT, bold=True)
    draw_text_center(surf, "点击箭头 · 解开阻挡 · 清空棋盘", cx, 170, 18, COLOR_TEXT_DIM)

    panel = pygame.Rect(cx - 320, 210, 640, 200)
    draw_panel(surf, panel)
    rules = [
        "点击箭头：前方无阻挡时，飞出棋盘并消除",
        "前方有阻挡：碰撞反馈，并消耗一次可失误次数",
        "可失误次数为 0 后再错，本关失败；清空箭头过关",
        f"地图每次随机生成，箭头越多越难 · 共 {TOTAL_LEVELS} 关",
        f"每关可失误 {MISSES_PER_LEVEL} 次",
    ]
    for i, line in enumerate(rules):
        draw_text_center(surf, line, cx, 238 + i * 34, 17, COLOR_TEXT)

    for d, dx in enumerate((-120, -40, 40, 120)):
        poly = arrow_polygon(d, cx + dx, 440, 0.95)
        pygame.draw.polygon(surf, ARROW_COLORS[d], poly)
        pygame.draw.polygon(surf, (20, 24, 32), poly, 2)

    for btn in game.buttons:
        draw_button(surf, btn)

    draw_text_center(surf, "鼠标点击操作 · R 重新开始（换新图） · Esc 返回菜单", cx, 640, 15, COLOR_TEXT_DIM)
    draw_text_center(surf, "Pygame 实现 · 逆序构造保证关卡有解", cx, 670, 13, COLOR_TEXT_DIM)


def draw_hud(surf: pygame.Surface, game: Game) -> None:
    pygame.draw.rect(surf, COLOR_PANEL, pygame.Rect(0, 0, WINDOW_W, HUD_H))
    pygame.draw.line(surf, COLOR_BORDER, (0, HUD_H), (WINDOW_W, HUD_H), 2)

    alive = len(game.alive_arrows())
    total = len(game.arrows)

    draw_text(surf, game.level_name, 36, 22, 24, COLOR_TEXT, bold=True)
    draw_text(surf, game.level_desc, 36, 58, 15, COLOR_TEXT_DIM)

    miss_color = (
        COLOR_SUCCESS
        if game.misses_left > 1
        else COLOR_WARN
        if game.misses_left == 1
        else COLOR_DANGER
    )
    stats = [
        ("关卡", f"{game.level_index + 1}/{TOTAL_LEVELS}", COLOR_TEXT),
        ("剩余箭头", f"{alive}/{total}", COLOR_ACCENT),
        ("可失误", f"{game.misses_left}/{game.misses_max}", miss_color),
    ]
    right = WINDOW_W - 36
    widths = [120, 140, 140]
    for i in range(len(stats) - 1, -1, -1):
        label, value, color = stats[i]
        w = widths[i]
        box_cx = right - w // 2
        draw_text_center(surf, label, box_cx, 28, 14, COLOR_TEXT_DIM)
        draw_text_center(surf, value, box_cx, 58, 26, color, bold=True)
        right -= w + 12


def draw_board(surf: pygame.Surface, game: Game) -> None:
    ox, oy = game.board_origin
    pad = 14
    panel = pygame.Rect(ox - pad, oy - pad, game.cols * CELL + pad * 2, game.rows * CELL + pad * 2)
    draw_panel(surf, panel)

    mouse = pygame.mouse.get_pos()
    input_locked = game.pending_fail or game.pending_win or game.state != State.PLAYING

    for r in range(game.rows):
        for c in range(game.cols):
            rect = cell_rect(game, r, c)
            fill = COLOR_CELL
            if (not input_locked) and rect.collidepoint(mouse):
                fill = COLOR_CELL_HOVER
            pygame.draw.rect(surf, fill, rect, border_radius=6)
            pygame.draw.rect(surf, COLOR_GRID, rect, width=1, border_radius=6)

    for arrow in game.arrows:
        if not arrow.alive:
            if arrow.anim != "flying" or arrow.alpha <= 5:
                continue
        rect = cell_rect(game, arrow.row, arrow.col)
        draw_arrow(surf, arrow, rect, alpha=arrow.alpha)

    for ft in game.floats:
        draw_text_center(surf, ft.text, int(ft.x), int(ft.y), 20, ft.color, bold=True)


def draw_banner(surf: pygame.Surface, game: Game) -> None:
    if game.banner_timer <= 0:
        return
    a = min(1.0, game.banner_timer / 0.25)
    bar = pygame.Surface((WINDOW_W, BANNER_H), pygame.SRCALPHA)
    bar.fill((0, 0, 0, int(130 * a)))
    surf.blit(bar, (0, HUD_H))
    draw_text_center(
        surf,
        game.banner,
        WINDOW_W // 2,
        HUD_H + BANNER_H // 2,
        18,
        COLOR_TEXT,
        bold=True,
    )


def draw_bottom_bar(surf: pygame.Surface, game: Game) -> None:
    bar = pygame.Rect(0, WINDOW_H - BOTTOM_H, WINDOW_W, BOTTOM_H)
    pygame.draw.rect(surf, COLOR_PANEL, bar)
    pygame.draw.line(surf, COLOR_BORDER, (0, WINDOW_H - BOTTOM_H), (WINDOW_W, WINDOW_H - BOTTOM_H), 2)
    for btn in game.buttons:
        draw_button(surf, btn)
    draw_text_center(
        surf,
        "点击箭头尝试飞出 · R 重开新图 · Esc 菜单",
        WINDOW_W - 230,
        WINDOW_H - BOTTOM_H // 2,
        15,
        COLOR_TEXT_DIM,
    )


def draw_result(surf: pygame.Surface, game: Game, kind: str) -> None:
    overlay = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
    overlay.fill((10, 12, 18, 190))
    surf.blit(overlay, (0, 0))

    panel = result_panel_rect()
    draw_panel(surf, panel, COLOR_PANEL_LIGHT)
    cx = panel.centerx
    top = panel.top

    if kind == "win":
        draw_text_center(surf, "通关！", cx, top + 70, 48, COLOR_SUCCESS, bold=True)
        draw_text_center(surf, game.level_name, cx, top + 125, 20, COLOR_TEXT)
        draw_text_center(surf, f"本关 {game.arrow_count} 支箭头已全部清除", cx, top + 160, 16, COLOR_TEXT_DIM)
        draw_text_center(
            surf,
            f"剩余可失误：{game.misses_left} / {game.misses_max}",
            cx,
            top + 190,
            16,
            COLOR_TEXT_DIM,
        )
    elif kind == "fail":
        draw_text_center(surf, "挑战失败", cx, top + 70, 48, COLOR_DANGER, bold=True)
        draw_text_center(surf, game.level_name, cx, top + 125, 20, COLOR_TEXT)
        draw_text_center(surf, "可失误次数为 0 后再次失误", cx, top + 160, 16, COLOR_TEXT_DIM)
        left = len(game.alive_arrows())
        draw_text_center(surf, f"仍有 {left} 个箭头未清除", cx, top + 190, 16, COLOR_TEXT_DIM)
    else:
        draw_text_center(surf, "全部通关！", cx, top + 90, 48, COLOR_SUCCESS, bold=True)
        draw_text_center(surf, "你已成功解开全部随机关卡", cx, top + 150, 18, COLOR_TEXT)
        draw_text_center(surf, "感谢游玩「一箭又一箭」", cx, top + 185, 16, COLOR_TEXT_DIM)

    for btn in game.buttons:
        draw_button(surf, btn)


# ---------------------------------------------------------------------------
# 输入与交互
# ---------------------------------------------------------------------------
def handle_action(game: Game, action: str) -> None:
    if action == "start":
        load_level(game, 0)
        rebuild_buttons(game)
    elif action == "restart":
        # 重新开始 = 本关重新随机生成
        load_level(game, game.level_index)
        rebuild_buttons(game)
    elif action == "menu":
        game.state = State.MENU
        game.floats.clear()
        game.pending_fail = False
        game.pending_win = False
        rebuild_buttons(game)
    elif action == "next":
        nxt = game.level_index + 1
        if nxt < TOTAL_LEVELS:
            load_level(game, nxt)
        else:
            game.state = State.ALL_CLEAR
        rebuild_buttons(game)


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
        rect = cell_rect(game, row, col)
        game.floats.append(FloatText("消除", rect.centerx, rect.centery, COLOR_SUCCESS))
        game.banner = f"箭头向{DIR_NAME[target.direction]}飞出"
        game.banner_timer = 0.8
        if not game.alive_arrows():
            game.pending_win = True
        return

    # 碰撞：先播动效
    target.anim = "bump"
    target.anim_t = 0.0
    target.flash = 1.0
    game.shake = SHAKE_AMPLITUDE
    rect = cell_rect(game, row, col)
    game.floats.append(FloatText("阻挡！", rect.centerx, rect.top - 6, COLOR_DANGER))

    # 规则：次数归零本身不失败；次数已是 0 时再错才失败
    if game.misses_left <= 0:
        game.floats.append(FloatText("失误耗尽", rect.centerx, rect.bottom + 8, COLOR_DANGER))
        game.banner = "可失误次数已为 0，本次失误导致失败"
        game.banner_timer = 1.2
        game.pending_fail = True
    else:
        game.misses_left -= 1
        if game.misses_left == 0:
            game.floats.append(FloatText("可失误已用完", rect.centerx, rect.bottom + 8, COLOR_WARN))
            game.banner = "前方有阻挡！可失误次数已为 0，再错将失败"
        else:
            game.floats.append(FloatText(f"还可失误 {game.misses_left}", rect.centerx, rect.bottom + 8, COLOR_WARN))
            game.banner = f"前方有阻挡，无法飞出（还可失误 {game.misses_left} 次）"
        game.banner_timer = 1.0


def on_mouse_down(game: Game, pos: Tuple[int, int]) -> None:
    for btn in game.buttons:
        if btn.rect.collidepoint(pos):
            handle_action(game, btn.action)
            return

    if game.state == State.PLAYING and not game.pending_fail and not game.pending_win:
        for a in game.arrows:
            if not a.alive:
                continue
            if cell_rect(game, a.row, a.col).collidepoint(pos):
                click_arrow(game, a.row, a.col)
                break


# ---------------------------------------------------------------------------
# 动画与延迟结算
# ---------------------------------------------------------------------------
def math_damp(x: float) -> float:
    return math.exp(-4.0 * x) * math.sin(14.0 * x)


def update_animations(game: Game, dt: float) -> None:
    if game.shake > 0:
        game.shake = max(0.0, game.shake - dt * 20)
    if game.banner_timer > 0:
        game.banner_timer = max(0.0, game.banner_timer - dt)

    new_floats = []
    for ft in game.floats:
        ft.t += dt
        ft.y -= 36 * dt
        if ft.t < ft.life:
            new_floats.append(ft)
    game.floats = new_floats

    for a in game.arrows:
        if a.anim == "flying":
            a.anim_t += dt
            dr, dc = DIR_DELTA[a.direction]
            dist = FLY_SPEED * a.anim_t
            a.ox = dc * dist
            a.oy = dr * dist
            a.alpha = max(0.0, 255 - dist * 0.4)
            if a.alpha <= 2 or a.anim_t > 1.0:
                a.anim = ""
                a.ox = a.oy = 0
                a.alpha = 0
        elif a.anim == "bump":
            a.anim_t += dt
            dr, dc = DIR_DELTA[a.direction]
            t = a.anim_t
            if t >= BUMP_DURATION:
                a.anim = ""
                a.ox = a.oy = 0
                a.flash = 0.0
            else:
                phase = t / BUMP_DURATION
                if phase < 0.35:
                    dist = BUMP_AMPLITUDE * (phase / 0.35)
                else:
                    back = (phase - 0.35) / 0.65
                    dist = BUMP_AMPLITUDE * (1 - back) * (0.35 * ((-1) ** int(back * 6)))
                    dist += BUMP_AMPLITUDE * (1 - back) * math_damp(back)
                a.ox = dc * dist
                a.oy = dr * dist
                wobble = 3.5 * (1 - phase) * (1 if int(phase * 10) % 2 == 0 else -1)
                a.ox += -dr * wobble
                a.oy += dc * wobble
                a.flash = max(0.0, 1.0 - phase * 1.3)
        else:
            a.flash = max(0.0, a.flash - dt * 2)

    if game.pending_fail and game.state == State.PLAYING:
        if not any(a.anim == "bump" for a in game.arrows):
            game.pending_fail = False
            game.state = State.FAIL
            rebuild_buttons(game)

    if game.pending_win and game.state == State.PLAYING:
        if not any(a.anim == "flying" for a in game.arrows):
            game.pending_win = False
            game.state = State.WIN
            rebuild_buttons(game)


# ---------------------------------------------------------------------------
# 主循环
# ---------------------------------------------------------------------------
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
                if event.key == pygame.K_ESCAPE:
                    if game.state != State.MENU:
                        handle_action(game, "menu")
                elif event.key == pygame.K_r and game.state == State.PLAYING:
                    handle_action(game, "restart")
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                on_mouse_down(game, event.pos)
            elif event.type == pygame.MOUSEMOTION:
                for btn in game.buttons:
                    btn.hover = btn.rect.collidepoint(event.pos)

        update_animations(game, dt)
        screen.fill(COLOR_BG)

        if game.state == State.MENU:
            draw_menu(screen, game)
        elif game.state in (State.PLAYING, State.WIN, State.FAIL):
            offset = (0, 0)
            if game.shake > 0:
                offset = (
                    random.randint(-int(game.shake), int(game.shake)),
                    random.randint(-int(game.shake), int(game.shake)),
                )
            world = pygame.Surface((WINDOW_W, WINDOW_H))
            world.fill(COLOR_BG)
            draw_hud(world, game)
            draw_banner(world, game)
            draw_board(world, game)
            draw_bottom_bar(world, game)
            screen.blit(world, offset)
            if game.state == State.WIN:
                draw_result(screen, game, "win")
            elif game.state == State.FAIL:
                draw_result(screen, game, "fail")
        elif game.state == State.ALL_CLEAR:
            draw_result(screen, game, "clear")

        pygame.display.flip()

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
