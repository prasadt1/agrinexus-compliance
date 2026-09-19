"""Every factual UI/PDF claim about retention or documentation points must resolve to a fixture."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.cases import CaseStore
from src.planner import plan
from src.receipt import build_receipt_payload, write_receipt_pdf


# Uncited legal-sounding retention, or the rescinded federal RUP rule as authority.
BANNED_RETENTION_CLAIMS = [
    re.compile(r"Kept for two years(?!\s*\(demo)", re.I),
    re.compile(r"label already requires you to keep application records", re.I),
    re.compile(r"7 CFR\s*§?\s*110\.3", re.I),
    re.compile(r"7 CFR Part 110", re.I),
]


def test_no_hardcoded_false_retention_authorities_in_web_or_receipt_src():
    offenders: list[str] = []
    for path in [
        *(ROOT / "web").rglob("*.html"),
        *(ROOT / "web").rglob("*.js"),
        ROOT / "src" / "receipt.py",
    ]:
        text = path.read_text(encoding="utf-8")
        for pat in BANNED_RETENTION_CLAIMS:
            if pat.search(text):
                # Allow explicit "rescinded" historical notes only in comments/docs — not in these paths.
                offenders.append(
                    f"{path.relative_to(ROOT)}: matches {pat.pattern!r}"
                )
    assert not offenders, "false or uncited retention claims:\n" + "\n".join(offenders)


def test_stryax_retention_is_demo_policy_with_label_deferral_context():
    result = plan(offline=True, pack="mchenry_stryax_pula")
    product = result["product"]
    assert product["record_retention_years"] == 2
    retention = product["record_retention"]
    assert retention["authority"] == "demonstration retention policy"
    assert "7 CFR" not in (retention.get("authority") or "")
    assert "applicable federal and state record keeping requirements" in (
        retention.get("label_context_quote") or ""
    )
    doc = product["documentation_mitigation_point"]
    assert doc["value"] == 1
    assert "ONE point" in doc["source_quote"]
    assert "creation and keeping" in doc["source_quote"]


def test_liberty_keeps_demo_retention_omits_documentation_point():
    result = plan(offline=True, pack="boone_liberty")
    product = result["product"]
    assert product["record_retention_years"] == 2
    assert product["record_retention"]["authority"] == "demonstration retention policy"
    assert product["record_retention"].get("label_context_quote") is None
    assert product["documentation_mitigation_point"] is None


def test_receipt_payload_and_pdf_follow_fixture_per_product(tmp_path):
    store = CaseStore(path=tmp_path / "cases.jsonl")

    stryax = store.create(
        plan(offline=True, pack="mchenry_stryax_pula"),
        planned_spray_date="2026-09-18",
    )
    s_payload = build_receipt_payload(stryax)
    assert s_payload["product"]["record_retention"]["authority"] == (
        "demonstration retention policy"
    )
    assert s_payload["product"]["documentation_mitigation_point"]["value"] == 1
    s_pdf = write_receipt_pdf(stryax, out_dir=tmp_path)
    assert s_pdf.exists() and s_pdf.stat().st_size > 500

    liberty = store.create(
        plan(offline=True, pack="boone_liberty"),
        planned_spray_date="2026-09-18",
    )
    l_payload = build_receipt_payload(liberty)
    assert l_payload["product"]["record_retention_years"] == 2
    assert l_payload["product"]["documentation_mitigation_point"] is None
