#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查找文献并生成 GB/T 7714-2015 格式的参考文献引用。

用法:
    python3 find_lit.py "研究方向/领域/论文标题" [--max 10] [--out 输出目录]

数据来源: Crossref REST API (https://api.crossref.org)，免费、无需 API key。
引用文本由 Crossref 返回的结构化元数据程序化生成，不由语言模型凭记忆撰写。
"""

import argparse
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

API_URL = "https://api.crossref.org/works"
# Crossref 的"礼貌池"要求请求方带上联系邮箱，能换来更稳定的响应。
# 不希望公开邮箱的人可以不设，程序会退化为普通 User-Agent。
MAILTO = os.environ.get("CROSSREF_MAILTO", "").strip()
TIMEOUT = 30
DEFAULT_MAX = 10
# 默认输出到当前工作目录下的 literature/ 子文件夹（即你运行命令时所在的项目文件夹）
DEFAULT_OUT = os.path.join(os.getcwd(), "literature")

# Crossref type -> GB/T 7714 文献类型标识码
TYPE_MAP = {
    "journal-article": "J",
    "proceedings-article": "C",
    "book": "M",
    "book-chapter": "M",
    "monograph": "M",
    "reference-entry": "M",
    "dissertation": "D",
    "report": "R",
    "standard": "S",
    "posted-content": "EB/OL",
    "dataset": "DB/OL",
}

# 走完整期刊/会议著录格式的类型码
FULL_FORMAT_TYPES = {"J", "C"}

# 专著：GB/T 7714 要求"出版地: 出版者, 出版年"，与期刊格式不同
BOOK_TYPES = {"M"}

# 非文献条目（插图、评审报告、基金等），检索时直接丢弃
JUNK_TYPES = {"component", "peer-review", "grant", "journal-issue", "journal"}

CJK_RE = re.compile(r"[㐀-䶿一-鿿豈-﫿]")


def has_cjk(text):
    """判断字符串是否含中日韩字符。"""
    return bool(text) and bool(CJK_RE.search(text))


def initials(given):
    """'John Allen' -> 'J A'。GB/T 7714 要求缩写名首字母大写且不加缩写点。"""
    parts = [p for p in re.split(r"[\s\-.]+", given.strip()) if p]
    return " ".join(p[0].upper() for p in parts)


def format_author(author):
    """把单个 Crossref 作者对象格式化为 GB/T 7714 的姓名形式。"""
    family = (author.get("family") or "").strip()
    given = (author.get("given") or "").strip()

    if family:
        # 中文姓名不拆缩写，原样保留
        if has_cjk(family) or has_cjk(given):
            # 中文姓名连写，不加空格
            return "{}{}".format(family, given)
        if given:
            return "{} {}".format(family, initials(given))
        return family

    # 机构作者或仅提供全名的条目
    name = (author.get("name") or "").strip()
    return name


def format_authors(authors, cjk_title):
    """GB/T 7714: 3 名以内全部著录，超过 3 名只著录前 3 名并加 '等'/'et al.'。"""
    if not authors:
        return ""

    names = [n for n in (format_author(a) for a in authors) if n]
    if not names:
        return ""

    if len(names) > 3:
        suffix = "等" if cjk_title else "et al."
        return ", ".join(names[:3]) + ", " + suffix
    return ", ".join(names)


def get_year(item):
    """按优先级从 published / issued / published-print 中取年份。"""
    for key in ("published", "issued", "published-print", "published-online"):
        parts = (item.get(key) or {}).get("date-parts") or []
        if parts and parts[0] and parts[0][0]:
            return str(parts[0][0])
    return ""


def first_of(value):
    """Crossref 很多字段是单元素列表，取第一个非空值。"""
    if isinstance(value, list):
        for v in value:
            if v:
                return v
        return ""
    return value or ""


def format_locator(item):
    """生成 '卷(期): 页码' 形式的定位信息，缺失部分自动省略。"""
    volume = str(item.get("volume") or "").strip()
    issue = str(item.get("issue") or "").strip()
    page = str(item.get("page") or "").strip()

    locator = ""
    if volume and issue:
        locator = "{}({})".format(volume, issue)
    elif volume:
        locator = volume
    elif issue:
        locator = "({})".format(issue)

    if locator and page:
        return "{}: {}".format(locator, page)
    if locator:
        return locator
    return page


def format_book_imprint(item, year):
    """GB/T 7714 专著的出版项：'出版地: 出版者, 出版年'，缺失部分自动省略。"""
    place = first_of(item.get("publisher-location")).strip()
    publisher = first_of(item.get("publisher")).strip()

    if place and publisher:
        imprint = "{}: {}".format(place, publisher)
    else:
        imprint = place or publisher

    return ", ".join(p for p in (imprint, year) if p)


def format_chapter(head, item, year):
    """GB/T 7714 析出文献：作者. 题名[M]//书名. 出版地: 出版者, 出版年: 页码."""
    book_title = first_of(item.get("container-title")).strip()
    imprint = format_book_imprint(item, year)
    page = str(item.get("page") or "").strip()

    tail = imprint
    if page:
        tail = "{}: {}".format(tail, page) if tail else page

    if tail:
        return "{}[M]//{}. {}.".format(head, book_title, tail)
    return "{}[M]//{}.".format(head, book_title)


def format_gbt7714(item, today=None):
    """把一条 Crossref 记录格式化为 GB/T 7714-2015 引用文本。"""
    today = today or datetime.date.today()

    title = first_of(item.get("title")).strip()
    if not title:
        return ""

    # 元数据里的题名常自带结尾句点，去掉以免与著录符号叠加成 ".."
    title = title.rstrip()
    while title.endswith((".", "。")):
        title = title[:-1].rstrip()
    if not title:
        return ""

    cjk_title = has_cjk(title)
    authors = format_authors(item.get("author") or [], cjk_title)
    year = get_year(item)
    venue = first_of(item.get("container-title")).strip()
    doi = (item.get("DOI") or "").strip()
    type_code = TYPE_MAP.get((item.get("type") or "").strip(), "EB/OL")

    # 作者. 题名 （无作者时不留分隔点；"et al." 已含句点则不重复追加）
    if authors:
        author_part = authors if authors.endswith(".") else authors + "."
        head = "{} {}".format(author_part, title)
    else:
        head = title

    if type_code in FULL_FORMAT_TYPES:
        # 作者. 题名[J]. 刊名, 年, 卷(期): 页码.
        tail_parts = [p for p in (venue, year, format_locator(item)) if p]
        citation = "{}[{}]. {}.".format(head, type_code, ", ".join(tail_parts))
    elif type_code in BOOK_TYPES:
        # 书中章节：题名通常与书名不同，按析出文献著录
        is_chapter = (
            (item.get("type") or "").strip() == "book-chapter"
            and venue
            and venue != title
        )
        if is_chapter:
            citation = format_chapter(head, item, year)
        else:
            # 作者. 题名[M]. 出版地: 出版者, 出版年.
            imprint = format_book_imprint(item, year)
            citation = ("{}[M]. {}.".format(head, imprint) if imprint
                        else "{}[M].".format(head))
    else:
        # 作者. 题名[EB/OL]. (年)[引用日期]. https://doi.org/xxx.
        citation = "{}[{}].".format(head, type_code)
        if year:
            citation += " ({}).".format(year)
        citation += "[{}].".format(today.isoformat())
        if doi:
            citation += " https://doi.org/{}.".format(doi)

    citation = re.sub(r"\s+", " ", citation).strip()
    return citation


def fetch(query, rows):
    """调用 Crossref API，返回 (items, error_message)。"""
    # 多取一些，抵消下面过滤掉噪音条目造成的缺额
    fetch_rows = max(1, min(rows + 10, 100))
    params = urllib.parse.urlencode(
        {
            "query": query,
            "rows": fetch_rows,
            "select": "DOI,title,author,container-title,volume,issue,page,"
                      "published,issued,type,publisher,publisher-location",
        }
    )
    user_agent = "find-literature/1.1"
    if MAILTO:
        user_agent += " (mailto:{})".format(MAILTO)
    request = urllib.request.Request(
        "{}?{}".format(API_URL, params),
        headers={
            "User-Agent": user_agent,
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return [], "Crossref 返回 HTTP {} ({})".format(exc.code, exc.reason)
    except urllib.error.URLError as exc:
        return [], "网络连接失败: {}".format(exc.reason)
    except (ValueError, OSError) as exc:
        return [], "响应解析失败: {}".format(exc)

    items = (payload.get("message") or {}).get("items") or []
    items = [
        item for item in items
        if (item.get("type") or "").strip() not in JUNK_TYPES
    ]
    return items[:rows], ""


def build_report(query, items, today=None):
    """组装 txt 文件内容。"""
    today = today or datetime.date.today()
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "文献检索结果",
        "=" * 60,
        "查询词  : {}".format(query),
        "数据来源: Crossref (api.crossref.org)",
        "检索时间: {}".format(timestamp),
        "结果数量: {} 条".format(len(items)),
        "=" * 60,
        "",
        "说明: 以下引用由 Crossref 元数据程序化生成，非模型撰写。",
        "      请用 DOI 逐条核对后再使用。",
        "",
    ]

    for index, item in enumerate(items, start=1):
        citation = format_gbt7714(item, today=today)
        if not citation:
            continue
        doi = (item.get("DOI") or "").strip() or "(无)"
        lines.append("[{}] {}".format(index, citation))
        lines.append("     类型: {} | DOI: {}".format(
            (item.get("type") or "unknown").strip(), doi))
        lines.append("")

    return "\n".join(lines) + "\n"


def safe_slug(query):
    """把查询词变成安全的文件名片段。"""
    slug = re.sub(r"[^\w一-鿿]+", "-", query, flags=re.UNICODE).strip("-")
    return (slug or "query")[:40]


def write_output(query, items, out_dir):
    """写入 txt，返回文件路径。"""
    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(out_dir, "文献_{}_{}.txt".format(safe_slug(query), stamp))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(build_report(query, items))
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="检索 Crossref 并生成 GB/T 7714 格式参考文献到 txt 文件。"
    )
    parser.add_argument("query", help="研究方向 / 领域 / 论文标题")
    parser.add_argument("--max", type=int, default=DEFAULT_MAX,
                        help="检索条数，默认 {}".format(DEFAULT_MAX))
    parser.add_argument("--out", default=DEFAULT_OUT,
                        help="输出目录，默认 {}".format(DEFAULT_OUT))
    args = parser.parse_args(argv)

    try:
        items, error = fetch(args.query, args.max)
    except Exception as exc:  # 兜底，保证命令行不抛栈
        print("检索失败: {}".format(exc), file=sys.stderr)
        return 1

    if error:
        print("检索失败: {}".format(error), file=sys.stderr)
        return 1

    if not items:
        print("没有找到与 “{}” 相关的文献，请尝试更换关键词。".format(args.query))
        return 0

    try:
        path = write_output(args.query, items, args.out)
    except OSError as exc:
        print("写入文件失败: {}".format(exc), file=sys.stderr)
        return 1

    print("找到 {} 条文献，已写入:".format(len(items)))
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
