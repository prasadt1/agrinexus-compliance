# AgriNexus Compliance (MVP demo)

Decision-support **demo** for 2026 ESA pesticide-**label** mitigation execution + follow-through receipt.

**Not legal advice. Not certified applicator software.** Labels control; Strategies are frameworks.  
**Verify** means comparing what the applicator reports against the plan this system issued — not legal clearance.

**Current demo pack:** Liberty ULTRA · **EPA Reg. No. 7969-500** · ISU Ag Engineering/Agronomy Research Farm, Boone County, IA (Iowa State ICM Table 1 practices) · Bulletins Live! Two printable for **September 2026** (no extra PULA limits in that map view).

NIW / product intent: [`SETTLED.md`](../../NIW-evidence-pack/SETTLED.md) · [`BUILD-MVP.md`](../../NIW-evidence-pack/BUILD-MVP.md) · [`BUILD-ITEM-1-CASE-LADDER.md`](../../NIW-evidence-pack/BUILD-ITEM-1-CASE-LADDER.md)

## Quick start

```bash
cd ~/projects/agrinexus-compliance
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python scripts/demo_reset.py          # clear cases + seed the Boone ladder cohort
python -m src.cli plan
python -m src.cli plan --windy

uvicorn src.api:app --reload --port 8000
# http://127.0.0.1:8000 — partner board first; “Take the tour” anytime
# Screenshots: append ?capture=1 so the sticky header is not stitched twice
```

Demo clock (EventBridge stand-in — code/README only, never in UI copy):

```bash
curl -X POST http://127.0.0.1:8000/api/demo/clock -H 'Content-Type: application/json' \
  -d '{"advance_hours": 24}'
```

## Accountability ladder

Statuses: `PLANNED` → `NUDGED` (24 h / 48 h) → `CONFIRMED` → `VERIFIED` | `NEEDS_REVIEW` → `CLOSED`  
Also: `BLOCKED` (weather/points at plan), `EXPIRED` (no reply by 72 h).

Reminders anchor on **planned spray date at 18:00 America/Chicago** (else `created_at`).  
Checklist confirmation verifies offline; free-text stays `CONFIRMED` until the model layer is on.

## Verification rules (deterministic)

Against the issued plan:

- Applied and bulletin saved
- Weather: `weather_respected` or reported wind ≤ label `max_wind_mph`
- Every credited **practice** confirmed (menu `confirmation: practice`); **attributes** need no confirmation
- No contradictions; `needs_human` false; free-text confidence ≥ 0.6

Otherwise `NEEDS_REVIEW` with a per-item table for the partner and the receipt.

## Honesty split

| Deterministic (rules) | Model (optional Bedrock) |
|-----------------------|--------------------------|
| Point arithmetic over mitigation menu | Reading label/bulletin language |
| Wind / precip spray gate (15 mph for 7969-500) | Reasons for recommended practices |
| Scheduler reminders + expiry | Interpreting free-text confirmation |
| Checklist → verify against plan | — |
| Receipt SHA-256 over JSON (hash field absent) | — |

## Fixture provenance

| Fixture | Source | Date |
|---------|--------|------|
| `fixtures/labels/7969-500.*` + `sources/7969-500-epa-label-20241206.pdf` | [EPA PPLS label PDF](https://www3.epa.gov/pesticides/chem_search/ppls/007969-00500-20241206.pdf) (Liberty ULTRA ABN) | **2026-08-23** |
| `fixtures/labels/sources/264-1241-stryax-epa-label-20260206.pdf` + `264-1241.json` | [EPA Stryax label](https://www3.epa.gov/pesticides/chem_search/ppls/000264-01241-20260206.pdf); wind **3–10 mph**; Illinois soybean cutoff **June 20**; pack `mchenry_stryax_pula` | **2026-08-23** / corrected **2026-09-17** |
| `fixtures/mitigation_menu.json` + `fields/field_boone.json` | [Iowa State ICM Table 1](https://crops.extension.iastate.edu/post/prepare-now-2026-epa-endangered-species-requirements) (Anderson, 11 Mar 2026) citing [EPA Mitigation Menu](https://www.epa.gov/endangered-species/mitigation-menu); field pin at ISU Ag Engineering/Agronomy Research Farm, Boone (`42.019052, -93.774039`); September framed as post-harvest burndown / fallow | **2026-09-13** (coords) / **2026-08-23** (menu) |
| `fixtures/fields/field_mchenry_twin_creeks.json` | Contrast field at `42.39536, -88.40846` (Greenwood Township, McHenry County, IL); irrigated; 3 pts vs PULA total 6 | **2026-09-17** |
| `fixtures/fields/field_dupage_west_chicago.json` | **Superseded** prairie-vicinity contrast field | **2026-09-17** |
| `fixtures/bulletins/blt-boone-ia-7969-500-2026-09.pdf` + `.json` | Real Bulletins Live! Two Printable Bulletin — farm coords + **September 2026** + **7969-500**; no extra PULA in map view (230th St / U Ave). June/July were no longer offered by BLT at print time. | Printed **2026-09-13** |
| `fixtures/bulletins/blt-mchenry-il-264-1241-2026-09.pdf` + `.json` | Real BLT Printable Bulletin — McHenry / Twin Creeks + **September 2026** + **264-1241**; **DC125** = +3 (total 6); MD5 `dbdc9ae47595600465ba28b1a5d8ab7e` | Printed **2026-09-17** |
| `fixtures/bulletins/blt-dupage-il-264-1241-2026-09.pdf` + `.json` | **Superseded** DuPage / West Chicago Prairie print — kept for provenance | Printed **2026-09-17** |
| `fixtures/bulletins/blt-boone-ia-7969-500-2026-08.pdf` + `.json` | **Superseded** town-center print — kept for provenance | Printed **2026-08-23** |

## Layout

```
fixtures/     Liberty Ultra pack + BLT farm printable
src/          points, weather, planner, verify, scheduler, clock, cases, receipt, api
web/          Partner board → Plan → Confirm → Receipt
scripts/      demo_reset.py
tests/        offline ladder + verification + copy guards
```
