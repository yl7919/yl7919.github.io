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
<li class="nav-item"><a class="nav-link" href="../cv.html"><span class="menu-text">CV</span></a></li>
<li class="nav-item"><a class="nav-link" href="../software.html"><span class="menu-text">Software</span></a></li>
<li class="nav-item"><a class="nav-link" href="../photography/index.html"><span class="menu-text">Photography</span></a></li>
<li class="nav-item"><a class="nav-link" href="../zh/"><span class="menu-text">中文</span></a></li>
</ul>"""
FOOTER = """<footer class="footer"><div class="nav-footer">
<div class="nav-footer-left"><p>© 2026 Mingyang Liu</p></div>
<div class="nav-footer-right"><p>Built with Quarto · <a href="../privacy.html">Privacy</a> · Exhibit data are generated from the author’s research materials; see each figure’s provenance line.</p></div>
</div></footer>"""
PAGE = "<html><body>" + NAV + "<main>Privacy is not a label here. Built with Quarto? Research</main>" + FOOTER + "</body></html>"


def test_rewrite_translates_the_seven_labels_and_the_footer_sentence():
    out = zh_labels.rewrite(PAGE)
    for zh in ("研究", "简历", "软件", "摄影", "English"):
        assert f'<span class="menu-text">{zh}</span>' in out
    for en in ("Research", "CV", "Software", "Photography", "中文"):
        assert f'<span class="menu-text">{en}</span>' not in out
    assert '<a href="../privacy.html">隐私</a>' in out
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
