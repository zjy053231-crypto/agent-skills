"""find_lit.py 的单元测试。

脚本所在目录名带连字符（find-literature），无法直接 import，
所以用 importlib 按文件路径加载。
"""

import datetime
import importlib.util
import pathlib
import sys

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "find_lit.py"
_spec = importlib.util.spec_from_file_location("find_lit", MODULE_PATH)
find_lit = importlib.util.module_from_spec(_spec)
sys.modules["find_lit"] = find_lit
_spec.loader.exec_module(find_lit)

TODAY = datetime.date(2026, 11, 16)


def journal(**overrides):
    item = {
        "type": "journal-article",
        "title": ["Prompt Engineering and Creative Practice"],
        "author": [
            {"family": "Kim", "given": "Sangho"},
            {"family": "Kwon", "given": "Kyung"},
            {"family": "Park", "given": "Seung-Pyo"},
        ],
        "container-title": ["International Journal of Human-Computer Interaction"],
        "volume": "40",
        "issue": "3",
        "page": "101-115",
        "published": {"date-parts": [[2026]]},
        "DOI": "10.1080/10447318.2026.2706942",
    }
    item.update(overrides)
    return item


# ---------------------------------------------------------------- 期刊 / 会议

def test_journal_article_full_imprint():
    assert find_lit.format_gbt7714(journal(), today=TODAY) == (
        "Kim S, Kwon K, Park S P. Prompt Engineering and Creative Practice[J]. "
        "International Journal of Human-Computer Interaction, 2026, 40(3): 101-115."
    )


def test_more_than_three_authors_use_et_al():
    item = journal(author=journal()["author"] + [{"family": "Lee", "given": "Min"}])
    citation = find_lit.format_gbt7714(item, today=TODAY)
    assert "Kim S, Kwon K, Park S P, et al." in citation


def test_chinese_title_uses_deng():
    item = journal(
        title=["生成式人工智能的创作劳动"],
        author=[
            {"family": "张", "given": "三"},
            {"family": "李", "given": "四"},
            {"family": "王", "given": "五"},
            {"family": "赵", "given": "六"},
        ],
    )
    citation = find_lit.format_gbt7714(item, today=TODAY)
    assert "张三, 李四, 王五, 等." in citation


def test_no_author_leaves_no_leading_punctuation():
    item = journal(author=[])
    citation = find_lit.format_gbt7714(item, today=TODAY)
    assert citation.startswith("Prompt Engineering and Creative Practice[J].")


def test_missing_volume_and_page_degrades_gracefully():
    citation = find_lit.format_gbt7714(
        journal(volume="", issue="", page=""), today=TODAY
    )
    assert citation.endswith(
        "International Journal of Human-Computer Interaction, 2026."
    )


def test_issue_without_volume():
    locator = find_lit.format_locator({"issue": "2", "page": "7"})
    assert locator == "(2): 7"


def test_conference_article():
    item = journal(
        type="proceedings-article",
        **{"container-title": ["Proceedings of CHI 2025"]},
        volume="",
        issue="",
        page="1-12",
    )
    citation = find_lit.format_gbt7714(item, today=TODAY)
    assert "[C]." in citation
    assert "Proceedings of CHI 2025, 2026, 1-12." in citation


# ---------------------------------------------------------------- 专著

def book(**overrides):
    item = {
        "type": "book",
        "title": ["Understanding Media"],
        "author": [{"family": "McLuhan", "given": "Marshall"}],
        "publisher": "Routledge",
        "publisher-location": "London",
        "published": {"date-parts": [[1964]]},
    }
    item.update(overrides)
    return item


def test_book_includes_place_and_publisher():
    assert find_lit.format_gbt7714(book(), today=TODAY) == (
        "McLuhan M. Understanding Media[M]. London: Routledge, 1964."
    )


def test_book_without_place():
    citation = find_lit.format_gbt7714(
        book(**{"publisher-location": ""}), today=TODAY
    )
    assert citation == "McLuhan M. Understanding Media[M]. Routledge, 1964."


