"""tools/check_links.py rule (g) — duplicate OJS cell names (spec D22, "Error handling")."""
import base64
import importlib.util
import json
from pathlib import Path

SITE = Path(__file__).resolve().parents[2] / "site"
SPEC = importlib.util.spec_from_file_location("check_links", SITE / "tools" / "check_links.py")
check_links = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_links)


def page_with(*sources: str) -> str:
    module = {"contents": [{"methodName": "interpret", "cellName": f"ojs-cell-{i}", "inline": "False", "source": s}
                           for i, s in enumerate(sources, 1)]}
    blob = base64.b64encode(json.dumps(module).encode()).decode()
    return f'<html><body><script type="ojs-module-contents">\n{blob}\n</script></body></html>'


def test_definitions_cover_plain_viewof_and_mutable_but_not_indented_or_comparisons():
    src = ('palette = ({\n  band: "x"\n})\n'
           'viewof pf_view = Inputs.radio([1, 2], { label: t("view") })\n'
           'mutable pf_state = 0\n'
           'pf_chart = {\n  const color = 1\n  if (pf_view === 2) return html``\n  return color\n}\n'
           'pf_ok = (a) => a == 1\n'
           'Plot.plot({ marks: [] })\n')
    assert check_links.ojs_definitions(src) == ["palette", "pf_view", "pf_state", "pf_chart", "pf_ok"]


def test_duplicate_cells_reports_names_defined_twice_across_cells():
    html = page_with('pf_data = FileAttachment("/data/a.json").json()',
                     'viewof pf_view = Inputs.radio([1])',
                     'pf_data = 3\nviewof pf_view = Inputs.radio([2])\ngeo_chart = 1')
    assert check_links.duplicate_cells(html) == {"pf_data": 2, "pf_view": 2}


def test_unique_cells_and_pages_without_ojs_pass():
    assert check_links.duplicate_cells(page_with("pf_a = 1", "geo_b = 2")) == {}
    assert check_links.duplicate_cells("<html><body><p>no figures</p></body></html>") == {}


def test_helpers_and_figure_includes_define_distinct_names():
    """The shipped includes, concatenated as a page would include them, have no duplicate cell names."""
    import re
    files = [SITE / "_includes/_exhibit-helpers.qmd", SITE / "_includes/_fig-portfolio-formation.qmd",
             SITE / "research/_fig-rolling-geometry.qmd"]
    cells = []
    for f in files:
        cells += re.findall(r"```\{ojs\}\n//\| echo: false\n(.*?)\n```", f.read_text(encoding="utf-8"), re.S)
    assert check_links.duplicate_cells(page_with(*cells)) == {}
    names = [n for c in cells for n in check_links.ojs_definitions(c)]
    for f, prefix in ((files[1], "pf_"), (files[2], "geo_")):
        own = [n for c in re.findall(r"```\{ojs\}\n//\| echo: false\n(.*?)\n```", f.read_text(encoding="utf-8"), re.S)
               for n in check_links.ojs_definitions(c)]
        assert own and all(n.startswith(prefix) for n in own), (f.name, own)
    assert len(names) == len(set(names))


# --------------------------------------------------------------------------- rules (a)-(k), site checks

FIG_OK = ('<div id="figure-x" class="column-page dfigure"><div class="dfigure-title"><strong>Figure 1</strong></div>'
          '<p>body</p><div class="figcaption">Read it. <span class="provenance">Source: research release '
          '2026-09-09</span></div></div>')


def test_rule_f_and_j_accept_a_complete_figure_unit():
    assert check_links.dfigure_problems(check_links.parse(f"<main>{FIG_OK}</main>")) == []


