"""Quant-owned valuation arithmetic, independent gates, frozen replay, and lineage."""

from __future__ import annotations

from decimal import Decimal

from src.analysis_artifacts import ArtifactStore
from src.market_evidence import ValuationInput, number
from src.quant_analysis import run_isolated


def compatible(inputs, *, flow=False):
    if (
        len({i.company for i in inputs}) != 1
        or len({i.currency for i in inputs}) != 1
        or inputs[0].currency != "USD"
    ):
        raise ValueError("Valuation requires same-company USD inputs")
    if any(i.freshness != "dated" for i in inputs):
        raise ValueError("Stale/undated inputs excluded from valuation")
    fundamentals = [
        i for i in inputs if i.source_kind not in ("quote", "user_assumption")
    ]
    if any(
        i.accounting_basis == "unspecified"
        or i.dilution == "unspecified"
        or i.split_basis == "unspecified"
        or not i.end
        or not i.as_of
        for i in fundamentals
    ):
        raise ValueError("Missing accounting, dilution, split, period, or as-of basis")
    if len({i.accounting_basis for i in fundamentals}) > 1:
        raise ValueError("Incompatible GAAP/adjusted accounting bases")
    if (
        fundamentals
        and len({i.split_basis for i in inputs if i.source_kind != "user_assumption"})
        > 1
    ):
        raise ValueError("Unreconciled split bases")
    flows = [i for i in fundamentals if i.metric in ("eps", "revenue", "ebitda", "fcf")]
    if flow and (
        len({(i.start, i.end, i.horizon) for i in flows}) != 1
        or any(not i.start for i in flows)
    ):
        raise ValueError("Flow periods/definitions are incompatible")


def formula(kind, inputs):
    """Independent financial recomputation. No generation result is trusted."""
    compatible(inputs, flow=kind == "fcf_yield")
    vals = [number(i.value) for i in inputs]
    metrics = [i.metric for i in inputs]
    if kind in ("pe", "forward_pe"):
        if (
            metrics != ["price", "eps"]
            or vals[1] <= 0
            or inputs[1].dilution != "diluted"
        ):
            raise ValueError("P/E requires positive diluted EPS")
        if kind == "forward_pe" and (
            inputs[1].source_kind != "consensus" or not inputs[1].horizon
        ):
            raise ValueError("Forward P/E requires an explicit consensus horizon")
        return vals[0] / vals[1], "multiple", "price / positive diluted EPS"
    if kind in ("ev_revenue", "ev_ebitda"):
        denominator = "revenue" if kind == "ev_revenue" else "ebitda"
        if (
            metrics != ["price", "shares", "debt", "cash", denominator]
            or vals[-1] <= 0
            or vals[1] <= 0
            or vals[2] < 0
            or vals[3] < 0
        ):
            raise ValueError(
                "EV multiple requires price, shares, debt, cash, and positive denominator"
            )
        if len({i.end for i in inputs[1:4]}) != 1:
            raise ValueError("EV share/cash/debt dates do not match")
        if inputs[-1].horizon not in ("TTM", "annual"):
            raise ValueError("EV denominator needs a defined TTM/annual interval")
        return (
            (vals[0] * vals[1] + vals[2] - vals[3]) / vals[4],
            "multiple",
            "(price * shares + total debt - cash and cash equivalents) / "
            + denominator,
        )
    if kind == "fcf_yield":
        if (
            metrics != ["fcf", "price", "shares"]
            or vals[1] <= 0
            or vals[2] <= 0
            or vals[0] <= 0
        ):
            raise ValueError(
                "FCF yield requires positive operating cash flow less capex and compatible market cap"
            )
        return (
            vals[0] / (vals[1] * vals[2]) * 100,
            "percent",
            "(operating cash flow - capital expenditures) / (price * shares) * 100",
        )
    if kind == "implied_price":
        if metrics != ["eps", "multiple"] or min(vals) <= 0:
            raise ValueError(
                "Scenario requires positive EPS and an explicit positive multiple"
            )
        if inputs[1].source_kind != "user_assumption":
            raise ValueError("Scenario multiple must be an explicit assumption")
        return vals[0] * vals[1], "USD/share", "assumed EPS * assumed P/E"
    if kind == "scenario_return":
        if metrics != ["eps", "multiple", "price"] or min(vals) <= 0:
            raise ValueError(
                "Scenario return requires positive EPS, assumed multiple, and comparison price"
            )
        if inputs[1].source_kind != "user_assumption":
            raise ValueError("Scenario multiple must be an explicit assumption")
        return (
            (vals[0] * vals[1] / vals[2] - 1) * 100,
            "percent",
            "(assumed EPS * assumed P/E / dated comparison price - 1) * 100",
        )
    raise ValueError("Unsupported valuation formula")


