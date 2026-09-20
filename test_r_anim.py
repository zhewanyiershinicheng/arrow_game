# -*- coding: utf-8 -*-
"""R 键、转场与按钮动效测试。"""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["ARROW_GAME_HEADLESS"] = "1"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame
import arrow_game as ag

pygame.init()
pygame.display.set_mode((ag.WINDOW_W, ag.WINDOW_H))


class FakeKeys:
    def __init__(self, pressed=None):
        self.pressed = set(pressed or [])

    def __getitem__(self, key):
        return key in self.pressed


def pump(game, seconds=0.5):
    steps = max(1, int(seconds / 0.05))
    for _ in range(steps):
        ag.update_animations(game, 0.05)


def test_r_key_states():
    g = ag.Game()
    ag.rebuild_buttons(g)

    ag.handle_r_key(g)
    assert g.trans_dir == 1
    pump(g, 0.6)
    assert g.state == ag.State.PLAYING
    print("MENU R → PLAYING", g.level_name)

    ag.handle_r_key(g)
    pump(g, 0.6)
    assert g.state == ag.State.PLAYING
    assert g.misses_left == ag.MISSES_PER_LEVEL
    print("PLAYING R → restart, misses", g.misses_left)

    g2 = ag.Game()
    ag.rebuild_buttons(g2)
    keys_down = FakeKeys({pygame.K_r})
    ag.poll_hotkeys(g2, keys_down)
    assert g2.trans_dir == 1 and g2.key_r_down
    pump(g2, 0.6)
    assert g2.state == ag.State.PLAYING
    grid_before = tuple(g2.level_grid)
    ag.poll_hotkeys(g2, keys_down)
    assert tuple(g2.level_grid) == grid_before
    ag.poll_hotkeys(g2, FakeKeys())
    assert g2.key_r_down is False
    ag.poll_hotkeys(g2, FakeKeys({pygame.K_r}))
    pump(g2, 0.6)
    print("poll edge-trigger OK")

    order = ag.solve_level(g.level_grid)
    for r, c, d in order:
        ag.click_arrow(g, r, c)
    pump(g, 1.2)
    assert g.state == ag.State.WIN
    ag.handle_r_key(g)
    pump(g, 0.6)
    assert g.state == ag.State.PLAYING and g.level_index == 0
    print("WIN R → restart OK")

    g3 = ag.Game()
    ag.load_level(g3, 2)
    for _ in range(40):
        if g3.state != ag.State.PLAYING or g3.pending_fail:
            break
        t = next(
            (
                a
                for a in g3.arrows
                if a.alive and a.anim != "bump" and ag.is_blocked(g3.arrows, a, g3.rows, g3.cols)
            ),
            None,
        )
        if not t:
            ag.update_animations(g3, 0.1)
            continue
        ag.click_arrow(g3, t.row, t.col)
        ag.update_animations(g3, 0.2)
    pump(g3, 0.6)
    if g3.state == ag.State.FAIL:
        ag.handle_r_key(g3)
        pump(g3, 0.6)
        assert g3.state == ag.State.PLAYING
        print("FAIL R → restart OK")
    else:
        print("FAIL path not hit, skip")


def test_transition_and_buttons():
    g = ag.Game()
    ag.rebuild_buttons(g)
    ag.request_action(g, "start")
    assert g.trans_dir == 1 and g.trans_pending == "start"
    assert g.state == ag.State.MENU
    pump(g, ag.TRANS_OUT + 0.08)
    assert g.state == ag.State.PLAYING
    pump(g, ag.TRANS_IN + 0.12)
    assert g.trans_dir == 0
    print("transition menu→play OK", [(b.action, b.label) for b in g.buttons])

    btn = g.buttons[0]
    btn.hover = True
    btn.press = 1.0
    ag.update_button_anim(g, 0.08)
    assert btn.hover_t > 0.05
    assert btn.press < 1.0
    print("button hover_t", round(btn.hover_t, 2), "press", round(btn.press, 2))

    ag.request_action(g, "menu")
    ag.request_action(g, "restart")
    assert g.trans_pending == "menu"
    pump(g, 0.6)
    assert g.state == ag.State.MENU
    print("transition lock + menu OK")

    # 绘制冒烟
    screen = pygame.display.get_surface() or pygame.display.set_mode((ag.WINDOW_W, ag.WINDOW_H))
    g.screen_t = 0.3
    ag.draw_menu(screen, g)
    ag.draw_transition_overlay(screen, g)
    print("draw menu/overlay OK")


def test_animations():
    g = ag.Game()
    ag.load_level(g, 0)
    for _ in range(20):
        ag.update_animations(g, 0.05)
    assert g.level_enter > 0.3
    free = next(a for a in g.arrows if a.alive and not ag.is_blocked(g.arrows, a, g.rows, g.cols))
    ag.click_arrow(g, free.row, free.col)
    assert free.anim == "flying"
    assert len(g.particles) > 0
    blocked = next((a for a in g.arrows if a.alive and ag.is_blocked(g.arrows, a, g.rows, g.cols)), None)
    if blocked:
        ag.click_arrow(g, blocked.row, blocked.col)
        assert blocked.anim == "bump" and g.hit_flash > 0
    print("gameplay anims OK")


def main():
    test_r_key_states()
    test_transition_and_buttons()
    test_animations()
    print("\nALL_OK")


if __name__ == "__main__":
    main()
