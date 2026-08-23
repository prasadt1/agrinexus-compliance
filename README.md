# AgriNexus Compliance (MVP demo)

Decision-support **demo** for 2026 ESA pesticide-**label** mitigation execution + follow-through receipt.

**Not legal advice. Not certified applicator software.** Labels control; Strategies are frameworks.

**Current demo pack:** Liberty ULTRA · **EPA Reg. No. 7969-500** · Boone County, IA (Iowa State ICM Table 1 field). Bulletins Live! Two printable PDF for that county/month/Reg. No. is still a **manual download** (see `fixtures/bulletins/README.md`).

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
# http://127.0.0.1:8000
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
| `fixtures/bulletins/blt-boone-ia-7969-500-2026-04.json` | Actions paraphrased from label §12; **printable BLT PDF still pending your download** | **2026-08-23** |

## Remaining Week 0 leftover

1. Download BLT Printable Bulletin: Boone County, IA + application month + **7969-500** → save PDF under `fixtures/bulletins/`.  
2. Set `bulletin_pdf` / `pula_active` in the bulletin JSON from that printout.  

Optional: wire Stryax **264-1241** as a second product for the BLT-heavy story.

## Layout

```
fixtures/     real Liberty Ultra pack + pending BLT PDF
src/          points, weather, planner, interpreter, cases, receipt, api, cli
web/          Check → Confirm → Record
tests/
```
