#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
给 python-pptx 生成的页面加"点击触发"的进入动画。

python-pptx 没有动画 API，动画存在 slide XML 的 <p:timing> 节点里，
只能自己注入。本模块里的 XML 模板已经和真实 PowerPoint 生成的
动画树做过逐节点比对（见 anim_check.py），不是凭记忆写的。

用法（不需要改动你原有的 tbox/rect 等辅助函数）：

    from pptx_anim import Anim, mark, since

    s = blank()
    head(s, ...)              # 标题不要动画

    m = mark(s)
    lead = tbox(s, ...); para(lead, ...)
    g_lead = since(s, m)      # 这一批形状

    m = mark(s)
    for ...: card(s, ...); ...
    g_cards = since(s, m)

    Anim(s).add(g_lead, "fade").add(g_cards, "rise").apply()

每个 add() = 放映时的一次点击。同一组内的形状一起出现。
"""

from pptx.oxml import parse_xml
from pptx.oxml.ns import qn, nsdecls

# 进入效果预设。pid/sub/filt 三元组必须与 PowerPoint 的实际预设一致，
# 否则效果能放但"效果选项"里显示不对。这两个已用真实文件验证过。
EFFECTS = {
    # 淡入：最克制，适合正文
    "fade": dict(pid=10, sub=0, filt="fade", dur=450, y=None),
    # 上浮：轻微上移 + 淡入，适合强调性元素（数据卡、结论）
    "rise": dict(pid=12, sub=4, filt="wipe(up)", dur=550,
                 y="#ppt_y+#ppt_h*0.6"),
}


def mark(slide):
    """记下当前形状数量。之后用 since(slide, m) 取这一批新加的形状。

    依赖 slide.shapes 按加入顺序排列这一事实，所以不用改任何辅助函数。
    """
    return len(slide.shapes)


def since(slide, m):
    return list(slide.shapes)[m:]


class Anim:
    """收集"点击组"，最后由 apply() 一次性写入 p:timing。"""

    def __init__(self, slide):
        self.slide = slide
        self.groups = []

    def add(self, shapes, effect="fade"):
        """加一个点击组。shapes 可以是形状列表或单个形状。"""
        if shapes is None:
            return self
        if not isinstance(shapes, (list, tuple)):
            shapes = [shapes]
        shapes = [sp for sp in shapes if sp is not None]
        if shapes:
            if effect not in EFFECTS:
                raise ValueError("未知效果 %r，可选：%s"
                                 % (effect, "、".join(EFFECTS)))
            self.groups.append((shapes, effect))
        return self

    def apply(self):
        if not self.groups:
            return
        _write(self.slide, self.groups)


def _write(slide, groups):
    nid = [2]                       # id 1/2 被根节点和 mainSeq 占用

    def nx():
        nid[0] += 1
        return nid[0]

    def one(sp, eff, node_type):
        sid = sp.shape_id
        e = EFFECTS[eff]
        eff_id = nx()
        parts = []
        set_id = nx()
        parts.append(
            '<p:set><p:cBhvr><p:cTn id="%d" dur="1" fill="hold">'
            '<p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn>'
            '<p:tgtEl><p:spTgt spid="%d"/></p:tgtEl>'
            '<p:attrNameLst><p:attrName>style.visibility</p:attrName>'
            '</p:attrNameLst></p:cBhvr>'
            '<p:to><p:strVal val="visible"/></p:to></p:set>' % (set_id, sid))
        if e["y"]:
            a_id = nx()
            parts.append(
                '<p:anim calcmode="lin" valueType="num"><p:cBhvr additive="base">'
                '<p:cTn id="%d" dur="%d"/><p:tgtEl><p:spTgt spid="%d"/></p:tgtEl>'
                '<p:attrNameLst><p:attrName>ppt_y</p:attrName></p:attrNameLst>'
                '</p:cBhvr><p:tavLst>'
                '<p:tav tm="0"><p:val><p:strVal val="%s"/></p:val></p:tav>'
                '<p:tav tm="100000"><p:val><p:strVal val="#ppt_y"/></p:val></p:tav>'
                '</p:tavLst></p:anim>' % (a_id, e["dur"], sid, e["y"]))
        ef_id = nx()
        parts.append(
            '<p:animEffect transition="in" filter="%s"><p:cBhvr>'
            '<p:cTn id="%d" dur="%d"/><p:tgtEl><p:spTgt spid="%d"/></p:tgtEl>'
            '</p:cBhvr></p:animEffect>' % (e["filt"], ef_id, e["dur"], sid))
        return ('<p:par><p:cTn id="%d" presetID="%d" presetClass="entr" '
                'presetSubtype="%d" fill="hold" nodeType="%s">'
                '<p:stCondLst><p:cond delay="0"/></p:stCondLst>'
                '<p:childTnLst>%s</p:childTnLst></p:cTn></p:par>'
                % (eff_id, e["pid"], e["sub"], node_type, "".join(parts)))

    body = []
    for shapes, eff in groups:
        inner = "".join(one(sp, eff, "clickEffect" if i == 0 else "withEffect")
                        for i, sp in enumerate(shapes))
        body.append('<p:par><p:cTn id="%d" fill="hold">'
                    '<p:stCondLst><p:cond delay="indefinite"/></p:stCondLst>'
                    '<p:childTnLst><p:par><p:cTn id="%d" fill="hold">'
                    '<p:stCondLst><p:cond delay="0"/></p:stCondLst>'
                    '<p:childTnLst>%s</p:childTnLst></p:cTn></p:par>'
                    '</p:childTnLst></p:cTn></p:par>' % (nx(), nx(), inner))

    xml = ('<p:timing %s><p:tnLst><p:par>'
           '<p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot">'
           '<p:childTnLst><p:seq concurrent="1" nextAc="seek">'
           '<p:cTn id="2" dur="indefinite" nodeType="mainSeq">'
           '<p:childTnLst>%s</p:childTnLst></p:cTn>'
           '<p:prevCondLst><p:cond evt="onPrev" delay="0">'
           '<p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>'
           '<p:nextCondLst><p:cond evt="onNext" delay="0">'
           '<p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst>'
           '</p:seq></p:childTnLst></p:cTn></p:par></p:tnLst></p:timing>'
           % (nsdecls("p", "a"), "".join(body)))

    sld = slide._element
    old = sld.find(qn("p:timing"))
    if old is not None:
        sld.remove(old)                      # 重复 apply 时替换而不是叠加
    el = parse_xml(xml)
    ext = sld.find(qn("p:extLst"))
    if ext is not None:
        ext.addprevious(el)                  # p:sld 的子元素有固定顺序
    else:
        sld.append(el)