def test_rule_f_and_j_report_missing_title_caption_and_provenance():
    no_title = '<div id="a" class="dfigure"><div class="figcaption"><span class="provenance">manuscript</span></div></div>'
    no_cap = '<div id="b" class="dfigure"><div class="dfigure-title">T</div><p>x</p></div>'
    no_prov = '<div id="c" class="dfigure"><div class="dfigure-title">T</div><div class="figcaption">Only words.</div></div>'
    vague = ('<div id="d" class="dfigure"><div class="dfigure-title">T</div>'
             '<div class="figcaption"><span class="provenance">Source: somewhere</span></div></div>')
    msgs = check_links.dfigure_problems(check_links.parse(no_title + no_cap + no_prov + vague))
    assert msgs == ["DFIGURE .dfigure a has no .dfigure-title",
                    "DFIGURE .dfigure b has no .figcaption",
                    "PROVENANCE .dfigure c .figcaption 1 has no span.provenance",
                    "PROVENANCE .dfigure d .figcaption 1 provenance names no manuscript or release"]


def test_tree_builder_handles_void_elements_and_stray_end_tags():
    root = check_links.parse('<div class="dfigure"><img src="a.png"><br><div class="dfigure-title">T</div></p>'
                             '<div class="figcaption"><span class="provenance">working paper</span></div></div>')
    assert check_links.dfigure_problems(root) == []


def test_rule_k_img_without_alt_and_rule_e_city_band():
    root = check_links.parse('<img src="/a.png" alt=""><img src="/b.png"><div class="city-band x"></div>')
    assert check_links.imgs_without_alt(root) == ["/b.png"]
    assert check_links.city_band_count(root) == 1
    P = check_links.Path
    assert check_links.city_band_allowed(P("photography/london.html"))
    assert check_links.city_band_allowed(P("zh/photography/index.html"))
    assert not check_links.city_band_allowed(P("index.html"))
    assert not check_links.city_band_allowed(P("zh/index.html"))


def test_downloads_expand_vars_and_drop_what_paperhead_drops():
    meta = {"downloads": [{"label": "Paper (PDF)", "href": "/assets/pdfs/p.pdf"},
                          {"label": "Appendix", "href": "{{< var appendix >}}"},
                          {"label": "Code", "href": "{{< var unknown_key >}}"},
                          {"label": "Site", "href": "{{< var site >}}"},
                          {"text": "Replication: available on request"}]}
    assert check_links.download_entries(meta, {"appendix": "", "site": "/x.html"}) == [
        ("Paper (PDF)", "/assets/pdfs/p.pdf"), ("Site", "/x.html")]


def test_rule_h_byline(tmp_path):
    pdf = tmp_path / "p.pdf"
    meta = {"author": [{"name": "Mingyang Liu"}], "byline_ok": "2026-09-27"}
    ok = lambda p: "Title\nMingyang\nLiu*\nImperial Business School"      # noqa: E731 (split across lines)
    other = lambda p: "Title\nA. Coauthor\nImperial Business School"       # noqa: E731
    assert check_links.byline_problems("research/x.qmd", meta, [("Paper (PDF)", pdf)], ok) == []
    assert check_links.byline_problems("research/x.qmd", meta, [("Paper (PDF)", pdf)], other) == [
        "BYLINE research/x.qmd: 'Mingyang Liu' not on page 1 of p.pdf (Paper (PDF))"]
    no_ok = {"author": meta["author"]}
    assert any("byline_ok" in m for m in check_links.byline_problems("research/x.qmd", no_ok, [("Slides", pdf)], ok))
    assert check_links.byline_problems("research/thesis.qmd", no_ok, [], ok) == []   # no PDF -> no byline_ok needed


def test_rule_h_fails_when_pdftotext_is_missing(tmp_path):
    def missing(p):
        raise FileNotFoundError("pdftotext not found")
    msgs = check_links.byline_problems("research/x.qmd", {"author": ["Mingyang Liu"], "byline_ok": 1},
                                       [("Slides (PDF)", tmp_path / "s.pdf")], missing)
    assert msgs and "cannot read page 1" in msgs[0]


def test_rule_i_appledouble(tmp_path):
    (tmp_path / "a.html").write_text("x")
    (tmp_path / "._a.html").write_bytes(b"\x00\x05\x16\x07rest")            # OS companion
    (tmp_path / "._orphan.png").write_bytes(b"\x00\x05\x16\x07rest")        # no sibling
    (tmp_path / "b.png").write_text("x")
    (tmp_path / "._b.png").write_bytes(b"not appledouble")                   # copied junk
    fails, tolerated = check_links.appledouble_problems(tmp_path, platform="darwin")
    assert tolerated == 1 and sorted(fails) == ["APPLEDOUBLE ._b.png is in _site", "APPLEDOUBLE ._orphan.png is in _site"]
    fails, tolerated = check_links.appledouble_problems(tmp_path, platform="linux")
    assert tolerated == 0 and len(fails) == 3


