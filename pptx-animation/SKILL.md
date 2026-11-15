---
name: pptx-animation
description: 给 python-pptx 生成的 .pptx 加"点击触发"的进入动画。python-pptx 没有动画 API，动画只能手写 p:timing XML 注入，写错会让文件报"已损坏"。本 skill 用"从本机真实 PowerPoint 文件提取基准 + 逐节点比对"的方式保证手写 XML 正确。当用户说"给 ppt 加动画""太枯燥了""让它动起来"，或要做带演示动画的幻灯片时使用。
argument-hint: "<pptx 文件或生成脚本>"
---

# 给 PPTX 加动画

## 核心原则

**python-pptx 根本没有动画 API。** 动画存在每页 slide XML 的 `<p:timing>` 节点里，
唯一的办法是手写这段 XML 注入进去。

**因此绝不能凭记忆写这段 XML。** 它层次深、节点顺序有强约束，写错一个元素的
位置，PowerPoint / WPS 打开时就直接报"文件已损坏，需要修复"——用户拿到的是
一个打不开的文件，比没有动画糟糕得多。

破局办法是：**在本机找一个真实带 PowerPoint 动画的 .pptx，把里面 PowerPoint
自己生成的 `<p:timing>` 当作结构基准**，照着它的形状写，写完再逐节点比对。
`anim_check.py` 就是干这个的。

这段"找基准 → 照着写 → 比对验证"的流程是本 skill 的全部价值所在。
`pptx_anim.py` 里的模板已经这样验证过，可以直接用；但只要你改动了 XML
结构，就必须重新验证。

## 执行步骤

1. **确认环境**：`python3 -c "import pptx, lxml"`。缺了就先装。

2. **找基准**：

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/anim_check.py" find
   ```

   会在桌面、下载、微信/WPS 的文件目录里找带 PowerPoint 动画的 pptx。
   **一个都找不到时**：让用户随便打开一个 pptx，加个动画另存一份，再重跑。

3. **查效果预设**：

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/anim_check.py" bank
   ```

   打印出真实存在的 `presetID / presetSubtype / filter` 组合。
   想用 `fade`、`rise` 之外的效果，从这里查准确的三元组填进
   `pptx_anim.py` 的 `EFFECTS`。**三个值必须搭配正确**，否则动画能放但
   "效果选项"里显示的是别的效果。
   输出里若出现**本工具自己生成的文件**，用 `--exclude` 排掉——
   否则比对成了自己跟自己比，验证等于没做。

4. **写动画**：在用户的生成脚本里 import 本 skill 的模块：

   ```python
   import sys
   sys.path.insert(0, "${CLAUDE_SKILL_DIR}")
   from pptx_anim import Anim, mark, since

   s = blank()
   head(s, ...)                 # 标题不参与动画

   m = mark(s)
   lead = tbox(s, ...); para(lead, ...)
   g_lead = since(s, m)         # 这一批新加的形状

   m = mark(s)
   for ...: card(s, ...); ...
   g_cards = since(s, m)

   Anim(s).add(g_lead, "fade").add(g_cards, "rise").apply()
   ```

   `mark()` / `since()` 靠 `len(slide.shapes)` 计数，**不需要改动用户原有的
   tbox / rect / pic 等辅助函数**——这是选这个 API 的原因。
   每个 `add()` = 放映时的一次点击。

5. **验证**（必做）：

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/anim_check.py" check <文件> --against
   ```

   要看到 `✓ N 个效果与真实 PowerPoint 基准逐节点同构` 且 `问题页数：0`。
   出现 `✗` 就去修，别交付。

6. **留一份无动画备份**（见下文"必须向用户说明"）。

## 怎么设计分组（这一步决定好不好用，不是技术问题）

**默认不动的**：标题、页码、页眉分隔线——它们跟着页面直接出现。

**正文按内容逻辑分块，不按元素分块。** 一张卡片是"卡片底 + 编号 + 标题 + 正文"
四五个形状，必须放进**同一个 add()**，否则会出现"先出文字后出卡片底"的穿帮。

**点击次数要克制。** 一页 3–5 次是舒服的区间。同一逻辑层级的并列项
（三条要点、四张卡片）**合成一次出现**，不要逐条点——逐条点会让演示变得拖沓，
反而比不带动画更烦。真正值得逐条点的只有两种：

- **流程/时间线**：按步骤推进符合讲述节奏
- **结论页**：每条停一下让听众消化

一页超过 8 次点击就该拆开或者合并了。

**效果选择**：`fade`（淡入）给正文，`rise`（轻微上浮）给强调性元素
（数据卡、"转折句"、结论条目）。**整份稿子只用一两种效果**，
花哨的效果混搭会让严肃内容显得轻浮。

## 必须向用户说明的三点

1. **动画没被实际播放验证过。** `anim_check.py` 证明的是 XML 结构合法且与
   真实 PowerPoint 输出同构，**不等于亲眼看过它动**。本机没有 PowerPoint /
   LibreOffice 时无法真机播放，要如实告诉用户，让他在 WPS 里点一遍。

2. **Keynote 对 PPTX 动画支持很差**，基本会丢掉。WPS 和 PowerPoint 正常。
   用户如果在 Mac 上用 Keynote，动画这个需求本身就得先确认。

3. **留无动画备份，并提醒用户关掉重开。** 剥离所有 `p:timing` 生成一份
   `xxx_无动画备份.pptx` 放同一目录。另外文件若正在 WPS 里开着，
   会存在 `.~xxx.pptx` 锁文件，**必须关闭后重新打开**才能看到新版本。

## 常见问题

- **`find` 一个文件都找不到** —— 让用户手动造一个带动画的 pptx 放到桌面。
- **`check` 报"悬空 spid"** —— 动画引用了不存在的形状 id。通常是先建了动画
  又删了形状，或者 `mark()`/`since()` 的范围切错了。
- **`check` 报"结构与基准不同"** —— 真 bug，照报告里的 `@N` 位置和两侧节点名
  对比修。注意"位移量/延迟值不同"不算——`sig()` 已经把它们归一化了，
  报出来的都是结构差异。
- **`? 在基准库里没有，无法比对`** —— 用了基准库里没有的效果组合。
  跑 `bank` 看有哪些可用的，或者接受"未比对"这个状态并如实告知用户。
- **想加退出动画/强调动画** —— `pptx_anim.py` 目前只做进入（`presetClass="entr"`）。
  扩展时照 `EFFECTS` 的结构加参数即可，但**务必**先用 `bank` 查准三元组，
  再用 `check --against` 验证。
