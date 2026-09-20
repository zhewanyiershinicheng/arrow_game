# -*- coding: utf-8 -*-
"""按钮文案/动作断言（适配随机地图 API）。"""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["ARROW_GAME_HEADLESS"] = "1"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame
import arrow_game as ag

pygame.init()
pygame.display.set_mode((ag.WINDOW_W, ag.WINDOW_H))


def clear_level(game: ag.Game) -> None:
    order = ag.solve_level(game.level_grid)
    assert order, "当前随机关应有解"
    for r, c, d in order:
        ag.click_arrow(game, r, c)
    for _ in range(40):
        ag.update_animations(game, 0.05)
        if game.state == ag.State.WIN:
            break


def force_fail(game: ag.Game) -> None:
    """把可失误次数打光后，再错一次触发失败。"""
    while game.state == ag.State.PLAYING and not game.pending_fail:
        blocked = next(
            (
                a
                for a in game.arrows
                if a.alive and a.anim != "bump" and ag.is_blocked(game.arrows, a, game.rows, game.cols)
            ),
            None,
        )
        if blocked:
            ag.click_arrow(game, blocked.row, blocked.col)
        else:
            free = next((a for a in game.arrows if a.alive and a.anim != "bump"), None)
            if free:
                ag.click_arrow(game, free.row, free.col)
            else:
                ag.update_animations(game, 0.1)
        for _ in range(12):
            ag.update_animations(game, 0.05)
    for _ in range(40):
        ag.update_animations(game, 0.05)
        if game.state == ag.State.FAIL:
            break


def main() -> None:
    # MENU
    g = ag.Game()
    ag.rebuild_buttons(g)
    assert [(b.action, b.label) for b in g.buttons] == [("start", "开始游戏")]

    # PLAYING
    ag.handle_action(g, "start")
    ag.rebuild_buttons(g)
    assert [(b.action, b.label) for b in g.buttons] == [
        ("restart", "重新开始"),
        ("menu", "返回菜单"),
    ]

    # FAIL（随机关）
    force_fail(g)
    assert g.state == ag.State.FAIL, g.state
    print("FAIL", [(b.action, b.label) for b in g.buttons])
    assert [(b.action, b.label) for b in g.buttons] == [
        ("restart", "重新开始"),
        ("menu", "返回菜单"),
    ]

    # WIN 连锁 → ALL_CLEAR
    g2 = ag.Game()
    ag.handle_action(g2, "start")
    for i in range(ag.TOTAL_LEVELS):
        clear_level(g2)
        assert g2.state == ag.State.WIN
        expected_next = "下一关" if i + 1 < ag.TOTAL_LEVELS else "查看结果"
        print(f"L{i+1} WIN", [(b.action, b.label) for b in g2.buttons])
        assert [(b.action, b.label) for b in g2.buttons] == [
            ("next", expected_next),
            ("restart", "重玩本关"),
            ("menu", "返回菜单"),
        ]
        ag.handle_action(g2, "next")
        ag.rebuild_buttons(g2)
    assert g2.state == ag.State.ALL_CLEAR
    print("ALL_CLEAR", [(b.action, b.label) for b in g2.buttons])
    assert [(b.action, b.label) for b in g2.buttons] == [
        ("start", "再玩一遍"),
        ("menu", "返回菜单"),
    ]
    print("OK")


if __name__ == "__main__":
    main()
