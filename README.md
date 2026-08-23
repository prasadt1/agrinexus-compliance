# AgriNexus Compliance (MVP demo)

Decision-support **demo** for 2026 ESA pesticide-**label** mitigation execution + follow-through receipt.

**Not legal advice. Not certified applicator software.** Labels control; Strategies are frameworks.

**Current demo pack:** Liberty ULTRA · **EPA Reg. No. 7969-500** · Boone County, IA (Iowa State ICM Table 1 field) · Bulletins Live! Two printable for **August 2026** (no extra PULA limits in that map view).

NIW / product intent: [`SETTLED.md`](../../NIW-evidence-pack/SETTLED.md) · [`BUILD-MVP.md`](../../NIW-evidence-pack/BUILD-MVP.md)

## Quick start

```bash
cd ~/projects/agrinexus-compliance
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m src.cli plan
python -m src.cli plan --windy
python -m src.cli interpret "Saved the Boone bulletin, kept grassed waterway, sprayed at 7am under 6 mph"

uvicorn src.api:app --reload --port 8000
# http://127.0.0.1:8000 — first visit auto-starts a guided tour (desktop); “Take the tour” anytime
```

## Honesty split

| Deterministic | Model (optional Bedrock) |
|---------------|--------------------------|
| Point arithmetic over mitigation menu | Reading label/bulletin language |
| Wind / precip spray gate (label max wind 15 mph for 7969-500) | Reasons for recommended practices |
| Case status + simulated reminders | Interpreting free-text confirmation |

## Fixture provenance

| Fixture | Source | Date |
|---------|--------|------|
| `fixtures/labels/7969-500.*` + `sources/7969-500-epa-label-20241206.pdf` | [EPA PPLS label PDF](https://www3.epa.gov/pesticides/chem_search/ppls/007969-00500-20241206.pdf) (Liberty ULTRA ABN) | **2026-08-23** |
| `fixtures/labels/sources/264-1241-stryax-epa-label-20260206.pdf` | [EPA Stryax label](https://www3.epa.gov/pesticides/chem_search/ppls/000264-01241-20260206.pdf) (BLT example in Iowa State article; not wired as default) | **2026-08-23** |
| `fixtures/mitigation_menu.json` + `fields/field_boone.json` | [Iowa State ICM Table 1](https://crops.extension.iastate.edu/post/prepare-now-2026-epa-endangered-species-requirements) (Anderson, 11 Mar 2026) citing [EPA Mitigation Menu](https://www.epa.gov/endangered-species/mitigation-menu) | **2026-08-23** |
| `fixtures/bulletins/blt-boone-ia-7969-500-2026-08.pdf` + `.json` | Real Bulletins Live! Two Printable Bulletin for Boone coords + **August 2026** + **7969-500**; no extra PULA limits in map view | Printed **2026-08-23** |

## Remaining Week 0 leftover

Done for the Liberty Ultra / Boone pack: real label PDF + real BLT printable (Aug 2026). Optional next: wire Stryax **264-1241** as a second product for a BLT-heavy contrast case.

## Layout

```
fixtures/     real Liberty Ultra pack + pending BLT PDF
src/          points, weather, planner, interpreter, cases, receipt, api, cli
web/          Check → Confirm → Record
tests/
```
