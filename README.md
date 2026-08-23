# AgriNexus Compliance (MVP scaffold)

Decision-support **demo** for 2026 ESA pesticide-**label** mitigation execution + follow-through receipt.

**Not legal advice. Not certified applicator software.** Labels control; Strategies are frameworks. Fixtures are educational stubs — replace with your own Bulletins Live! Two printout and label excerpts before any real use.

NIW / product intent: [`SETTLED.md`](../../NIW-evidence-pack/SETTLED.md) · [`BUILD-MVP.md`](../../NIW-evidence-pack/BUILD-MVP.md)

## Quick start

```bash
cd ~/projects/agrinexus-compliance
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Deterministic points + weather (no AWS needed)
python -m src.cli plan --offline

# With Bedrock (needs AWS creds + model access)
export AWS_REGION=us-east-1
export COMPLIANCE_BEDROCK_MODEL=anthropic.claude-3-haiku-20240307-v1:0
python -m src.cli plan
```

## Honesty split

| Deterministic (`points.py`, `weather.py`) | Model (`planner.py`, `interpreter.py`) |
|-------------------------------------------|----------------------------------------|
| Point arithmetic over mitigation menu | Reading label/bulletin language |
| Wind / precip spray gate | Recommending which menu practices close a shortfall |
| Case scheduling (later) | Interpreting free-text confirmation |

## Replace these fixtures (Week 0)

1. Download a real **Bulletins Live! Two** printable for your county + month + EPA Reg. No. → `fixtures/bulletins/`
2. Paste ESA / runoff / drift sections from that product’s label → `fixtures/labels/`
3. Update `required_points` and `epa_reg_no` in the label JSON to match the label (not this stub)

## Layout

```
fixtures/     menu, field, label stub, bulletin stub
src/          points, weather, planner, interpreter, cli
tests/        offline unit tests
web/          (empty — Week 2)
```
