"""tools/zh_labels.py — post-render Chinese navbar/footer labels and navbar current-item marks."""
import importlib.util
import re
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[2] / "site"
SPEC = importlib.util.spec_from_file_location("zh_labels", SITE / "tools" / "zh_labels.py")
zh_labels = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(zh_labels)

NAV = """<a class="navbar-brand" href="../index.html"><span class="navbar-title">Mingyang Liu</span></a>
<ul class="navbar-nav">
<li class="nav-item"><a class="nav-link" href="../research/index.html"><span class="menu-text">Research</span></a></li>
<li class="nav-item"><a class="nav-link" href="../projects/index.html"><span class="menu-text">Projects</span></a></li>
<li class="nav-item"><a class="nav-link" href="../data-code.html"><span class="menu-text">Data &amp; Code</span></a></li>
<li class="nav-item"><a class="nav-link" href="../advisory.html"><span class="menu-text">Advisory</span></a></li>
<li class="nav-item"><a class="nav-link" href="../blog/index.html"><span class="menu-text">Blog</span></a></li>
<li class="nav-item"><a class="nav-link" href="../cv.html"><span class="menu-text">CV</span></a></li>
<li class="nav-item"><a class="nav-link" href="../software.html"><span class="menu-text">Software</span></a></li>
<li class="nav-item"><a class="nav-link" href="../photography/index.html"><span class="menu-text">Photography</span></a></li>
<li class="nav-item"><a class="nav-link" href="../zh/"><span class="menu-text">中文</span></a></li>
</ul>"""
FOOTER = """<footer class="footer"><div class="nav-footer">
<div class="nav-footer-left"><p>© 2026 Mingyang Liu · <a href="../advisory.html">Independent advisory</a> · <a href="https://www.pexels.com/@Mingyang-LIU-301813241" target="_blank" rel="noopener">Photography (Pexels)</a></p></div>
<div class="nav-footer-right"><p>Built with Quarto · <a href="../privacy.html">Privacy</a> · Exhibit data are generated from the author’s research materials; see each figure’s provenance line. · Campus photographs courtesy of the University of Michigan, Columbia University and Imperial College London.</p></div>
</div></footer>"""
PAGE = "<html><body>" + NAV + "<main>Privacy is not a label here. Built with Quarto? Research</main>" + FOOTER + "</body></html>"


def test_rewrite_translates_the_eight_labels_and_the_footer_sentence():
    out = zh_labels.rewrite(PAGE)
    for zh in ("研究", "项目", "数据与代码", "咨询", "博客", "简历", "软件", "摄影", "English"):
        assert f'<span class="menu-text">{zh}</span>' in out
    for en in ("Research", "Projects", "Data &amp; Code", "Blog", "CV", "Software", "Photography", "中文"):
        assert f'<span class="menu-text">{en}</span>' not in out
    assert '<a href="/zh/privacy.html">隐私</a>' in out
    # The top-level Data & Code item opens the Chinese page on zh pages.
    assert 'href="/zh/data-code.html"><span class="menu-text">数据与代码</span>' in out
    assert "../data-code.html" not in out
    # Projects (formerly Blog) and CV: zh pages open the Chinese projects index and the Chinese CV.
    assert 'href="/zh/projects/index.html"><span class="menu-text">项目</span>' in out
    assert "../projects/index.html" not in out
    # Blog (kept for old pages): zh pages open the Chinese blog.
    assert 'href="/zh/blog/index.html"><span class="menu-text">博客</span>' in out
    assert 'href="/zh/cv.html"><span class="menu-text">简历</span>' in out
    # Advisory (kept for old pages): zh pages open the Chinese advisory page.
    assert 'href="/zh/advisory.html"><span class="menu-text">咨询</span>' in out and "../advisory.html" not in out
    assert "../blog/index.html" not in out and "../cv.html" not in out
    # Footer Photography link: Chinese label, same external target, still a new tab.
    assert 'href="https://www.pexels.com/@Mingyang-LIU-301813241" target="_blank" rel="noopener">摄影作品（Pexels）</a>' in out
    assert "© 2026 刘明杨 · " in out and "© 2026 Mingyang Liu" not in out
    # The site name leads to the Chinese home on zh pages.
    assert '<a class="navbar-brand" href="/zh/">' in out and 'href="../index.html"' not in out
    assert "../privacy.html" not in out
    assert "校园照片由密歇根大学、哥伦比亚大学和帝国理工学院提供。" in out
    assert "Campus photographs" not in out
    assert "使用 Quarto 构建 · " in out
    assert "展示数据由作者的研究资料生成；出处见各图的来源说明。" in out
    assert "Exhibit data" not in out
    # Body text is untouched: only navbar spans and the <footer> block are rewritten.
    assert "Privacy is not a label here. Built with Quarto? Research" in out


