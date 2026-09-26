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
