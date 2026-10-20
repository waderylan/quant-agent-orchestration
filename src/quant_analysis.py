"""Independent financial validation of generated arithmetic and calculation lineage."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from src.codex_transport import register_close


class ResultRow(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    label: str = Field(min_length=1, max_length=160)
    kind: Literal[
        "value",
        "growth",
        "margin",
        "share",
        "difference",
        "quarter",
        "ratio",
        "currency",
        "scenario_scale",
        "scenario_total",
        "scenario_share",
    ]
    inputs: list[str] = Field(min_length=1, max_length=2)
    value: str
    used_inputs: list[str] = Field(max_length=64)


def run_isolated(code, sources, *, timeout=3):
    if not isinstance(code, str) or len(code) > 12000:
        raise ValueError("Analysis code must contain at most 12000 characters")
    values = {sid: s["value"] for sid, s in sources.items()}
    payload = json.dumps({"code": code, "values": values})
    if len(payload.encode()) > 262144:
        raise ValueError("Analysis input exceeds 256 KiB")
    environment = {
        k: v
        for k, v in os.environ.items()
        if k.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "LANG"}
    }
    try:
        with subprocess.Popen(
            [
                sys.executable,
                "-I",
                "-S",
                "-B",
                str(Path(__file__).with_name("quant_runner.py")),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=tempfile.gettempdir(),
            env=environment,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        ) as process:

            def close():
                if process.poll() is None:
                    process.kill()

            with register_close(close):
                try:
                    stdout, _ = process.communicate(payload, timeout=timeout)
                except subprocess.TimeoutExpired:
                    close()
                    process.communicate()
                    raise
            returncode = process.returncode
    except subprocess.TimeoutExpired as error:
        raise ValueError("Analysis execution timed out; child terminated") from error
    try:
        output = json.loads(stdout)
    except json.JSONDecodeError as error:
        raise ValueError("Analysis child failed without a valid result") from error
    if returncode or "error" in output:
        raise ValueError(output.get("error", "Analysis child failed"))
    return output["results"]


def compatible_revisions(left, right, sources):
    cutoff = max(left["filed"], right["filed"])
    for sid in set(left["source_ids"] + right["source_ids"]):
        original = sources[sid]
        for record in [original, *original.get("inputs", [])]:
            if any(
                r["filed"] <= cutoff for r in record.get("conflicting_comparatives", [])
            ):
                raise ValueError(
                    "Conflicting comparative revision prevents this calculation"
                )


def comparable(left, right, sources, *, same_interval=False, cumulative=False):
    if left["company"] != right["company"]:
        raise ValueError(
            "Cross-company arithmetic is not a within-company financial comparison"
        )
    if (
        left["revision_basis"] != right["revision_basis"]
        or left["revision_basis"] != "original_report"
    ):
        raise ValueError("Incompatible revision bases")
    if left["accounting_basis"] != right["accounting_basis"]:
        raise ValueError("Incompatible accounting bases")
    compatible_revisions(left, right, sources)
    if same_interval:
        for key in ("start", "end", "basis", "period", "fiscal_year"):
            if left[key] != right[key]:
                raise ValueError(
                    "Numerator and denominator require the same fiscal interval"
                )
    elif (
        (left["basis"] != right["basis"] and not cumulative)
        or left["metric"] != right["metric"]
        or left["unit"] != right["unit"]
        or (
            left["metric"] == "revenue_component"
            and left.get("component") != right.get("component")
        )
    ):
        raise ValueError(
            "Comparison requires matching metrics, units, and period bases"
        )


def validate_results(rows, sources, *, scenario=None):
    """Recompute each result separately; declared lineage must match executed lineage."""
    known = {}
    for sid, source in sources.items():
        if source.get("status") != "available" or source.get("unit") != "USD":
            raise ValueError("Only available USD observations can enter analysis")
        known[sid] = {**source, "source_ids": [sid]}
    verified = []
    if not 1 <= len(rows) <= 64:
        raise ValueError("Analysis needs 1-64 result rows")
    for number, raw in enumerate(rows, 1):
        row = ResultRow.model_validate(raw)
        if any(sid not in known for sid in row.inputs):
            raise ValueError("Calculation references a missing or forward input")
        inputs = [known[sid] for sid in row.inputs]
        if len(inputs) != (
            1 if row.kind in ("value", "currency", "scenario_scale") else 2
        ):
            raise ValueError("Incorrect number of calculation inputs")
        current = inputs[0]
        metadata = {
            k: current[k]
            for k in (
                "company",
                "fiscal_year",
                "period",
                "basis",
                "start",
                "end",
                "fiscal_start",
                "fiscal_end",
                "metric",
                "unit",
                "revision_basis",
                "accounting_basis",
                "filed",
            )
        }
        warnings = sorted({w for s in inputs for w in s.get("warnings", [])})
        if current.get("component"):
            metadata["component"] = current["component"]
        if current.get("scenario"):
            metadata["scenario"] = current["scenario"]
        values = [Decimal(str(s["value"])) for s in inputs]
        if row.kind == "value":
            expected, formula = values[0], row.inputs[0]
        elif row.kind == "ratio":
            numerator, denominator = inputs
            comparable(numerator, denominator, sources, same_interval=True)
            if (
                numerator["metric"] != "operating_cash_flow"
                or denominator["metric"] != "net_income"
                or numerator["unit"] != "USD"
                or denominator["unit"] != "USD"
                or values[1] <= 0
            ):
                raise ValueError(
                    "Cash conversion requires matching operating cash flow and positive parent net income"
                )
            expected = values[0] / values[1]
            formula = f"{row.inputs[0]} / {row.inputs[1]}"
            metadata.update(metric="cash_conversion", unit="multiple")
        elif row.kind in (
            "currency",
            "scenario_scale",
            "scenario_total",
            "scenario_share",
        ):
            if not scenario or scenario.get("origin") != "user":
                raise ValueError(
                    "Scenario calculations require an explicit approved user assumption"
                )
            if row.kind == "currency":
                rate = Decimal(scenario.get("usd_per_eur", "0"))
                if (
                    scenario.get("kind") != "currency"
                    or not 0 < rate <= 1000000
                    or current["unit"] != "USD"
                ):
                    raise ValueError(
                        "Currency conversion requires an approved positive USD-per-EUR rate and reported USD input"
                    )
                expected = values[0] / rate
                formula = f"{row.inputs[0]} / {rate} USD per EUR (user assumption)"
                metadata.update(unit="EUR", metric=current["metric"] + "_scenario_eur")
            else:
                factor = Decimal(scenario.get("factor", "0"))
                component = scenario.get("component")
                if scenario.get("kind") != "component" or not 0 < factor <= 100:
                    raise ValueError(
                        "Component scenario requires an approved bounded multiplier"
                    )
                if row.kind == "scenario_scale":
                    if (
                        current.get("component") != component
                        or current.get("provenance") != "filing_revenue_table"
                        or current["metric"] != "revenue_component"
                    ):
                        raise ValueError(
                            "Scenario numerator requires the verified requested component"
                        )
                    expected, formula = (
                        values[0] * factor,
                        f"{row.inputs[0]} * {factor} (user assumption)",
                    )
                    metadata.update(metric="scenario_" + component + "_revenue")
                elif row.kind == "scenario_total":
                    total, part = inputs
                    comparable(total, part, sources, same_interval=True)
                    if (
                        total["metric"] != "revenue"
                        or part.get("component") != component
                        or part.get("provenance") != "filing_revenue_table"
                        or part["metric"] != "revenue_component"
                        or total.get("accession") != part.get("accession")
                    ):
                        raise ValueError(
                            "Scenario total requires same-filing consolidated revenue and verified component"
                        )
                    expected = values[0] + (factor - 1) * values[1]
                    formula = f"{row.inputs[0]} + ({factor} - 1) * {row.inputs[1]} (user assumption)"
                    metadata.update(metric="scenario_total_revenue")
                else:
                    numerator, denominator = inputs
                    comparable(numerator, denominator, sources, same_interval=True)
                    if (
                        numerator.get("scenario") != scenario
                        or denominator.get("scenario") != scenario
                        or numerator["metric"] != "scenario_" + component + "_revenue"
                        or denominator["metric"] != "scenario_total_revenue"
                        or values[1] <= 0
                        or not 0 <= values[0] <= values[1]
                    ):
                        raise ValueError(
                            "Scenario share requires matching verified hypothetical numerator and total"
                        )
                    expected = values[0] / values[1] * 100
                    formula = f"{row.inputs[0]} / {row.inputs[1]} * 100 (hypothetical)"
                    metadata.update(
                        metric="scenario_" + component + "_share", unit="percent"
                    )
            metadata["scenario"] = scenario
            warnings = sorted(
                set(
                    warnings
                    + [
                        "Hypothetical user assumption; not a reported result or forecast"
                    ]
                )
            )
        elif row.kind == "share":
            numerator, denominator = inputs
            comparable(numerator, denominator, sources, same_interval=True)
            qct_total = numerator["metric"] == "qct_revenue" and numerator.get("component") == "qct_total" and numerator["company"] == "QCOM" and denominator["metric"] == "revenue" and numerator["period"] == "FY" and numerator["basis"] == "annual"
            if (
                (numerator["metric"] != "revenue_component" and not qct_total)
                or numerator.get("provenance") != "filing_revenue_table"
                or numerator.get("parent_metric") != "revenue"
                or numerator.get("parent_scope") != "consolidated"
                or denominator["metric"] not in ("revenue", "qct_revenue")
                or numerator["unit"] != "USD"
                or denominator["unit"] != "USD"
                or numerator.get("accession") != denominator.get("accession")
                or (
                    denominator["metric"] == "qct_revenue"
                    and denominator.get("provenance") != "filing_revenue_table"
                )
            ):
                raise ValueError(
                    "Revenue share requires an established component and same-filing consolidated revenue"
                )
            if values[1] <= 0 or not Decimal(0) <= values[0] <= values[1]:
                raise ValueError(
                    "Revenue share requires a positive total and a nonnegative component no larger than total"
                )
            expected = values[0] / values[1] * 100
            metadata.update(
                unit="percent",
                metric="qct_consolidated_revenue_share" if qct_total else numerator["component"]
                + (
                    "_qct_revenue_share"
                    if denominator["metric"] == "qct_revenue"
                    else "_revenue_share"
                ),
            )
            formula = f"{row.inputs[0]} / {row.inputs[1]} * 100"
        elif row.kind == "margin":
            numerator, denominator = inputs
            comparable(numerator, denominator, sources, same_interval=True)
            if (
                numerator["unit"] != "USD"
                or denominator["unit"] != "USD"
                or denominator["metric"] != "revenue"
                or numerator["metric"] not in ("gross_profit", "operating_income", "net_income")
            ):
                raise ValueError(
                    "Margin requires gross profit, operating income or parent-attributable net income and matching revenue"
                )
            if values[1] <= 0:
                raise ValueError("Margin revenue denominator must be positive")
            expected = values[0] / values[1] * 100
            metadata.update(
                unit="percent",
                metric="gross_margin"
                if numerator["metric"] == "gross_profit"
                else "net_margin" if numerator["metric"] == "net_income" else "operating_margin",
            )
            formula = f"{row.inputs[0]} / {row.inputs[1]} * 100"
        elif row.kind == "quarter":
            previous = inputs[1]
            comparable(current, previous, sources, cumulative=True)
            if (
                current["unit"] != "USD"
                or current["fiscal_year"] != previous["fiscal_year"]
                or current["fiscal_start"] != previous["fiscal_start"]
                or current["start"] != previous["start"]
            ):
                raise ValueError(
                    "Quarter derivation requires the same fiscal year and cumulative start"
                )
            # Annual and YTD are both cumulative inputs; other comparisons cannot mix them.
            if current["basis"] not in ("annual", "ytd") or previous["basis"] != "ytd":
                raise ValueError("Quarter derivation requires cumulative inputs")
            ordinal = {"Q1": 1, "Q2": 2, "Q3": 3, "FY": 4}
            if (
                ordinal.get(current["period"]) != ordinal.get(previous["period"], 0) + 1
                or current["end"] <= previous["end"]
            ):
                raise ValueError(
                    "Quarter derivation requires adjacent cumulative reporting periods"
                )
            expected = values[0] - values[1]
            metadata.update(
                period=f"Q{ordinal[current['period']]}",
                basis="quarter",
                start=(
                    date.fromisoformat(previous["end"]) + timedelta(days=1)
                ).isoformat(),
            )
            formula = f"{row.inputs[0]} - {row.inputs[1]}"
        elif row.kind == "difference" and (current["metric"], inputs[1]["metric"]) == ("operating_cash_flow", "net_income"):
            # Cash generated beyond (or short of) reported earnings for one fiscal interval.
            comparable(current, inputs[1], sources, same_interval=True)
            expected = values[0] - values[1]
            metadata["metric"] = "operating_cash_flow_minus_net_income"
            formula = f"{row.inputs[0]} - {row.inputs[1]}"
        else:
            previous = inputs[1]
            comparable(current, previous, sources)
            if current["start"] <= previous["end"]:
                raise ValueError("Comparison intervals overlap or are reversed")
            durations = [
                (date.fromisoformat(s["end"]) - date.fromisoformat(s["start"])).days + 1
                for s in inputs
            ]
            if abs(durations[0] - durations[1]) > 7:
                raise ValueError(
                    "Comparison intervals have materially different durations"
                )
            if row.kind == "growth":
                if current["unit"] != "USD" or values[1] <= 0:
                    raise ValueError(
                        "Percentage growth requires a positive USD baseline"
                    )
                expected = (values[0] / values[1] - 1) * 100
                metadata.update(unit="percent", metric=current["metric"] + "_growth")
                formula = f"({row.inputs[0]} / {row.inputs[1]} - 1) * 100"
            else:
                expected = values[0] - values[1]
                if current["unit"] == "percent":
                    if current["metric"] not in ("gross_margin", "operating_margin", "net_margin"):
                        raise ValueError(
                            "Percentage-point differences require matching margin metrics"
                        )
                    metadata["unit"] = "percentage_points"
                metadata["metric"] = current["metric"] + "_change"
                formula = f"{row.inputs[0]} - {row.inputs[1]}"
        base_inputs = sorted({sid for source in inputs for sid in source["source_ids"]})
        if set(row.used_inputs) != set(base_inputs):
            raise ValueError("Executed arithmetic lineage differs from declared inputs")
        try:
            actual = Decimal(row.value)
        except InvalidOperation as error:
            raise ValueError("Calculation value must be a decimal number") from error
        tolerance = (
            Decimal("1e-8")
            if metadata["unit"] in ("percent", "percentage_points", "multiple", "EUR")
            else Decimal(0)
        )
        if not actual.is_finite() or abs(actual - expected) > tolerance:
            raise ValueError(
                "Generated calculation differs from independent recomputation"
            )
        sid = f"C{number}"
        period_label = "" if metadata["period"] == "FY" else " " + metadata["period"]
        metric_label = (
            (current["component"] + " revenue")
            if metadata["metric"] == "revenue_component"
            else metadata["metric"].replace("_", " ")
        )
        if current.get("component") and metadata["metric"].startswith(
            "revenue_component_"
        ):
            metric_label = (
                metadata["metric"]
                .replace("revenue_component", current["component"] + "_revenue")
                .replace("_", " ")
            )
        label = f"{metadata['company']} FY{metadata['fiscal_year']}{period_label} {metric_label}"
        if any(s.get("evidence_kind", "").startswith("synthetic") for s in inputs):
            label += " (synthetic fixture)"
        if row.kind in ("growth", "difference") and inputs[1]["metric"] == current["metric"]:
            prior_period = (
                "" if inputs[1]["period"] == "FY" else " " + inputs[1]["period"]
            )
            label += f" vs FY{inputs[1]['fiscal_year']}{prior_period}"
        verified_row = {
            **metadata,
            "kind": "calculation",
            "calculation_kind": row.kind,
            "source_id": sid,
            "label": label,
            "requested_label": row.label,
            "inputs": row.inputs,
            "source_ids": base_inputs,
            "formula": formula,
            "value": str(expected),
            "display_value": f"{expected:,.4f}" if tolerance else f"{expected:,.0f}",
            "warnings": warnings,
        }
        known[sid] = verified_row
        verified.append(verified_row)
    return verified