def test_rewrite_accepts_straight_apostrophe_and_is_idempotent():
    straight = PAGE.replace("’", "'")
    out = zh_labels.rewrite(straight)
    assert "展示数据由作者的研究资料生成" in out and "Exhibit data" not in out
    assert zh_labels.rewrite(out) == out


def test_rewrite_is_a_no_op_without_labels():
    html = "<html><body><p>Nothing to translate.</p></body></html>"
    assert zh_labels.rewrite(html) == html


def test_is_zh_output_is_relative_to_the_output_dir(tmp_path):
    out = tmp_path / "zh" / "checkout" / "_site"          # a `zh` directory above the output dir
    (out / "zh" / "research").mkdir(parents=True)
    (out / "research").mkdir()
    assert zh_labels.is_zh_output(out / "zh" / "index.html", out)
    assert zh_labels.is_zh_output(out / "zh" / "research" / "x.html", out)
    assert not zh_labels.is_zh_output(out / "index.html", out)
    assert not zh_labels.is_zh_output(out / "research" / "index.html", out)
    assert not zh_labels.is_zh_output(out / "zh" / "._index.html", out)
    assert not zh_labels.is_zh_output(out / "zh" / "data.json", out)
    assert not zh_labels.is_zh_output(tmp_path / "zh" / "elsewhere.html", out)
    assert not zh_labels.is_zh_output(Path("zh/index.html"), out)   # bare relative path, not under out


