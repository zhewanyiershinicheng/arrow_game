---
feature: ui-stellar-light
status: designed
updated: 2026-09-18
branch: none-session-dir
commits: n/a
---

# Stellar Light UI Redesign

## Report

## [S1] Problem
游戏界面为深色霓虹风格，视觉信息密度与层次不足，不符合作业展示所需的「界面美观、布局合理、文字清楚」。用户要求在 **Hexo Stellar 浅色主题** 语言下全面重做视觉，游戏规则与随机关卡逻辑保持不变。

## [S2] Design

### Visual language (Stellar light)
- **Page**: light slate canvas `#F4F6F8`, soft procedural dot-grid (not neon)
- **Card**: white `#FFFFFF`, border `#E5EAF0`, radius 12, soft shadow `rgba(15,23,42,0.06)`
- **Ink**: primary `#1F2937`, muted `#6B7280`
- **Accent**: Stellar blue `#3B82F6`, soft fill `#EBF2FF`
- **Semantic**: success `#22C55E`, warn `#F59E0B`, danger `#EF4444`
- **Type**: Microsoft YaHei / system CJK; display bold for titles, regular for body; HUD uses pill badges
- **Buttons**: primary solid blue + white secondary outline; pill radius 10
- **Board cells**: `#F8FAFC` fill, `#E5EAF0` grid; hover `#EEF4FF`
- **Arrows**: deepen colors for contrast on light cells — 上 `#F59E0B`, 下 `#0EA5E9`, 左 `#8B5CF6`, 右 `#EA580C`
- **Signature**: white elevated cards + blue metadata pills (Stellar documentation-card language)
- **Assets**: procedural only (dot grid, soft gradient title band, card shadows, decorative arrow chips) — external image CDNs unreachable

### Screens (all redrawn)
1. **Menu** — light canvas, title + white rules card + primary CTA
2. **Playing** — white HUD bar with pill stats; white board panel; light cells; footer controls
3. **Bump / fly** — same light palette; red bump flash on light cards; success fly tint
4. **Win / Fail / All-clear** — white modal cards, soft shadow, blue/red CTAs
5. **No answer leaks** — no free-arrow green rings, no hint/verify buttons

### Unchanged contracts
- Random solvable map generation (reverse construction + solver)
- Miss rule: `3→0` allowed; mistake at `0` → fail after bump animation
- Arrow counts by level: 5 / 7 / 9 / 11
- Input: click, R restart, Esc menu

## [S3] Out of Scope
- 不改玩法规则、关卡生成算法、胜负判定
- 不做深色/浅色运行时切换（仅浅色）
- 不引入外部网络图片依赖
- 不迁移到 Web/HTML 交付物

## Tasks
- [ ] T1: 设计令牌与全局绘制常量切换为 Stellar light — acceptance: 背景/卡片/文字/强调色均为浅色体系，无旧深色霓虹残留 (covers: S2)
- [ ] T2: 重绘菜单/HUD/棋盘/底栏/结果弹层 — acceptance: 五类界面截图无文字重叠、对比度可读、按钮状态齐全 (covers: S2; depends: T1)
- [ ] T3: 程序化装饰素材（点阵底纹/阴影/胶囊徽章） — acceptance: assets 或内联绘制生效，截图可见 Stellar 卡片质感 (covers: S2; depends: T1)
- [ ] T4: 回归随机地图与失误规则测试 — acceptance: auto_playtest 全部 PASS (covers: S2)
- [ ] T5: 截图 QA + 更新设计说明 — acceptance: shots/*.png 呈现浅色 Stellar，逻辑测试通过 (covers: S2; depends: T2,T3,T4)
