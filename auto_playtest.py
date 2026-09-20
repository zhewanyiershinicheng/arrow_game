# -*- coding: utf-8 -*-
"""验证随机地图、可失误规则与 Stellar 界面绘制。"""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["ARROW_GAME_HEADLESS"] = "1"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame
import arrow_game as ag


def test_random_solvable():
    print("=== 随机地图可解性 ===")
    for level in range(ag.TOTAL_LEVELS):
        target = ag.arrow_count_for_level(level)
        grids = set()
        for _ in range(20):
            grid, n = ag.generate_solvable_grid(level)
            order = ag.solve_level(grid)
            total = sum(ch in ag.CHAR_DIR for row in grid for ch in row)
            assert order and len(order) == total, f"L{level+1} 无解"
            assert n == total
            assert n == target, f"L{level+1} 箭头数 {n} != 目标 {target}"
            grids.add(tuple(grid))
        print(f"L{level+1}: 箭头={target}, 不同地图 {len(grids)}/20")
        assert len(grids) >= 4


def test_miss_rule():
    print("=== 可失误次数规则 ===")
    g = ag.Game()
    ag.load_level(g, 2)
    mistakes = 0
    while mistakes < ag.MISSES_PER_LEVEL:
        target = next(
            (a for a in g.arrows if a.alive and a.anim != "bump" and ag.is_blocked(g.arrows, a, g.rows, g.cols)),
            None,
        )
        if target is None:
            free = next((a for a in g.arrows if a.alive and a.anim != "bump"), None)
            if free:
                ag.click_arrow(g, free.row, free.col)
            for _ in range(20):
                ag.update_animations(g, 0.05)
            continue
        ag.click_arrow(g, target.row, target.col)
        mistakes += 1
        for _ in range(20):
            ag.update_animations(g, 0.05)
        assert g.state == ag.State.PLAYING and not g.pending_fail
        assert g.misses_left == ag.MISSES_PER_LEVEL - mistakes
    target = next(
        (a for a in g.arrows if a.alive and a.anim != "bump" and ag.is_blocked(g.arrows, a, g.rows, g.cols)),
        None,
    )
    assert target is not None
    ag.click_arrow(g, target.row, target.col)
    assert g.pending_fail and g.state == ag.State.PLAYING and target.anim == "bump"
    for _ in range(30):
        ag.update_animations(g, 0.05)
        if g.state == ag.State.FAIL:
            break
    assert g.state == ag.State.FAIL
    assert [b.action for b in g.buttons] == ["restart", "menu"]
    print("  3 次归零不失败；第 4 次失误 → FAIL")


def test_full_clear():
    print("=== 连续通关 ===")
    g = ag.Game()
    ag.handle_action(g, "start")
    for level in range(ag.TOTAL_LEVELS):
        assert g.arrow_count == ag.arrow_count_for_level(level), (
            f"L{level+1} arrow_count={g.arrow_count} target={ag.arrow_count_for_level(level)}"
        )
        order = ag.solve_level(g.level_grid)
        for r, c, d in order:
            ag.click_arrow(g, r, c)
        for _ in range(40):
            ag.update_animations(g, 0.05)
            if g.state == ag.State.WIN:
                break
        assert g.state == ag.State.WIN
        assert [(b.action, b.label) for b in g.buttons][0][1] == (
            "下一关" if level + 1 < ag.TOTAL_LEVELS else "查看结果"
        )
        ag.handle_action(g, "next")
        ag.rebuild_buttons(g)
    assert g.state == ag.State.ALL_CLEAR
    print("  4 关随机图通关 → ALL_CLEAR")


def test_stellar_draw():
    print("=== Stellar 浅色绘制 ===")
    pygame.init()
    screen = pygame.display.set_mode((ag.WINDOW_W, ag.WINDOW_H))
    g = ag.Game()
    ag.rebuild_buttons(g)
    # 背景应为浅色
    assert ag.C_BG[0] > 200 and ag.C_CARD == (255, 255, 255)
    ag.draw_menu(screen, g)
    # 抽样菜单背景像素
    px = pygame.PixelArray(screen)
    center_bg = tuple(screen.get_at((20, 200)))[:3]
    assert center_bg[0] > 200, f"菜单背景应为浅色，got {center_bg}"
    del px

    ag.handle_action(g, "start")
    world = pygame.Surface((ag.WINDOW_W, ag.WINDOW_H))
    world.fill(ag.C_BG)
    ag.draw_dot_grid(world)
    ag.draw_hud(world, g)
    ag.draw_board(world, g)
    ag.draw_bottom_bar(world, g)
    hud_px = tuple(world.get_at((WINDOW := ag.WINDOW_W // 2, 10)))[:3]
    assert hud_px[0] > 240, f"HUD 应为白卡片，got {hud_px}"
    print("  浅色令牌与界面绘制正常:", g.level_name)

    # 失败/通关按钮
    order = ag.solve_level(g.level_grid)
    for r, c, d in order:
        ag.click_arrow(g, r, c)
    for _ in range(40):
        ag.update_animations(g, 0.05)
        if g.state == ag.State.WIN:
            break
    assert [b.action for b in g.buttons] == ["next", "restart", "menu"]
    ag.draw_result(screen, g, "win")
    print("  WIN 按钮与结果层绘制 OK")


def main():
    test_random_solvable()
    test_miss_rule()
    test_full_clear()
    test_stellar_draw()
    print("\nALL_TESTS_PASSED")


if __name__ == "__main__":
    main()