def test_output_dir_honours_quarto_env(monkeypatch, tmp_path):
    monkeypatch.setenv("QUARTO_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("QUARTO_PROJECT_OUTPUT_DIR", raising=False)
    assert zh_labels.output_dir() == tmp_path / "_site"
    monkeypatch.setenv("QUARTO_PROJECT_OUTPUT_DIR", "out")
    assert zh_labels.output_dir() == tmp_path / "out"


def _page(lang, alternates=True):
    head = ('<link rel="alternate" hreflang="en" href="https://yl7919.github.io/research/x.html">\n'
            '<link rel="alternate" hreflang="zh-Hans" href="https://yl7919.github.io/zh/research/x.html">\n') if alternates else ""
    label = "English" if lang == "zh" else "中文"
    return (f'<html lang="{lang}"><head>{head}</head><body><ul class="navbar-nav">'
            f'<li class="nav-item"><a class="nav-link" href="../cv.html"><span class="menu-text">CV</span></a></li>'
            f'<li class="nav-item"><a class="nav-link" href="../zh/"> <span class="menu-text">{label}</span></a></li></ul></body></html>')


def test_set_toggle_points_at_the_counterpart_both_ways():
    en = zh_labels.set_toggle(_page("en"))
    assert 'class="nav-link lang-toggle" href="/zh/research/x.html"' in en
    zh = zh_labels.set_toggle(_page("zh"))
    assert 'class="nav-link lang-toggle" href="/research/x.html"' in zh
    assert 'href="../cv.html"' in en                       # other nav items untouched
    assert zh_labels.set_toggle(en) == en                  # idempotent


def test_set_toggle_leaves_pages_without_alternates_alone():
    html = _page("en", alternates=False)
    assert zh_labels.set_toggle(html) == html


def test_label_toggle_names_the_language_of_label_and_target():
    """The endonym stays the accessible name; lang/hreflang let a screen reader read 中文 in Chinese."""
    en = zh_labels.label_toggle(zh_labels.set_toggle(_page("en")))
    assert 'href="/zh/research/x.html" lang="zh-Hans" hreflang="zh-Hans"> <span class="menu-text">中文</span>' in en
    zh = zh_labels.label_toggle(zh_labels.set_toggle(_page("zh")))
    assert 'href="/research/x.html" lang="en" hreflang="en"> <span class="menu-text">English</span>' in zh
    bare = zh_labels.label_toggle(_page("en", alternates=False))       # Quarto's /zh/ link: same attributes
    assert 'href="../zh/" lang="zh-Hans" hreflang="zh-Hans">' in bare
    for out in (en, zh, bare):
        assert "aria-label" not in out
        assert len(re.findall(r'<a [^>]*\blang=', out)) == 1             # only the toggle; CV untouched
        assert zh_labels.label_toggle(out) == out                        # idempotent
        assert zh_labels.set_toggle(out) == out


def test_navbar_scripts_are_wired_and_no_script_forces_aria_current_page():
    """assets/after-body.html loads the navbar scripts (deferred, after Bootstrap); a project page is marked by
    tools/zh_labels.py (aria-current="true" below an index), never forced to "page" by an inline script."""
    after = (SITE / "assets" / "after-body.html").read_text(encoding="utf-8")
    for js in ("lang-toggle.js", "nav-active.js", "nav-a11y.js"):
        assert f'<script src="/assets/js/{js}" defer></script>' in after
        assert (SITE / "assets" / "js" / js).exists()
    assert "aria-current" not in after
    keys = (SITE / "assets" / "js" / "nav-a11y.js").read_text(encoding="utf-8")
    assert 'setAttribute("role", "button")' in keys and 'e.key !== " "' in keys and "preventDefault()" in keys
    toggle = (SITE / "assets" / "js" / "lang-toggle.js").read_text(encoding="utf-8")
    assert 'removeAttribute("aria-label")' in toggle and 'setAttribute("hreflang"' in toggle


def test_rewrite_uses_full_width_parentheses_for_the_licence_link():
    html = '<div>x<a rel="license" href="https://creativecommons.org/licenses/by/4.0/">(查看许可协议)</a></div>'
    assert "（查看许可协议）" in zh_labels.rewrite(html)


MENU = """<li class="nav-item dropdown">
<a class="nav-link dropdown-toggle" href="#" id="nav-menu-research" role="link" data-bs-toggle="dropdown" aria-expanded="false"><span class="menu-text">Research</span></a>
<ul class="dropdown-menu" aria-labelledby="nav-menu-research">
<li class="dropdown-header">Five questions, each with an interactive example</li>
<li><a class="dropdown-item" href="../../research/geometric-framework.html#gf-example">
 <span class="dropdown-text"><span class="rq"><span class="n">1</span> <span class="q">Which ruler?</span> <span class="do">Drag the overlap: the plain ruler lets two blocks sum to 190%</span></span></span></a></li>
<li><hr class="dropdown-divider"></li>
<li><a class="dropdown-item" href="../../research/index.html"><span class="dropdown-text">All research</span></a></li>
</ul></li>"""


def test_rewrite_menu_gives_the_research_dropdown_zh_hrefs_and_text_and_is_idempotent():
    page = '<html><body><ul class="navbar-nav">' + MENU + "</ul></body></html>"
    out = zh_labels.rewrite(page)
    assert 'href="/zh/research/geometric-framework.html#gf-example"' in out
    assert 'href="/zh/research/index.html"' in out
    assert "../../research/" not in out
    for zh in ("五个问题，每个都有一个可以动手试的例子", "用哪把尺子？", "全部研究", '<span class="menu-text">研究</span>'):
        assert zh in out
    for en in ("Which ruler?", "Five questions", "All research", "Drag the overlap"):
        assert en not in out
    assert '<span class="n">1</span> <span class="q">' in out       # spaces between spans kept
    assert zh_labels.rewrite(out) == out


def test_menu_tables_match_quarto_yml():
    """The EN menu in _quarto.yml and MENU_ITEMS/MENU_HEADERS must stay in step; otherwise
    rewrite_menu() silently leaves English text and hrefs on zh pages."""
    import yaml
    cfg = yaml.safe_load((SITE / "_quarto.yml").read_text(encoding="utf-8"))
    menu = next(i for i in cfg["website"]["navbar"]["left"] if isinstance(i, dict) and i.get("text") == "Research")["menu"]
    hrefs = sorted(m["href"].replace(".qmd", ".html") for m in menu if isinstance(m, dict) and "href" in m)
    assert hrefs == sorted(zh_labels.MENU_ITEMS)
    assert [m["text"] for m in menu if isinstance(m, dict) and "href" not in m] == list(zh_labels.MENU_HEADERS)


ACTIVE_NAV = """<a class="navbar-brand" href="/zh/"><span class="navbar-title">Mingyang Liu</span></a>
<ul class="navbar-nav">
<li class="nav-item dropdown"><a class="nav-link dropdown-toggle" href="#" id="nav-menu-research"><span class="menu-text">研究</span></a></li>
<li class="nav-item"><a class="nav-link" href="/zh/projects/index.html"><span class="menu-text">项目</span></a></li>
<li class="nav-item"><a class="nav-link" href="/zh/data-code.html"><span class="menu-text">数据与代码</span></a></li>
<li class="nav-item"><a class="nav-link" href="/zh/blog/index.html"><span class="menu-text">博客</span></a></li>
<li class="nav-item"><a class="nav-link" href="/zh/cv.html"><span class="menu-text">简历</span></a></li>
<li class="nav-item"><a class="nav-link lang-toggle" href="/blog/"><span class="menu-text">English</span></a></li>
</ul>"""


def _active(html):
    return re.findall(r'<a class="nav-link[^"]*\bactive\b[^"]*" href="([^"]*)"[^>]*aria-current="([^"]*)"', html)


def test_mark_active_highlights_the_rewritten_zh_items():
    assert _active(zh_labels.mark_active(ACTIVE_NAV, "/zh/blog/index.html")) == [("/zh/blog/index.html", "page")]
    assert _active(zh_labels.mark_active(ACTIVE_NAV, "/zh/cv.html")) == [("/zh/cv.html", "page")]
    assert _active(zh_labels.mark_active(ACTIVE_NAV, "/zh/data-code.html")) == [("/zh/data-code.html", "page")]
    # A blog post highlights its section; the home pages and the research pages highlight nothing here.
    assert _active(zh_labels.mark_active(ACTIVE_NAV, "/zh/blog/strategy-notes.html")) == [("/zh/blog/index.html", "true")]
    # A project page highlights 项目; the projects index is the current page.
    assert _active(zh_labels.mark_active(ACTIVE_NAV, "/zh/projects/index.html")) == [("/zh/projects/index.html", "page")]
    assert _active(zh_labels.mark_active(ACTIVE_NAV, "/zh/projects/naipca-toolkit.html")) == [("/zh/projects/index.html", "true")]
    for page in ("/zh/index.html", "/zh/research/characteristic-geometry.html"):
        assert _active(zh_labels.mark_active(ACTIVE_NAV, page)) == []
    once = zh_labels.mark_active(ACTIVE_NAV, "/zh/cv.html")
    assert zh_labels.mark_active(once, "/zh/cv.html") == once          # idempotent


def test_mark_active_resolves_relative_hrefs_and_keeps_quarto_marks():
    en = ('<a class="nav-link" href="../blog/index.html"><span class="menu-text">Blog</span></a>'
          '<a class="nav-link active" href="../cv.html" aria-current="page"><span class="menu-text">CV</span></a>'
          '<a class="nav-link lang-toggle" href="/zh/blog/x.html"><span class="menu-text">中文</span></a>')
    out = zh_labels.mark_active(en, "/blog/x.html")
    assert _active(out) == [("../blog/index.html", "true"), ("../cv.html", "page")]
    assert zh_labels.site_path(Path("/nowhere/x.html"), Path("/elsewhere")) is None


def test_research_menu_has_no_job_market_pill():
    """No job-market label in the Research dropdown, in either language."""
    zh_items = " ".join(text for _, text in zh_labels.MENU_ITEMS.values())
    assert "求职论文" not in zh_items and "rq-jmp" not in zh_items
    quarto_yml = (SITE / "_quarto.yml").read_text(encoding="utf-8")
    assert "Job market paper" not in quarto_yml and "rq-jmp" not in quarto_yml


def test_footer_advisory_link_is_chinese_on_zh_pages_and_idempotent():
    """The Advisory page is linked from the footer as "Independent advisory"; on zh pages the label is
    独立咨询 and the link opens the Chinese page."""
    out = zh_labels.rewrite(PAGE)
    assert '<a href="/zh/advisory.html">独立咨询</a>' in out
    assert "Independent advisory" not in out
    for href in ("./advisory.html", "/advisory.html", "../../advisory.html"):
        page = PAGE.replace('href="../advisory.html">Independent advisory', f'href="{href}">Independent advisory')
        assert '<a href="/zh/advisory.html">独立咨询</a>' in zh_labels.rewrite(page)
    assert zh_labels.rewrite(out) == out
    # Body text naming the label is untouched (only the <footer> block is rewritten).
    body = "<html><body><main><a href=\"../advisory.html\">Independent advisory</a></main></body></html>"
    assert zh_labels.rewrite(body) == body


def test_quarto_yml_navbar_has_four_tabs_and_footer_links_advisory():
    """Navbar: Research | Projects | Data & Code | CV (+ the language toggle), with any menu the release adds;
    Advisory sits in the footer, with the label that FOOTER_LABELS translates."""
    import yaml
    cfg = yaml.safe_load((SITE / "_quarto.yml").read_text(encoding="utf-8"))
    left = cfg["website"]["navbar"]["left"]
    expected = ["Research"]
    # The Research Toolkit menu sits between Research and Projects.
    expected.append("Research Toolkit")
    expected += ["Projects", "Data & Code", "CV"]
    assert [i["text"] for i in left] == expected
    assert [i["text"] for i in cfg["website"]["navbar"]["right"]] == ["中文"]
    # The visible endonym is the toggle's accessible name: no aria-label (Quarto would drop it anyway).
    assert all("aria-label" not in i for i in cfg["website"]["navbar"]["right"])
    assert not any("advisory" in str(i.get("href", "")) for i in left)
    footer = cfg["website"]["page-footer"]["left"]
    assert "[Independent advisory](/advisory.qmd)" in footer
    assert "Independent advisory" in zh_labels.FOOTER_LABELS and zh_labels.FOOTER_LABELS["Independent advisory"] == "独立咨询"


def _toolkit_expected() -> dict[str, tuple[str, str, str]]:
    """EN href -> (EN label, ZH label, ZH href) for every Research Toolkit item in this build."""
    items = {}
    items["projects/forecast-evaluation.html"] = (
        "Macro Forecast Evaluation", "宏观预测评估", "/zh/projects/forecast-evaluation.html")
    items["research-toolkit/index.html"] = ("Toolkit Overview", "工具概览", "/zh/research-toolkit/index.html")
    return items


def test_toolkit_menu_sits_between_research_and_projects_and_matches_the_zh_table():
    """One Research Toolkit menu with short functional labels; the EN menu in _quarto.yml and TOOLKIT_ITEMS must
    list the same pages, or zh pages keep English items."""
    import yaml
    cfg = yaml.safe_load((SITE / "_quarto.yml").read_text(encoding="utf-8"))
    left = cfg["website"]["navbar"]["left"]
    texts = [i["text"] for i in left]
    assert texts.index("Research Toolkit") == texts.index("Research") + 1 == texts.index("Projects") - 1
    menu = next(i for i in left if i["text"] == "Research Toolkit")["menu"]
    links = [m for m in menu if isinstance(m, dict) and "href" in m]
    hrefs = [m["href"].replace(".qmd", ".html") for m in links]
    expected = _toolkit_expected()
    assert sorted(hrefs) == sorted(expected) == sorted(zh_labels.TOOLKIT_ITEMS)
    assert hrefs[-1] == "research-toolkit/index.html"            # the overview closes the menu, as "All research"
    for m, href in zip(links, hrefs):
        en, zh, zh_href = expected[href]
        assert en in m["text"]
        assert zh in zh_labels.TOOLKIT_ITEMS[href][1] and zh_labels.TOOLKIT_ITEMS[href][0] == zh_href
    assert zh_labels.NAV_LABELS["Research Toolkit"] == "研究工具"
    # Existing tool URLs stay where they were (the navbar adds entries, it moves no page).
    for href in hrefs:
        assert (SITE / href.replace(".html", ".qmd")).exists()
        assert (SITE / "zh" / href.replace(".html", ".qmd")).exists()


def test_rewrite_gives_the_toolkit_menu_chinese_labels_and_zh_hrefs():
    items = "".join(
        f'<li><a class="dropdown-item" href="../../{href}">\n <span class="dropdown-text">{en}</span></a></li>\n'
        for href, (en, _zh, _zh_href) in _toolkit_expected().items())
    page = ('<html><body><ul class="navbar-nav"><li class="nav-item dropdown">'
            '<a class="nav-link dropdown-toggle" href="#" id="nav-menu-research-toolkit" role="link" '
            'data-bs-toggle="dropdown" aria-expanded="false"><span class="menu-text">Research Toolkit</span></a>'
            '<ul class="dropdown-menu" aria-labelledby="nav-menu-research-toolkit">' + items + "</ul></li></ul></body></html>")
    out = zh_labels.rewrite(page)
    assert '<span class="menu-text">研究工具</span>' in out and ">Research Toolkit<" not in out
    for href, (en, zh, zh_href) in _toolkit_expected().items():
        assert f'href="{zh_href}"' in out and zh in out
        assert f'href="../../{href}"' not in out
    assert "Toolkit Overview" not in out
    assert zh_labels.rewrite(out) == out


def test_toolkit_items_separate_name_and_description_for_screen_readers():
    """A visually hidden colon between a tool's name and its one-line description (":" EN, "：" ZH), so a screen
    reader announces "name: description" rather than one run-on phrase."""
    import yaml
    cfg = yaml.safe_load((SITE / "_quarto.yml").read_text(encoding="utf-8"))
    menu = next(i for i in cfg["website"]["navbar"]["left"] if i["text"] == "Research Toolkit")["menu"]
    tools = [m for m in menu if isinstance(m, dict) and "rq-tool" in m.get("text", "")]
    assert len(tools) == len(_toolkit_expected()) - 1                   # every tool; the overview is plain text
    for m in tools:
        en = _toolkit_expected()[m["href"].replace(".qmd", ".html")][0]
        assert f'<span class="q">{en}</span><span class="visually-hidden">:</span> <span class="do">' in m["text"]
        _zh_href, zh_html = zh_labels.TOOLKIT_ITEMS[m["href"].replace(".qmd", ".html")]
        zh = _toolkit_expected()[m["href"].replace(".qmd", ".html")][1]
        assert f'<span class="q">{zh}</span><span class="visually-hidden">：</span><span class="do">' in zh_html


def _toolkit_nav(zh: bool) -> str:
    """Navbar fragment as Quarto writes it (EN: relative hrefs) or after rewrite() (ZH: /zh/ hrefs)."""
    items = "".join(
        f'<li><a class="dropdown-item" href="{zh_href if zh else "../" + href}">\n'
        f' <span class="dropdown-text">{zh_label if zh else en}</span></a></li>\n'
        for href, (en, zh_label, zh_href) in _toolkit_expected().items())
    projects = "/zh/projects/index.html" if zh else "../projects/index.html"
    return ('<ul class="navbar-nav"><li class="nav-item dropdown">'
            '<a class="nav-link dropdown-toggle" href="#" id="nav-menu-research-toolkit" role="link" '
            'data-bs-toggle="dropdown" aria-expanded="false">'
            f'<span class="menu-text">{"研究工具" if zh else "Research Toolkit"}</span></a>'
            '<ul class="dropdown-menu" aria-labelledby="nav-menu-research-toolkit">\n' + items + "</ul></li>"
            f'<li class="nav-item"><a class="nav-link" href="{projects}">'
            f'<span class="menu-text">{"项目" if zh else "Projects"}</span></a></li></ul>')


def _items_marked(html):
    return re.findall(r'<a class="dropdown-item[^"]*\bactive\b[^"]*" href="([^"]*)"[^>]*aria-current="([^"]*)"', html)


def test_mark_active_puts_tool_pages_in_the_toolkit_not_in_projects():
    """On a tool page (its URL sits under /projects/) and on the overview, EN and ZH: the Research Toolkit toggle
    is current (aria-current="true"), the page's own item is aria-current="page", and Projects is not marked."""
    for href, (_en, _zh, zh_href) in _toolkit_expected().items():
        for zh, page, item_href in ((False, "/" + href, "../" + href), (True, zh_href, zh_href)):
            out = zh_labels.mark_active(_toolkit_nav(zh), page)
            assert _active(out) == [("#", "true")], (page, _active(out))   # the toggle only; Projects unmarked
            assert 'id="nav-menu-research-toolkit"' in re.search(r'<a class="nav-link dropdown-toggle active"[^>]*>', out).group(0)
            assert _items_marked(out) == [(item_href, "page")], page
            assert zh_labels.mark_active(out, page) == out                 # idempotent
    # Any other project page keeps Projects as its section, and the Toolkit stays unmarked.
    for zh, page, projects in ((False, "/projects/naipca-toolkit.html", "../projects/index.html"),
                               (True, "/zh/projects/naipca-toolkit.html", "/zh/projects/index.html")):
        out = zh_labels.mark_active(_toolkit_nav(zh), page)
        assert _active(out) == [(projects, "true")] and _items_marked(out) == []
    assert zh_labels.menu_sections()["nav-menu-research-toolkit"] >= {"/research-toolkit/", "/zh/research-toolkit/"}
