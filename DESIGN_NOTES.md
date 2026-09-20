# DESIGN NOTES — 一箭又一箭 UI

## Direction chosen
- User pick: **Stellar light** + full visual redesign.
- Mode: game UI (not web); frontend-design convention-light: hierarchy, cards, readable stats.
- External Stellar/GitHub assets unreachable → procedural tokens only (dot grid, cards, pills).

## Token system (delivered)
- bg `#F4F6F8` · card `#FFFFFF` · border `#E5EAF0`
- ink `#1F2937` · muted `#6B7280`
- primary `#3B82F6` · soft `#EBF2FF` · deep `#2563EB`
- success `#22C55E` · warn `#F59E0B` · danger `#EF4444`
- Type: Microsoft YaHei system stack
- Signature: white elevated cards + blue pill badges + numbered rule list
- Risk taken: light documentation aesthetic for a casual game (readable, assignment-friendly)

## Polish pass
- Menu legend chips use mini arrow glyphs (not color dots)
- Primary button shadow drawn under fill
- R restart works on PLAYING / WIN / FAIL (and ALL_CLEAR → start)
- test_buttons.py rewritten for random-map API + label asserts

## Logic invariants (do not regress)
- Random solvable maps; misses 3→0 allowed; fail only on mistake at 0; counts 5/7/9/11.

## Acceptance
- [x] Stellar light tokens + cards/pills on menu/HUD/board/result
- [x] Random solvable maps verified 20×/level
- [x] Miss rule: 3→0 no fail; fail on mistake at 0
- [x] Button labels asserted (test_buttons.py)
- [x] No free-arrow rings / no hint-verify in UI
