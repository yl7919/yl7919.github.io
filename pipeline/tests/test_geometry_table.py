"""Table 1 of the geometry page: generated from the portfolio_formation payload (spec "Research pages", paper 2)."""
import json
from pathlib import Path

from exhibits import portfolio_formation as pf

WEB = Path(__file__).resolve().parents[2]
SHIPPED_JSON = WEB / "site" / "data" / "portfolio_formation.json"
SHIPPED_MD = WEB / "site" / "research" / "_tbl-geometry-performance.md"


def _payload() -> dict:
    return json.loads(SHIPPED_JSON.read_text(encoding="utf-8"))


def test_table_rows_and_values_follow_the_cross_model_table():
    payload = _payload()
    md = pf.table_markdown(payload)
    rows = [r for r in payload["cross_model"]["table"]]
    assert md.count("<tr>") == len(rows) + 1                    # header + one row per investable model
    for r in rows:
        assert f"<td>{r['label']}</td>" in md
        assert f'<td class="num">{r["gross_sharpe"]:.2f}</td>' in md
    assert '<td class="num">−34.6</td>' in md               # IPCA drawdown keeps its own minus sign
    assert "PCA: excluded" in md and "DEGENERATE_NEAR_ZERO_GROSS" in md


def test_table_wording_follows_the_page_design():
    md = pf.table_markdown(_payload())
    assert "Proxy-adjusted Sharpe (10 bp)" in md and "Proxy-adjusted Sharpe (50 bp)" in md
    assert "Zero-mean threshold (proxy, bp)" in md
    assert "Net Sharpe" not in md and "Break-even" not in md and "break-even" not in md
    assert 'class="provenance"' in md and "Research_Release_2026-09-09" in md


def test_shipped_include_matches_shipped_json():
    assert SHIPPED_MD.read_text(encoding="utf-8") == pf.table_markdown(_payload())


def test_beyond_range_sentinel_is_keyed_on_the_threshold_column_and_notes_list_every_excluded_model():
    assert pf._cell("break_even_cost_bp", float("nan"), "{:.0f}") == "> 500"
    assert pf._cell("max_drawdown_pct", float("nan"), "{:.0f}") == "n/a"   # same format, different column
    assert pf._cell("gross_sharpe", None, "{:.2f}") == "n/a"
    payload = _payload()
    payload["cross_model"]["models"].append(
        {"id": "x", "label": "XYZ", "status": "NOT_RUN", "risk_matrix": "no risk matrix"})
    md = pf.table_markdown(payload)
    assert 'PCA: excluded; the release records it as "DEGENERATE_NEAR_ZERO_GROSS"' in md
    assert 'XYZ: excluded; the release records it as "NOT_RUN" (no risk matrix).' in md


def test_release_strings_are_html_escaped_in_the_generated_include():
    payload = _payload()
    payload["cross_model"]["table"][0]["label"] = "A<B & \"C\""
    payload["cross_model"]["models"].append(
        {"id": "x", "label": "<X>", "status": "NOT<RUN", "risk_matrix": "S & V'"})
    payload["meta"]["source_files"][0] = "a<b>.csv"
    payload["meta"]["source_release"] = "Rel&ease"
    md = pf.table_markdown(payload)
    assert '<td>A&lt;B &amp; "C"</td>' in md and "<td>A<B" not in md   # text nodes: quotes stay literal
    assert '&lt;X&gt;: excluded; the release records it as "NOT&lt;RUN" (S &amp; V\').' in md
    assert "<code>a&lt;b&gt;.csv</code>" in md and "research release Rel&amp;ease" in md
    assert "<X>" not in md and "<b>" not in md
