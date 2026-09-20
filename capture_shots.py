# -*- coding: utf-8 -*-
"""导出界面截图，用于排版检查。"""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
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
    world.fill(ag.COLOR_BG)
    ag.draw_hud(world, game)
    ag.draw_banner(world, game)
    ag.draw_board(world, game)
    ag.draw_bottom_bar(world, game)
    screen.fill(ag.COLOR_BG)
    screen.blit(world, (0, 0))
    return world


def main():
    pygame.init()
    screen = pygame.display.set_mode((ag.WINDOW_W, ag.WINDOW_H))
    game = ag.Game()
    ag.rebuild_buttons(game)

    screen.fill(ag.COLOR_BG)
    ag.draw_menu(screen, game)
    save(screen, "1_menu.png")

    ag.handle_action(game, "start")
    ag.rebuild_buttons(game)
    blit_game(screen, game)
    save(screen, "2_playing.png")

    # 找阻挡箭头并点击，截碰撞反馈
    blocked = next(a for a in game.arrows if ag.is_blocked(game.arrows, a, game.rows, game.cols))
    ag.click_arrow(game, blocked.row, blocked.col)
    assert game.misses_left == ag.MISSES_PER_LEVEL - 1
    for _ in range(5):
        ag.update_animations(game, 0.04)
    blit_game(screen, game)
    save(screen, "3_bump.png")
    print("after bump: state=", game.state, "misses=", game.misses_left, "pending_fail=", game.pending_fail)

    # 失败：持续点击阻挡箭头直至耗尽，并等待动画结算
    while game.state == ag.State.PLAYING and not game.pending_fail:
        blocked = None
        free = None
        for a in game.arrows:
            if not a.alive or a.anim == "bump":
                continue
            if ag.is_blocked(game.arrows, a, game.rows, game.cols):
                blocked = blocked or a
            else:
                free = free or a
        if blocked:
            ag.click_arrow(game, blocked.row, blocked.col)
        elif free:
            # 为了让失败更容易复现：只点阻挡；若暂无阻挡则推进动画
            ag.update_animations(game, 0.15)
        else:
            ag.update_animations(game, 0.15)
        if game.misses_left <= 0:
            game.pending_fail = True  # 确保进入结算

    for _ in range(40):
        ag.update_animations(game, 0.05)
        if game.state == ag.State.FAIL:
            break
    assert game.state == ag.State.FAIL, game.state
    assert [b.action for b in game.buttons] == ["restart", "menu"], [b.action for b in game.buttons]
    blit_game(screen, game)
    ag.draw_result(screen, game, "fail")
    save(screen, "4_fail.png")

    # 通关
    ag.handle_action(game, "start")
    ag.rebuild_buttons(game)
    order = ag.solve_level(ag.LEVELS[0]["grid"])
    for r, c, d in order:
        ag.click_arrow(game, r, c)
    for _ in range(40):
        ag.update_animations(game, 0.05)
        if game.state == ag.State.WIN:
            break
    assert game.state == ag.State.WIN, game.state
    assert [b.action for b in game.buttons] == ["next", "restart", "menu"]
    blit_game(screen, game)
    ag.draw_result(screen, game, "win")
    save(screen, "5_win.png")

    pygame.quit()
    print("done")


if __name__ == "__main__":
    main()
