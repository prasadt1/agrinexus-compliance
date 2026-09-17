# Bulletins Live! Two fixtures

## Active demo packs

### Boone / Liberty ULTRA (no PULA)
- **PDF:** `blt-boone-ia-7969-500-2026-09.pdf`
- **JSON:** `blt-boone-ia-7969-500-2026-09.json`
- Location: `42.019052, -93.774039` — ISU Ag Engineering/Agronomy Research Farm, Boone County, IA
- Month: **September 2026** (framed as post-harvest burndown / fallow in the field fixture)
- Product: **7969-500** (Liberty ULTRA)
- Result: **no extra PULA limitations** in the printed map view (beyond the label)
- Printed: **2026-09-13**

### McHenry / Stryax (PULA + Illinois cutoff — Item 2)
- **PDF:** `blt-mchenry-il-264-1241-2026-09.pdf` (source download: `bulletin-10.pdf`)
- **JSON:** `blt-mchenry-il-264-1241-2026-09.json`
- Location: `42.39536, -88.40846` — open parcel near Twin Creeks Rd, Greenwood Township, McHenry County, IL (Google Maps match to printed map roads; not an exact BLT click export)
- Month: **September 2026**
- Product: **264-1241** (STRYAX HERBICIDE)
- Result: **PULA active** — code **DC125**: 3 ADDITIONAL runoff/erosion points (total 6); planner also applies Illinois label cutoff (no dicamba on soybean after June 20) so September returns `LABEL_DATE_BLOCK` while still showing the points card
- MD5: `dbdc9ae47595600465ba28b1a5d8ab7e` · PDF creation `D:20260918001044+02'00'` · Date Printed `2026-09-17T23:49:26`
- Planner pack id: `mchenry_stryax_pula` (alias `dupage_stryax_pula` still resolves here)

## Superseded prints (kept for provenance)
- `blt-boone-ia-7969-500-2026-08.pdf` + `.json` — August 2026 print at Boone **town center**. Superseded for farmland map view.
- `blt-dupage-il-264-1241-2026-09.pdf` + `.json` — early Item 2 print at West Chicago Prairie vicinity. Superseded: label-illicit story for the click point / preserve adjacency; replaced by McHenry cropland print (`bulletin-10`).

Transcribe bulletin JSON from Printed Bulletin PDFs only. Do not invent PULA language. Record MD5 and PDF creation timestamp alongside Date Printed (Date Printed text alone does not uniquely identify a print).
