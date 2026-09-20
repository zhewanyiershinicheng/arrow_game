# -*- coding: utf-8 -*-
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["ARROW_GAME_HEADLESS"] = "1"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame
import arrow_game as ag

pygame.init()
pygame.display.set_mode((ag.WINDOW_W, ag.WINDOW_H))

# FAIL buttons
g = ag.Game()
ag.load_level(g, 2)
ag.rebuild_buttons(g)
for _ in range(20):
    if g.state != ag.State.PLAYING or g.pending_fail:
        break
    t = next(
        (
            a
            for a in g.arrows
            if a.alive and a.anim != "bump" and ag.is_blocked(g.arrows, a, g.rows, g.cols)
        ),
        None,
    )
    if not t:
        ag.update_animations(g, 0.1)
        continue
    ag.click_arrow(g, t.row, t.col)
for _ in range(40):
    ag.update_animations(g, 0.05)
    if g.state == ag.State.FAIL:
        break
print("FAIL state", g.state, "buttons", [(b.action, b.label) for b in g.buttons])
assert g.state == ag.State.FAIL
assert [(b.action, b.label) for b in g.buttons] == [
    ("restart", "重新开始"),
    ("menu", "返回菜单"),
]

# WIN / ALL_CLEAR
g2 = ag.Game()
ag.handle_action(g2, "start")
for i in range(len(ag.LEVELS)):
    order = ag.solve_level(ag.LEVELS[i]["grid"])
    for r, c, d in order:
        ag.click_arrow(g2, r, c)
    for _ in range(40):
        ag.update_animations(g2, 0.05)
        if g2.state == ag.State.WIN:
            break
    print(f"L{i+1} WIN buttons", [(b.action, b.label) for b in g2.buttons])
    if i < len(ag.LEVELS) - 1:
        assert [b.action for b in g2.buttons] == ["next", "restart", "menu"]
        ag.handle_action(g2, "next")
    else:
        assert g2.buttons[0].label == "查看结果"
        ag.handle_action(g2, "next")
assert g2.state == ag.State.ALL_CLEAR
print("ALL_CLEAR buttons", [(b.action, b.label) for b in g2.buttons])
print("OK")
