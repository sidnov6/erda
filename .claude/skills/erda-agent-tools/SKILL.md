---
name: erda-agent-tools
description: How to add a typed tool to the LangGraph feasibility committee — typed fn, schema, source_ids, graph registration, memo field mapping. Use whenever touching packages/agents or packages/engine interfaces.
---

# ERDA Agent Tools — the add-a-tool recipe

Spec references: §10 (committee), §10.3 (tool law), §0 rule 3 (LLM narrates, code calculates). Read those sections before adding or modifying any tool.

## 1. Tool law

Non-negotiable rules. Violating any of these is a bug, not a style choice.

- **LLM narrates, code calculates.** No model call ever performs arithmetic, unit conversion, or NPV math. Agents call typed tools; tools return numbers; the memo template interpolates them.
- **Every tool is a typed Python function over local DuckDB/Zarr.** No live internet at memo time. A memo re-run on the same snapshot must be byte-identical — that is the reproducibility contract.
- **Every tool return includes `source_ids`.** No exceptions, including derived values.
- **The memo schema requires `source_ids` on every quantitative field.** The coverage checker computes cited-fields/total-fields.
- **The Chair rejects memos with citation coverage < 0.9.** A tool that returns uncited numbers will sink the memo at synthesis.

## 2. Recipe — adding a tool

1. **Write a pure typed function** in `packages/agents/tools/`. Define pydantic input and output models. No I/O beyond local DuckDB/Zarr reads; no network; no LLM calls inside the tool.
2. **Output model carries values + units + `source_ids`.** Every quantitative field is a (value, unit) pair with its citing `source_ids`. A bare float is a bug.
3. **Register the tool in the LangGraph graph** (`packages/agents/`): bind it to the owning agent node per the committee map below.
4. **Map outputs to memo schema fields** in `packages/agents/memo_schema.py`. Every field the tool feeds must declare its `source_ids` so the coverage checker can count it.
5. **Unit test on the frozen fixture snapshot.** Tests run against the frozen test fixtures (§11) — never live data.
6. **Determinism check.** Same snapshot in → same output out. Add a test asserting repeated calls on the fixture snapshot produce identical results.

## 3. Committee map

Condensed from §10.1/§10.2. Agents run in parallel under the Orchestrator, except Economist, RedTeam, Chair which follow.

| Agent | Tools | Memo section |
|-------|-------|--------------|
| Geoscience | `get_model_score`, `get_offset_wells`, `get_basin_stats` | Model score + uncertainty, offset wells within 100 km, creaming-curve position, analogs |
| Fiscal | `get_fiscal_regime` | Regime type, royalty/CIT/PSC split, licensing-round status |
| PoliticalRisk | `get_governance`, `screen_sanctions` | WGI percentile, FSI, sanctions screen, licence-security notes |
| Infrastructure | `classify_dev_concept` | Water depth, distance to infra, development concept (§10.4) |
| Environment | `get_protected_overlap` | WDPA overlap % (block + 25 km buffer), named protected areas |
| Financeability | `screen_financing` | Which capital pools could plausibly fund |
| Economist | calls `packages/engine` — the ONLY path to numbers | NPV, EMV, breakeven, government take, Monte Carlo distribution |
| RedTeam | attacks the draft | Required section: "What would make this wrong" |
| Chair | renders memo, enforces citation coverage | Verdict + memo JSON → MD/PDF; rejects if coverage < 0.9 |

## 4. Deterministic boundary

The economics engine (`packages/engine/`) is import-pure, seeded, test-first. It performs all computation: DCF, EMV, Monte Carlo, fiscal take. Agents assemble inputs and report outputs — they never compute. If a tool needs a number derived from other numbers, that derivation lives in typed code (tool or engine), never in a prompt.

## 5. Verdict rule (§10.6)

GO / CONDITIONAL / NO-GO is decided by deterministic thresholds on EMV, P(EMV>0), sanctions flag, and WDPA overlap. The LLM words the verdict; the rules decide it. Never let an agent or the Chair override the threshold outcome in prose.
