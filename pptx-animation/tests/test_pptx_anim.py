"""pptx_anim.py 的测试。

目录名带连字符（pptx-animation），无法直接 import，用 importlib 按路径加载。
测试需要 python-pptx 作为依赖（pip install -r requirements-dev.txt）。
"""

import importlib.util
import pathlib
import sys

import pytest
from lxml import etree
from pptx import Presentation
from pptx.oxml.ns import qn
from pptx.util import Inches

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "pptx_anim.py"
_spec = importlib.util.spec_from_file_location("pptx_anim", MODULE_PATH)
pptx_anim = importlib.util.module_from_spec(_spec)
sys.modules["pptx_anim"] = pptx_anim
_spec.loader.exec_module(pptx_anim)


def blank_slide():
    """新建一个空白版式的幻灯片（版式索引 6 = Blank）。"""
    prs = Presentation()
    return prs.slides.add_slide(prs.slide_layouts[6])


def add_box(slide):
    return slide.shapes.add_textbox(Inches(1), Inches(1), Inches(2), Inches(1))


def timing_count(slide):
    return len(slide._element.findall(qn("p:timing")))


def slide_xml(slide):
    return etree.tostring(slide._element, encoding="unicode")


# ---------------------------------------------------------------- mark / since

def test_mark_and_since_return_only_new_shapes():
    s = blank_slide()
    add_box(s)
    m = pptx_anim.mark(s)
    new = [add_box(s), add_box(s)]
    assert [sp.shape_id for sp in pptx_anim.since(s, m)] == [sp.shape_id for sp in new]


def test_since_with_no_new_shapes_is_empty():
    s = blank_slide()
    add_box(s)
    m = pptx_anim.mark(s)
    assert pptx_anim.since(s, m) == []


def test_mark_on_empty_slide_is_zero():
    assert pptx_anim.mark(blank_slide()) == 0


# ---------------------------------------------------------------- Anim.add

def test_unknown_effect_raises():
    s = blank_slide()
    with pytest.raises(ValueError):
        pptx_anim.Anim(s).add([add_box(s)], "explode")


def test_add_none_is_ignored():
    s = blank_slide()
    pptx_anim.Anim(s).add(None).apply()
    assert timing_count(s) == 0


def test_apply_without_groups_writes_nothing():
    s = blank_slide()
    pptx_anim.Anim(s).apply()
    assert timing_count(s) == 0


def test_add_accepts_single_shape():
    s = blank_slide()
    box = add_box(s)
    pptx_anim.Anim(s).add(box, "fade").apply()
    assert timing_count(s) == 1


# ---------------------------------------------------------------- 输出结构

def test_apply_writes_one_timing_element():
    s = blank_slide()
    pptx_anim.Anim(s).add([add_box(s), add_box(s)], "fade").apply()
    assert timing_count(s) == 1


def test_apply_twice_replaces_instead_of_appending():
    s = blank_slide()
    box = add_box(s)
    pptx_anim.Anim(s).add([box], "fade").apply()
    pptx_anim.Anim(s).add([box], "rise").apply()
    assert timing_count(s) == 1


def test_first_shape_of_group_triggers_on_click():
    s = blank_slide()
    shapes = [add_box(s) for _ in range(3)]
    pptx_anim.Anim(s).add(shapes, "fade").add([add_box(s)], "rise").apply()

    xml = slide_xml(s)
    assert xml.count('nodeType="clickEffect"') == 2   # 每组第一个
    assert xml.count('nodeType="withEffect"') == 2    # 同组其余


def test_effect_presets_carry_required_keys():
    for name in ("fade", "rise"):
        effect = pptx_anim.EFFECTS[name]
        assert {"pid", "sub", "filt", "dur", "y"} <= set(effect)
        assert effect["dur"] > 0


def test_timing_is_inserted_before_extlst():
    """p:sld 的子元素顺序有约束，timing 必须在 extLst 之前。"""
    s = blank_slide()
    ext = s._element.makeelement(qn("p:extLst"), {})
    s._element.append(ext)

    pptx_anim.Anim(s).add([add_box(s)], "fade").apply()

    children = list(s._element)
    timing_index = children.index(s._element.find(qn("p:timing")))
    ext_index = children.index(ext)
    assert timing_index < ext_index
