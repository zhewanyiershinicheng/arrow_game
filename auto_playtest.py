# -*- coding: utf-8 -*-
"""验证随机地图可解性、箭头数量难度、以及可失误次数规则。"""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["ARROW_GAME_HEADLESS"] = "1"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame
import arrow_game as ag


def test_random_solvable():
    print("=== 随机地图可解性（每关 30 次） ===")
    for level in range(ag.TOTAL_LEVELS):
        target = ag.arrow_count_for_level(level)
        ok = 0
        counts = set()
        grids = set()
        for _ in range(30):
            grid, n = ag.generate_solvable_grid(level)
            order = ag.solve_level(grid)
            total = sum(ch in ag.CHAR_DIR for row in grid for ch in row)
            assert order is not None, f"L{level+1} 生成了无解图\n" + "\n".join(grid)
            assert len(order) == total, f"L{level+1} 步数不匹配 {len(order)} vs {total}"
            # 难度：箭头数应接近目标
            assert n == total
            ok += 1
            counts.add(n)
            grids.add(tuple(grid))
        print(f"L{level+1}: 目标箭头 {target}, 实际出现 {sorted(counts)}, 不同地图 {len(grids)}/30, 全部有解")
        assert ok == 30
        # 至少有一定随机性
        assert len(grids) >= 5, f"L{level+1} 地图几乎不变"


def test_miss_rule():
    print("=== 可失误次数规则 ===")
    g = ag.Game()
    ag.load_level(g, 2)
    ag.rebuild_buttons(g)
    assert g.misses_left == ag.MISSES_PER_LEVEL

    # 连续点阻挡：归零过程不失败
    mistakes = 0
    while mistakes < ag.MISSES_PER_LEVEL:
        target = next(
            (a for a in g.arrows if a.alive and a.anim != "bump" and ag.is_blocked(g.arrows, a, g.rows, g.cols)),
            None,
        )
        if target is None:
            # 清掉一个自由箭头，等待 bump 结束后再找阻挡
            free = next((a for a in g.arrows if a.alive and a.anim != "bump" and not ag.is_blocked(g.arrows, a, g.rows, g.cols)), None)
            if free:
                ag.click_arrow(g, free.row, free.col)
            for _ in range(20):
                ag.update_animations(g, 0.05)
            continue
        ag.click_arrow(g, target.row, target.col)
        mistakes += 1
        for _ in range(20):
            ag.update_animations(g, 0.05)
        print(f"  第 {mistakes} 次失误后: misses={g.misses_left}, state={g.state}, pending_fail={g.pending_fail}")
        assert g.state == ag.State.PLAYING, f"第 {mistakes} 次失误不应直接失败"
        assert not g.pending_fail
        assert g.misses_left == ag.MISSES_PER_LEVEL - mistakes

    assert g.misses_left == 0
    # 次数已是 0，再错才失败
    target = next(
        (a for a in g.arrows if a.alive and a.anim != "bump" and ag.is_blocked(g.arrows, a, g.rows, g.cols)),
        None,
    )
    if target is None:
        # 再消一个自由箭头制造/等待阻挡；若全自由则构造失败场景：任意点一个仍阻挡的
        for _ in range(30):
            for a in g.arrows:
                if a.alive and a.anim != "bump" and ag.is_blocked(g.arrows, a, g.rows, g.cols):
                    target = a
                    break
            if target:
                break
            free = next((a for a in g.arrows if a.alive and a.anim != "bump"), None)
            if free:
                # 只有点阻挡才会失败；若当前无阻挡，推进后可能仍无
                ag.update_animations(g, 0.05)
            else:
                break
    assert target is not None, "应仍存在阻挡箭头以测失败"
    ag.click_arrow(g, target.row, target.col)
    assert g.pending_fail is True
    assert g.state == ag.State.PLAYING
    assert target.anim == "bump"
    for _ in range(30):
        ag.update_animations(g, 0.05)
        if g.state == ag.State.FAIL:
            break
    assert g.state == ag.State.FAIL
    print("  次数为 0 后再失误 → FAIL（先动效后结算）")
    print("  FAIL buttons", [(b.action, b.label) for b in g.buttons])
    assert [(b.action, b.label) for b in g.buttons] == [("restart", "重新开始"), ("menu", "返回菜单")]


def test_random_restart_and_counts():
    print("=== 随机重开与箭头数量 ===")
    g = ag.Game()
    ag.handle_action(g, "start")
    seen = []
    for i in range(6):
        seen.append(tuple(g.level_grid))
        ag.handle_action(g, "restart")
    assert len(set(seen)) >= 3, "重开应生成不同地图"
    print(f"  连续重开 6 次，得到 {len(set(seen))} 种不同地图")

    counts = []
    for level in range(ag.TOTAL_LEVELS):
        ag.load_level(g, level)
        counts.append((g.arrow_count, len(g.alive_arrows()), ag.arrow_count_for_level(level)))
        assert g.arrow_count == len(g.alive_arrows())
        order = ag.solve_level(g.level_grid)
        assert order and len(order) == g.arrow_count
    print("  各关箭头数 (实际, 存活, 目标):", counts)
    assert counts[0][0] < counts[-1][0], "难度应随关卡箭头数上升"
    for actual, _, target in counts:
        assert actual >= 4


def test_full_clear_random():
    print("=== 随机图连续通关 ===")
    g = ag.Game()
    ag.handle_action(g, "start")
    for level in range(ag.TOTAL_LEVELS):
        order = ag.solve_level(g.level_grid)
        assert order
        for r, c, d in order:
            ag.click_arrow(g, r, c)
        for _ in range(40):
            ag.update_animations(g, 0.05)
            if g.state == ag.State.WIN:
                break
        assert g.state == ag.State.WIN, f"L{level+1} {g.state}"
        assert g.misses_left == ag.MISSES_PER_LEVEL
        ag.handle_action(g, "next")
        ag.rebuild_buttons(g)
    assert g.state == ag.State.ALL_CLEAR
    print("  4 关随机图全部通关 → ALL_CLEAR")


def test_draw_smoke():
    print("=== 界面绘制 ===")
    pygame.init()
    screen = pygame.display.set_mode((ag.WINDOW_W, ag.WINDOW_H))
    g = ag.Game()
    ag.rebuild_buttons(g)
    ag.draw_menu(screen, g)
    ag.handle_action(g, "start")
    ag.draw_hud(screen, g)
    ag.draw_banner(screen, g)
    ag.draw_board(screen, g)
    ag.draw_bottom_bar(screen, g)
    assert g.level_name.startswith("第")
    assert "随机" in g.level_desc
    print("  菜单/游戏 HUD 绘制正常:", g.level_name, "|", g.level_desc)


def main():
    test_random_solvable()
    test_miss_rule()
    test_random_restart_and_counts()
    test_full_clear_random()
    test_draw_smoke()
    print("\nALL_TESTS_PASSED")


if __name__ == "__main__":
    main()
