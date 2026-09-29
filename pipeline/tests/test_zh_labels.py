"""tools/zh_labels.py — post-render Chinese navbar/footer labels (spec "Bilingual mechanism")."""
import importlib.util
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[2] / "site"
SPEC = importlib.util.spec_from_file_location("zh_labels", SITE / "tools" / "zh_labels.py")
zh_labels = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(zh_labels)

NAV = """<ul class="navbar-nav">
<li class="nav-item"><a class="nav-link" href="../research/index.html"><span class="menu-text">Research</span></a></li>
<li class="nav-item"><a class="nav-link" href="../data-code.html"><span class="menu-text">Data &amp; Code</span></a></li>
<li class="nav-item"><a class="nav-link" href="../cv.html"><span class="menu-text">CV</span></a></li>
<li class="nav-item"><a class="nav-link" href="../software.html"><span class="menu-text">Software</span></a></li>
<li class="nav-item"><a class="nav-link" href="../photography/index.html"><span class="menu-text">Photography</span></a></li>
<li class="nav-item"><a class="nav-link" href="../zh/"><span class="menu-text">中文</span></a></li>
</ul>"""
FOOTER = """<footer class="footer"><div class="nav-footer">
<div class="nav-footer-left"><p>© 2026 Mingyang Liu</p></div>
<div class="nav-footer-right"><p>Built with Quarto · <a href="../privacy.html">Privacy</a> · Exhibit data are generated from the author’s research materials; see each figure’s provenance line. · Campus photographs courtesy of the University of Michigan, Columbia University and Imperial College London.</p></div>
</div></footer>"""
PAGE = "<html><body>" + NAV + "<main>Privacy is not a label here. Built with Quarto? Research</main>" + FOOTER + "</body></html>"


def test_rewrite_translates_the_eight_labels_and_the_footer_sentence():
    out = zh_labels.rewrite(PAGE)
    for zh in ("研究", "数据与代码", "简历", "软件", "摄影", "English"):
        assert f'<span class="menu-text">{zh}</span>' in out
    for en in ("Research", "Data &amp; Code", "CV", "Software", "Photography", "中文"):
        assert f'<span class="menu-text">{en}</span>' not in out
    assert '<a href="/zh/privacy.html">隐私</a>' in out
    # The top-level Data & Code item opens the Chinese page on zh pages.
    assert 'href="/zh/data-code.html"><span class="menu-text">数据与代码</span>' in out
    assert "../data-code.html" not in out
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


def test_rewrite_uses_full_width_parentheses_for_the_licence_link():
    html = '<div>x<a rel="license" href="https://creativecommons.org/licenses/by/4.0/">(查看许可协议)</a></div>'
    assert "（查看许可协议）" in zh_labels.rewrite(html)


MENU = """<li class="nav-item dropdown">
<a class="nav-link dropdown-toggle" href="#" id="nav-menu-research" role="link" data-bs-toggle="dropdown" aria-expanded="false"><span class="menu-text">Research</span></a>
<ul class="dropdown-menu" aria-labelledby="nav-menu-research">
<li class="dropdown-header">Five questions, each with a live example</li>
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
    menu = next(i for i in cfg["website"]["navbar"]["left"] if isinstance(i, dict) and "menu" in i)["menu"]
    hrefs = sorted(m["href"].replace(".qmd", ".html") for m in menu if isinstance(m, dict) and "href" in m)
    assert hrefs == sorted(zh_labels.MENU_ITEMS)
    assert [m["text"] for m in menu if isinstance(m, dict) and "href" not in m] == list(zh_labels.MENU_HEADERS)