def _mini_project(tmp_path):
    proj, site = tmp_path / "site", tmp_path / "site" / "_site"
    (site / "research").mkdir(parents=True)
    (site / "zh").mkdir()
    (proj / "_variables.yml").write_text('appendix: ""\n')
    (site / "index.html").write_text('<html><body><img src="/x.png" alt="x"><a href="research/p.html">p</a></body></html>')
    (site / "x.png").write_bytes(b"png")
    (site / "research" / "p.html").write_text("<html><body>p</body></html>")
    (proj / "index.qmd").write_text("---\ntitle: Home\ntranslation: /zh/index.html\n"
                                    "downloads:\n  - {label: Paper, href: /research/p.html}\n"
                                    "  - {label: Appendix, href: \"{{< var appendix >}}\"}\n---\n\nHi\n")
    return proj, site


def test_whole_check_passes_a_clean_project_and_reports_each_source_rule(tmp_path):
    proj, site = _mini_project(tmp_path)
    (site / "zh" / "index.html").write_text("<html><body>zh</body></html>")
    fails, n, _ = check_links.check(proj, site)
    assert fails == [] and n == 3
    (site / "zh" / "index.html").unlink()                                              # (c)
    (proj / "gallery.qmd").write_text("---\ntitle: G\nlightbox: false\n---\n{{< gallery london >}}\n")   # (b)
    (site / "gallery.html").write_text("<html><body></body></html>")
    (proj / "_includes").mkdir()
    (proj / "_includes" / "_f.qmd").write_text('x = FileAttachment("../data/a.json")\n')       # (d)
    (proj / "bad.qmd").write_text("---\ntitle: B\ndownloads:\n  - {label: Slides, href: /assets/missing.pdf}\n---\n")  # (a)
    (site / "bad.html").write_text("<html><body></body></html>")
    fails, _, _ = check_links.check(proj, site)
    kinds = sorted(f.split(" ", 1)[0] for f in fails)
    assert kinds == ["DOWNLOAD", "GALLERY", "INCLUDE-PATH", "TRANSLATION"], fails



def test_rule_l_private_ref(tmp_path, monkeypatch, capsys):
    """Rule (l) PRIVATE-REF: invented fixtures only (no real private repository name or address)."""
    proj, site = _mini_project(tmp_path)
    (site / "zh" / "index.html").write_text("<html><body>zh</body></html>")
    # passing page: the site's own repository and the public contact address
    (site / "index.html").write_text('<html><body><img src="/x.png" alt="x"><a href="research/p.html">p</a>'
                                     '<a href="https://github.com/yl7919/yl7919.github.io">site</a> '
                                     'yang.liu19@imperial.ac.uk</body></html>')
    fails, n, _ = check_links.check(proj, site)
    assert fails == [] and n == 3
    # the summary line, as main() prints it on the clean mini project
    orig = check_links.check
    monkeypatch.setattr(check_links, "SITE", site)
    monkeypatch.setattr(check_links, "check", lambda: orig(proj, site))
    assert check_links.main() == 0
    assert capsys.readouterr().out.splitlines()[0].endswith("0 broken references, 0 rule (a)-(l) failures")
    # failing page: another yl7919 repository, an ic.ac.uk login alias, an outlook.com address (all invented)
    (site / "research" / "p.html").write_text('<html><body><a href="https://github.com/yl7919/private-repo">x</a> '
                                             'abc123@ic.ac.uk and someone@outlook.com</body></html>')
    fails, _, _ = orig(proj, site)
    assert fails == ["PRIVATE-REF research/p.html: github.com/yl7919/private-repo",
                     "PRIVATE-REF research/p.html: abc123@ic.ac.uk",
                     "PRIVATE-REF research/p.html: someone@outlook.com"]