def test_book_with_publisher_but_no_year():
    item = book(published={}, issued={})
    assert find_lit.format_gbt7714(item, today=TODAY) == (
        "McLuhan M. Understanding Media[M]. London: Routledge."
    )


def test_book_without_imprint_does_not_emit_stray_period():
    item = book(publisher="", **{"publisher-location": ""}, published={}, issued={})
    assert find_lit.format_gbt7714(item, today=TODAY) == (
        "McLuhan M. Understanding Media[M]."
    )


# ---------------------------------------------------------------- 书中章节

def chapter(**overrides):
    item = {
        "type": "book-chapter",
        "title": ["Distant(ly) Reading Alexander Kluge's Distant Writing"],
        "author": [{"family": "Martens", "given": "Gunther"}],
        "container-title": ["Distant Writing"],
        "publisher": "V&R Unipress",
        "publisher-location": "Göttingen",
        "page": "29-46",
        "published": {"date-parts": [[2014]]},
    }
    item.update(overrides)
    return item


def test_book_chapter_uses_double_slash():
    assert find_lit.format_gbt7714(chapter(), today=TODAY) == (
        "Martens G. Distant(ly) Reading Alexander Kluge's Distant Writing[M]//"
        "Distant Writing. Göttingen: V&R Unipress, 2014: 29-46."
    )


def test_book_chapter_without_page():
    citation = find_lit.format_gbt7714(chapter(page=""), today=TODAY)
    assert citation.endswith("Göttingen: V&R Unipress, 2014.")


def test_chapter_with_title_equal_to_book_title_falls_back_to_monograph():
    item = chapter(
        **{"container-title": ["Distant(ly) Reading Alexander Kluge's Distant Writing"]}
    )
    assert "//" not in find_lit.format_gbt7714(item, today=TODAY)


# ---------------------------------------------------------------- 预印本 / 其他

def test_preprint_is_ebol_with_access_date():
    item = {
        "type": "posted-content",
        "title": ["Distant Writing"],
        "author": [{"family": "Floridi", "given": "Luciano"}],
        "published": {"date-parts": [[2025]]},
        "DOI": "10.1007/s11023-025-09732-1",
    }
    assert find_lit.format_gbt7714(item, today=TODAY) == (
        "Floridi L. Distant Writing[EB/OL]. (2025).[2026-11-16]. "
        "https://doi.org/10.1007/s11023-025-09732-1."
    )


def test_unknown_type_falls_back_to_ebol():
    item = journal(type="mystery-type")
    assert "[EB/OL]" in find_lit.format_gbt7714(item, today=TODAY)


def test_trailing_period_in_title_is_stripped():
    citation = find_lit.format_gbt7714(
        journal(title=["Prompt Engineering."]), today=TODAY
    )
    assert "Prompt Engineering[J]." in citation
    assert ".." not in citation


# ---------------------------------------------------------------- 辅助函数

def test_has_cjk():
    assert find_lit.has_cjk("生成式") is True
    assert find_lit.has_cjk("generative") is False
    assert find_lit.has_cjk("") is False


def test_initials_strips_punctuation():
    assert find_lit.initials("Seung-Pyo") == "S P"
    assert find_lit.initials("Luciano") == "L"


def test_get_year_priority():
    item = {
        "published": {"date-parts": [[2026]]},
        "issued": {"date-parts": [[2025]]},
    }
    assert find_lit.get_year(item) == "2026"


def test_get_year_falls_back():
    assert find_lit.get_year({"issued": {"date-parts": [[2024]]}}) == "2024"
    assert find_lit.get_year({}) == ""


def test_first_of():
    assert find_lit.first_of(["", "b"]) == "b"
    assert find_lit.first_of("x") == "x"
    assert find_lit.first_of(None) == ""


def test_safe_slug_keeps_chinese():
    assert find_lit.safe_slug("生成式 人工智能") == "生成式-人工智能"