def calculate(specs, sources, *, artifacts=None, calculation_offset=0):
    if not 1 <= len(specs) <= 24:
        raise ValueError("Valuation calculation count must be 1–24")
    parsed = {
        sid: ValuationInput.model_validate(
            {k: v for k, v in source.items() if k in ValuationInput.model_fields}
        )
        for sid, source in sources.items()
    }
    results, program_rows, expected = [], [], []
    for n, spec in enumerate(specs):
        if (
            set(spec) - {"kind", "inputs", "label", "horizon"}
            or not isinstance(spec.get("label"), str)
            or not 1 <= len(spec["label"]) <= 160
        ):
            raise ValueError("Invalid bounded valuation specification")
        ids = spec["inputs"]
        if (
            not isinstance(ids, list)
            or not 1 <= len(ids) <= 5
            or len(set(ids)) != len(ids)
        ):
            raise ValueError("Valuation requires one to five distinct input IDs")
        selected = [parsed[sid] for sid in ids]
        target, unit, definition = formula(spec["kind"], selected)
        value_expr = [f"values[{sid!r}]" for sid in ids]
        if spec["kind"] in ("pe", "forward_pe"):
            expression = f"{value_expr[0]} / {value_expr[1]}"
        elif spec["kind"] in ("ev_revenue", "ev_ebitda"):
            expression = f"({value_expr[0]} * {value_expr[1]} + {value_expr[2]} - {value_expr[3]}) / {value_expr[4]}"
        elif spec["kind"] == "fcf_yield":
            expression = f"{value_expr[0]} / ({value_expr[1]} * {value_expr[2]}) * 100"
        elif spec["kind"] == "implied_price":
            expression = f"{value_expr[0]} * {value_expr[1]}"
        else:
            expression = (
                f"({value_expr[0]} * {value_expr[1]} / {value_expr[2]} - 1) * 100"
            )
        program_rows.append(
            "{'label':"
            + repr(spec["label"])
            + ",'kind':'value','inputs':"
            + repr(ids)
            + ",'value':"
            + expression
            + "}"
        )
        expected.append(target)
        primary = selected[0]
        results.append(
            {
                "kind": "calculation",
                "source_id": f"C{calculation_offset + n + 1}",
                "label": spec["label"],
                "company": primary.company,
                "fiscal_year": int((primary.end or "0000")[:4]),
                "period": primary.horizon or "12-month scenario",
                "basis": "conditional scenario"
                if spec["kind"] in ("implied_price", "scenario_return")
                else "source-defined valuation",
                "start": primary.start,
                "end": primary.end,
                "metric": spec["kind"],
                "calculation_kind": spec["kind"],
                "value": str(target),
                "unit": unit,
                "formula": definition,
                "inputs": ids,
                "source_ids": ids,
                "horizon": spec.get("horizon", "12 months"),
                "assumptions": [
                    s.model_dump()
                    for s in selected
                    if s.source_kind == "user_assumption"
                ],
            }
        )
    code = "results=[" + ",".join(program_rows) + "]"
    executed = run_isolated(code, sources)
    for row, expected_value, spec in zip(executed, expected, specs):
        if abs(number(row["value"]) - expected_value) > Decimal("1e-8") or set(
            row["used_inputs"]
        ) != set(spec["inputs"]):
            raise ValueError("Valuation execution/recomputation or lineage differs")
    store = artifacts or ArtifactStore()
    for row in results:
        row["display_value"] = f"{Decimal(row['value']):,.4f}"
    identity, _ = store.publish(
        code,
        results,
        sources,
        assessment={
            "validator": "valuation-v1",
            "definitions": "EV=equity value + total debt - cash equivalents; FCF=operating cash flow - capex; EBITDA must be source-defined",
            "specs": specs,
        },
    )
    return {
        "bundle_id": identity,
        "calculations": results,
        "sources": {
            **{
                sid: store.observation_source(identity, s) for sid, s in sources.items()
            },
            **{r["source_id"]: store.source(identity, r) for r in results},
        },
        "artifacts": {
            "bundle_id": identity,
            "chart_url": f"/api/analysis/{identity}/files/chart.png",
            "downloads": store.downloads(identity),
            "calculations": [store.source(identity, r) for r in results],
        },
    }


def replay(bundle):
    if bundle.get("assessment", {}).get("validator") != "valuation-v1":
        raise ValueError("Not a valuation bundle")
    specs, sources = bundle["assessment"]["specs"], bundle["sources"]
    executed = run_isolated(bundle["code"], sources)
    if len(executed) != len(specs) or len(bundle["calculations"]) != len(specs):
        raise ValueError("Valuation replay result count differs")
    for spec, row, stored in zip(specs, executed, bundle["calculations"]):
        selected = [
            ValuationInput.model_validate(
                {
                    k: v
                    for k, v in sources[sid].items()
                    if k in ValuationInput.model_fields
                }
            )
            for sid in spec["inputs"]
        ]
        value, _, _ = formula(spec["kind"], selected)
        if (
            abs(number(row["value"]) - value) > Decimal("1e-8")
            or abs(number(stored["value"]) - value) > Decimal("1e-8")
            or set(row["used_inputs"]) != set(spec["inputs"])
        ):
            raise ValueError("Valuation replay calculation or lineage differs")
    return {"verified": True, "calculations": len(executed)}
