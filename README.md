# AgriNexus Compliance (MVP demo)

Decision-support **demo** for 2026 ESA pesticide-**label** mitigation execution + follow-through receipt.

**Not legal advice. Not certified applicator software.** Labels control; Strategies are frameworks. Current fixtures use educational stubs (`DEMO-000001`) — replace with a real label excerpt and Bulletins Live! Two printable before any outreach demo or video.

NIW / product intent: [`SETTLED.md`](../../NIW-evidence-pack/SETTLED.md) · [`BUILD-MVP.md`](../../NIW-evidence-pack/BUILD-MVP.md)

## Quick start

```bash
cd ~/projects/agrinexus-compliance
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Deterministic points + weather (no AWS needed) — default is offline
python -m src.cli plan

# Windy fixture → weather_ok=false / WEATHER_BLOCK
python -m src.cli plan --windy

# With Bedrock enrichment (needs AWS creds + model access)
export AWS_REGION=us-east-1
export COMPLIANCE_BEDROCK_MODEL=anthropic.claude-3-haiku-20240307-v1:0
python -m src.cli plan --bedrock

# Free-text confirmation (offline stub interpreter)
python -m src.cli interpret "Printed bulletin, kept grassed waterway, sprayed at 7am"

# Web UI (Plan → Confirm → Receipt) — one process
uvicorn src.api:app --reload --port 8000
# open http://127.0.0.1:8000
```

## Honesty split

| Deterministic (`points.py`, `weather.py`, case scheduling) | Model (`planner.py` Bedrock layer, `interpreter.py`) |
|-------------------------------------------|----------------------------------------|
| Point arithmetic over mitigation menu | Reading label/bulletin language |
| Wind / precip spray gate | Reasons for recommended practices |
| Case status + simulated T+24/T+48 reminders | Interpreting free-text confirmation |

UI shows **blue** = deterministic, **green** = model. Never present rule-based logic as AI.

## Fixture provenance

| Fixture | Source / note | Date |
|---------|---------------|------|
| `fixtures/mitigation_menu.json` | Educational stub modeled on [EPA Mitigation Menu](https://www.epa.gov/endangered-species/mitigation-menu) + [Iowa State ICM](https://crops.extension.iastate.edu/post/prepare-now-2026-epa-endangered-species-requirements); point values illustrative | `retrieved_approx`: **2026-08-16** |
| `fixtures/labels/DEMO-000001.*` | **Stub** — not a real EPA Reg. No. Structure paraphrased from public extension guidance | 2026-08-16 |
| `fixtures/bulletins/blt-boone-ia-demo-2026-04.json` | **Stub** — replace with printable from [Bulletins Live! Two](https://www.epa.gov/endangered-species/bulletins-live-two-view-bulletins) | 2026-08-16 |
| `fixtures/fields/field_boone.json` | Demo field style aligned with Iowa State ICM public examples | 2026-08-16 |

## Week 0 leftovers (before outreach / video)

Do **not** send Iowa State (or any extension specialist) a demo still running `DEMO-000001`. Before recording:

1. Download one real product label (EPA Reg. No. cited in Iowa State ICM or equivalent) → replace `fixtures/labels/`.
2. Download one real Bulletins Live! Two printable PDF for Boone (or chosen county) + month + that Reg. No. → `fixtures/bulletins/` (PDF allowed in git under that path).
3. Update `required_points`, wind limits, and menu points to match the label / EPA menu retrieval — record new `retrieved_approx` dates in JSON + this README.

Build plumbing on stubs; swap fixtures before the outreach artifact.

## Layout

```
fixtures/     menu, field, label stub, bulletin stub
src/          points, weather, planner, interpreter, cases, receipt, api, cli
web/          Plan → Confirm → Receipt (static + FastAPI)
tests/        offline unit tests
data/         local JSONL case store (gitignored)
receipts/     generated PDF/JSON (gitignored)
```

## Definition of done (demo path)

- [x] Three screens with honesty split + disclaimer
- [x] Simulate T+24 / T+48 reminder changes status and appears on receipt
- [x] Receipt PDF + JSON download
- [ ] Real label + BLT PDF fixtures (Week 0 leftover)
- [ ] Live URL or recorded 3-minute video
- [ ] Outreach one-pager: problem → 3 screenshots → offer of a free single-crop, single-county, single-season evaluation pilot → contact
