# Bulletins Live! Two fixtures

## Done
- Label for **Liberty ULTRA / EPA Reg. No. 7969-500** is in `fixtures/labels/` (official EPA PDF + excerpt).

## You still download (interactive map — cannot automate honestly)
1. Open https://www.epa.gov/endangered-species/bulletins-live-two-view-bulletins  
2. Location: **Boone County, Iowa** (or a specific field lat/lon).  
3. Application month: e.g. **April 2026**.  
4. EPA Reg. No.: **7969-500**.  
5. Click **Printable Bulletin** → save PDF here as  
   `blt-boone-ia-7969-500-2026-04.pdf`  
6. Update `blt-boone-ia-7969-500-2026-04.json`: set `bulletin_pdf`, `pula_active`, and any extra bulletin-specific actions.

Optional second product from the same Iowa State article: **Stryax**, EPA Reg. No. **264-1241** (label PDF already saved under `fixtures/labels/sources/`).
