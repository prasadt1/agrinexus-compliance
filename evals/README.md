# Evaluation set (Item 3)

Status: **scaffolding for commit 1 of BUILD-ITEM-3**. No live Bedrock runs published yet.

## Label identity

| Product | EPA Reg. No. | Label PDF stamp | Excerpt |
|---|---|---|---|
| Stryax Herbicide | 264-1241 | **2026/02/06** (Page n of 44) | `fixtures/labels/264-1241.md` |
| Liberty ULTRA | 7969-500 | **20241206** | `fixtures/labels/7969-500.md` (quotes still incomplete; see gate memo) |

Expected values (draft): `evals/264-1241.expected.json` — **Prasad verifies every `source_quote` against the PDF page** before this file is treated as the hand-built answer key. A Claude-drafted key must not silently grade a Claude Bedrock model.

## Schema rule: PULA points

- Score **`pula_total_points_inside_pula` = 6** from the label sentence *“SIX runoff/erosion mitigation points are required inside specific PULAs…”*
- **`pula_extra_points`** is **null** on label-only input (the model must not compute 6−3).
- When **bulletin** text is supplied, score **`pula_extra_points` = 3** from DC125 (*“3 ADDITIONAL points (for a total of 6 points)”*). Planner arithmetic may still add baseline + bulletin extra at runtime.

## Excerpt normalization

`264-1241.md` is NFKC-normalized. Ligatures are folded. The known pdftotext wind artifact (`between 310 mph`) is corrected to `between 3-10 mph` in the excerpt. **Scorer quote checks use the excerpt file only**, not raw PDF bytes.

## Scorer traps (do not publish a misleading accuracy number)

1. **Verbatim match against the normalized excerpt**, not the PDF text stream.
2. **Expected JSON is hand-built** — never copy derived planner fields (`pula_extra_points: 3`) into label-only expected.
3. **List fields** (`other_restrictions`, state blocks): publish (a) citation-validity / invented-restriction rate and (b) recall against must-find sentences — separately from scalar field accuracy.
4. **Null agreement is separate** from accuracy on non-null expected fields (all-null models must not look strong).
5. **Word numbers**: THREE → 3 and SIX → 6 are accepted without calling that “computing.”
6. **Record label stamp and page** in every published run README.
7. **Ten runs at temperature 0** measure run-to-run stability, not a confidence interval on reading quality.

## UI honesty (when the AI column ships)

Column header: **“AI reading (not used for this plan)”**. Plan numbers stay on the hand-verified fixture. See `reviews/GATE-item3-cowork-2026-09-18.md` §A4.

## Next

1. Prasad PDF page-check of `264-1241.expected.json`.
2. Liberty expected.json with the same discipline.
3. Offline mocked Bedrock tests; live eval runs only with credentials, skipped otherwise.
