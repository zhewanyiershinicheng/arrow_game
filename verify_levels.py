# -*- coding: utf-8 -*-
"""随机地图生成验证。"""
import os
import sys

os.environ["ARROW_GAME_HEADLESS"] = "1"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from arrow_game import (
    TOTAL_LEVELS,
    arrow_count_for_level,
    generate_solvable_grid,
    level_title,
    solve_level,
    CHAR_DIR,
    DIR_NAME,
)

def main():
    print("=== 随机地图抽样 ===")
    all_ok = True
    for level in range(TOTAL_LEVELS):
        grid, n = generate_solvable_grid(level)
        order = solve_level(grid)
        ok = order is not None and len(order) == n
        all_ok = all_ok and ok
        print(f"{level_title(level)} 箭头={n} 目标={arrow_count_for_level(level)} 可解={ok}")
        for row in grid:
            print(f"  {row}")
        if order:
            print("  顺序:", " → ".join(f"({r},{c}){DIR_NAME[d]}" for r, c, d in order[:8]),
                  ("..." if len(order) > 8 else ""))
    print("ALL_OK =", all_ok)
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
