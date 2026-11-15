#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
动画 XML 的基准发现与校验工具。

三个子命令：

  find    在本机找出真实带 PowerPoint 动画的 .pptx 文件
  bank    从这些文件里导出"效果预设库"（presetID/subtype/滤镜的真实组合）
  check   校验某个 .pptx 的动画 XML 是否合法、是否与真实 PowerPoint 输出同构

手写 p:timing 最大的风险是结构写错导致 PowerPoint/WPS 报"文件已损坏"。
所以不要凭记忆写 —— 先 find 找到基准，用 bank 查预设，写完用 check 验证。
"""

import os
import sys
import zipfile
import argparse

from lxml import etree

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS = {"p": P_NS, "a": A_NS}


def q(tag):
    pre, local = tag.split(":")
    return "{%s}%s" % (NS[pre], local)


# ---------------------------------------------------------------- find

SEARCH_ROOTS = [
    "~/Desktop", "~/Downloads", "~/Documents", "~/Movies",
    "~/Library/Containers/com.tencent.xinWeChat",
    "~/Library/Containers/com.kingsoft.wpsoffice.mac",
    "~/Library/Group Containers",
    "/Applications/WPS Office.app/Contents/Resources",
    "/Applications/Microsoft PowerPoint.app/Contents/Resources",
]

SKIP = ("node_modules", ".git", "site-packages", "Library/Caches")


def has_animation(path):
    """返回该文件里带 presetClass 的页数（0 表示没有动画）。"""
    try:
        z = zipfile.ZipFile(path)
    except Exception:
        return 0
    n = 0
    for name in z.namelist():
        if not (name.startswith("ppt/slides/slide") and name.endswith(".xml")):
            continue
        try:
            root = etree.fromstring(z.read(name))
        except Exception:
            continue
        if any(c.get("presetClass") for c in root.iter(q("p:cTn"))):
            n += 1
    return n


def cmd_find(args):
    found = []
    seen = set()
    for root in SEARCH_ROOTS:
        root = os.path.expanduser(root)
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            if any(s in dirpath for s in SKIP):
                dirnames[:] = []
                continue
            for fn in filenames:
                if not fn.lower().endswith((".pptx", ".pptm")):
                    continue
                p = os.path.join(dirpath, fn)
                if p in seen:
                    continue
                seen.add(p)
                n = has_animation(p)
                if n:
                    found.append((n, p))
        if len(found) >= 12 and not args.all:
            break
    if not found:
        print("没找到带 PowerPoint 动画的 pptx。")
        print("可以让用户随便打开一个 pptx 加个动画另存一份，再重跑本命令。")
        return 1
    found.sort(reverse=True)
    print("找到 %d 个带动画的文件（页数 = 含动画的幻灯片数）：\n" % len(found))
    for n, p in found:
        print("  %3d 页  %s" % (n, p))
    print("\n接下来跑：  anim_check.py bank")
    return 0


# ---------------------------------------------------------------- bank

def _ref_files(limit=12, exclude=()):
    """收集候选基准文件。

    exclude 用来排除"工具自己生成的"文件 —— 否则 check --against
    就变成自己跟自己比，验证等于没做。
    """
    exclude = {os.path.abspath(p) for p in exclude}
    out = []
    for root in SEARCH_ROOTS:
        root = os.path.expanduser(root)
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            if any(s in dirpath for s in SKIP):
                dirnames[:] = []
                continue
            for fn in filenames:
                if fn.lower().endswith((".pptx", ".pptm")):
                    p = os.path.join(dirpath, fn)
                    if os.path.abspath(p) in exclude:
                        continue
                    if has_animation(p):
                        out.append(p)
        if len(out) >= limit:
            break
    return out[:limit]


def collect_bank(files):
    """{(pid, sub, filter): 效果 cTn 元素}"""
    bank = {}
    for f in files:
        try:
            z = zipfile.ZipFile(f)
        except Exception:
            continue
        for name in z.namelist():
            if not (name.startswith("ppt/slides/slide") and name.endswith(".xml")):
                continue
            try:
                root = etree.fromstring(z.read(name))
            except Exception:
                continue
            for c in root.iter(q("p:cTn")):
                if not c.get("presetClass"):
                    continue
                fl = [a.get("filter") for a in c.iter(q("p:animEffect"))]
                key = (c.get("presetID"), c.get("presetSubtype"),
                       fl[0] if fl else None)
                bank.setdefault(key, c)
    return bank


def cmd_bank(args):
    files = _ref_files(exclude=args.exclude or ())
    if not files:
        print("没有可用的参考文件，先跑 find。")
        return 1
    bank = collect_bank(files)
    kinds = {}
    for (pid, sub, filt), c in bank.items():
        cls = c.get("presetClass")
        kinds.setdefault(cls, []).append((pid, sub, filt))
    print("基准来源（%d 个文件）：" % len(files))
    for f in files:
        print("    %s" % f)
    print("\n注意：上面若出现本工具自己生成的文件，用 --exclude 排除，"
          "否则比对是循环自证。\n")
    print("提取到 %d 种效果预设：\n" % len(bank))
    for cls in sorted(kinds):
        label = {"entr": "进入", "exit": "退出", "emph": "强调",
                 "path": "路径", "mediacall": "媒体"}.get(cls, cls)
        print("[%s %s]" % (label, cls))
        for pid, sub, filt in sorted(kinds[cls], key=lambda x: (x[0] or "", x[1] or "")):
            print("    presetID=%-4s subtype=%-4s filter=%s" % (pid, sub, filt))
        print()
    print("把想用的组合填进 pptx_anim.py 的 EFFECTS 即可。")
    print("注意 presetID/subtype 必须搭配正确，否则效果能放但'效果选项'显示不对。")
    return 0


# ---------------------------------------------------------------- check

# 只比"结构"，不比"可调参数"。
#
# 关键区分：节点少了/嵌套错了/效果类别不对 = 真 bug；
# 位移量填 0.6 还是 1.125、延迟填 0 还是 500 = 使用者的正常选择，
# 不该报错。否则一份好稿子会被刷出上百条假警报，工具就没法用了。
_DROP_ATTRS = {"id", "spid", "dur", "tm", "grpId"}
_DROP_TAGS = {"iterate"}          # 逐段/逐字选项，可选


def sig(el, out=None):
    """结构签名。忽略 id/spid/时长/位移量/延迟值，保留影响效果语义的部分。"""
    if out is None:
        out = []
    tag = etree.QName(el).localname
    if tag in _DROP_TAGS:
        return out
    if tag in ("cTn", "tgtEl", "spTgt"):
        out.append(tag)
    else:
        attrs = {}
        for k, v in el.attrib.items():
            name = k.split("}")[-1]
            if name in _DROP_ATTRS:
                continue
            if "#ppt_" in v:
                v = "<MOTION>"              # 位移公式的具体数值不重要
            elif name == "delay" and v != "indefinite":
                v = "<N>"                   # 效果自身的延迟不重要；
                                            # 但 indefinite 是"点击触发"，必须保留
            attrs[name] = v
        out.append(tag + (("|" + ",".join("%s=%s" % kv
                                          for kv in sorted(attrs.items())))
                          if attrs else ""))
    for c in el:
        sig(c, out)
    return out


def cmd_check(args):
    from pptx import Presentation

    path = args.file
    try:
        prs = Presentation(path)
    except Exception as e:
        print("✗ 无法打开：%s" % e)
        return 1
    print("✓ 可被解析，共 %d 页\n" % len(prs.slides))

    z = zipfile.ZipFile(path)
    bank = collect_bank(_ref_files(exclude=[path])) if args.against else {}
    problems = 0
    total_clicks = 0

    for i, sl in enumerate(prs.slides, 1):
        name = "ppt/slides/slide%d.xml" % i
        try:
            root = etree.fromstring(z.read(name))
        except KeyError:
            continue
        tm = root.find(q("p:timing"))
        if tm is None:
            print("  第%2d页  无动画" % i)
            continue

        ids = {sp.get("id") for sp in root.iter(q("p:cNvPr"))}
        spids = [e.get("spid") for e in tm.iter(q("p:spTgt"))]
        dangling = sorted({s for s in spids if s not in ids})
        ctn_ids = [e.get("id") for e in tm.iter(q("p:cTn"))]
        dup = sorted({x for x in ctn_ids if ctn_ids.count(x) > 1})
        clicks = len([e for e in tm.iter(q("p:cTn"))
                      if e.get("nodeType") == "clickEffect"])
        total_clicks += clicks

        bad = []
        if dangling:
            bad.append("悬空 spid %s（会导致 PowerPoint 报'需要修复'）" % dangling)
        if dup:
            bad.append("重复 cTn id %s" % dup)
        if not clicks:
            bad.append("没有任何 clickEffect 点击组")

        note = ""
        if bank and not bad:
            effs = [c for c in tm.iter(q("p:cTn")) if c.get("presetClass")]
            unmatched, mismatched, matched = [], [], 0
            for c in effs:
                fl = [a.get("filter") for a in c.iter(q("p:animEffect"))]
                key = (c.get("presetID"), c.get("presetSubtype"),
                       fl[0] if fl else None)
                ref = bank.get(key)
                if ref is None:
                    unmatched.append(key)
                    continue
                sa, sb = sig(ref), sig(c)
                if sa == sb:
                    matched += 1
                else:
                    mismatched.append((key, sa, sb))
            if matched:
                note += ("\n      ✓ %d 个效果与真实 PowerPoint 基准**逐节点同构**"
                         % matched)
            for key, sa, sb in mismatched:
                diff = next((j for j, (x, y) in enumerate(zip(sa, sb))
                             if x != y), min(len(sa), len(sb)))
                note += ("\n      ✗ %s 结构与基准不同（@%d: 基准[%s] 本文件[%s]，"
                         "长度 %d vs %d）" % (key, diff,
                                              sa[diff] if diff < len(sa) else "-",
                                              sb[diff] if diff < len(sb) else "-",
                                              len(sa), len(sb)))
                problems += 1
            for k in sorted(set(unmatched)):
                note += ("\n      ? %s 在基准库里没有，无法比对"
                         "（可跑 bank 看看有哪些可用）" % (k,))

        status = "✗ " + "；".join(bad) if bad else "✓ 正常"
        print("  第%2d页  效果%2d 点击%d次  %s%s"
              % (i, len(spids), clicks, status, note))
        if bad:
            problems += 1

    print("\n总点击次数：%d" % total_clicks)
    print("问题页数：%d" % problems)
    if not problems:
        print("结构校验通过。注意这只证明 XML 结构合法，"
              "不等于实际播放效果已确认 —— 仍需在 WPS/PowerPoint 里点一遍。")
    return 1 if problems else 0


def main():
    ap = argparse.ArgumentParser(description="pptx 动画 XML 基准发现与校验")
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("find", help="找本机带动画的 pptx")
    f.add_argument("--all", action="store_true", help="搜完所有目录")
    f.set_defaults(func=cmd_find)

    b = sub.add_parser("bank", help="导出效果预设库")
    b.add_argument("--exclude", nargs="*", default=[],
                   help="排除某些文件（例如本工具自己生成的产物）")
    b.set_defaults(func=cmd_bank)

    c = sub.add_parser("check", help="校验某个 pptx 的动画")
    c.add_argument("file")
    c.add_argument("--against", action="store_true",
                   help="同时与真实基准做结构比对（较慢）")
    c.set_defaults(func=cmd_check)

    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
