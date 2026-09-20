# -*- coding: utf-8 -*-
"""导出 Stellar 浅色界面截图。"""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["ARROW_GAME_HEADLESS"] = "1"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame
import arrow_game as ag

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shots")
os.makedirs(OUT, exist_ok=True)


def save(screen, name):
    path = os.path.join(OUT, name)
    pygame.image.save(screen, path)
    print("saved", path)


def blit_game(screen, game):
    world = pygame.Surface((ag.WINDOW_W, ag.WINDOW_H))
    world.fill(ag.C_BG)
    ag.draw_dot_grid(world)
    ag.draw_hud(world, game)
    ag.draw_banner(world, game)
    ag.draw_board(world, game)
    ag.draw_bottom_bar(world, game)
    screen.fill(ag.C_BG)
    screen.blit(world, (0, 0))


def main():
    pygame.init()
    screen = pygame.display.set_mode((ag.WINDOW_W, ag.WINDOW_H))
    game = ag.Game()
    ag.rebuild_buttons(game)

    screen.fill(ag.C_BG)
    ag.draw_menu(screen, game)
    save(screen, "1_menu.png")

    ag.handle_action(game, "start")
    ag.rebuild_buttons(game)
    blit_game(screen, game)
    save(screen, "2_playing.png")

    blocked = next(
        (a for a in game.arrows if ag.is_blocked(game.arrows, a, game.rows, game.cols)),
        None,
    )
    if blocked:
        ag.click_arrow(game, blocked.row, blocked.col)
        for _ in range(5):
            ag.update_animations(game, 0.04)
        blit_game(screen, game)
        save(screen, "3_bump.png")
        print("bump misses", game.misses_left)

    # FAIL on higher level for denser board
    ag.load_level(game, 2)
    ag.rebuild_buttons(game)
    for _ in range(30):
        if game.state != ag.State.PLAYING or game.pending_fail:
            break
        t = next(
            (
                a
                for a in game.arrows
                if a.alive and a.anim != "bump" and ag.is_blocked(game.arrows, a, game.rows, game.cols)
            ),
            None,
        )
        if t is None:
            ag.update_animations(game, 0.12)
            continue
        ag.click_arrow(game, t.row, t.col)
    for _ in range(40):
        ag.update_animations(game, 0.05)
        if game.state == ag.State.FAIL:
            break
    assert game.state == ag.State.FAIL
    assert [(b.action, b.label) for b in game.buttons] == [
        ("restart", "重新开始"),
        ("menu", "返回菜单"),
    ]
    blit_game(screen, game)
    ag.draw_result(screen, game, "fail")
    save(screen, "4_fail.png")

    ag.handle_action(game, "start")
    order = ag.solve_level(game.level_grid)
    for r, c, d in order:
        ag.click_arrow(game, r, c)
    for _ in range(40):
        ag.update_animations(game, 0.05)
        if game.state == ag.State.WIN:
            break
    assert game.state == ag.State.WIN
    blit_game(screen, game)
    ag.draw_result(screen, game, "win")
    save(screen, "5_win.png")

    pygame.quit()
    print("done")


if __name__ == "__main__":
    main()
