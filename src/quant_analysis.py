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
    kind: Literal["value", "growth", "margin", "difference", "quarter"]
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
    ):
        raise ValueError(
            "Comparison requires matching metrics, units, and period bases"
        )


def validate_results(rows, sources):
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
        if len(inputs) != (1 if row.kind == "value" else 2):
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
        values = [Decimal(str(s["value"])) for s in inputs]
        if row.kind == "value":
            expected, formula = values[0], row.inputs[0]
        elif row.kind == "margin":
            numerator, denominator = inputs
            comparable(numerator, denominator, sources, same_interval=True)
            if (
                numerator["unit"] != "USD"
                or denominator["unit"] != "USD"
                or denominator["metric"] != "revenue"
                or numerator["metric"] not in ("gross_profit", "operating_income")
            ):
                raise ValueError(
                    "Margin requires gross profit/operating income and matching revenue"
                )
            if values[1] <= 0:
                raise ValueError("Margin revenue denominator must be positive")
            expected = values[0] / values[1] * 100
            metadata.update(
                unit="percent",
                metric="gross_margin"
                if numerator["metric"] == "gross_profit"
                else "operating_margin",
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
                    if current["metric"] not in ("gross_margin", "operating_margin"):
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
            if metadata["unit"] in ("percent", "percentage_points")
            else Decimal(0)
        )
        if not actual.is_finite() or abs(actual - expected) > tolerance:
            raise ValueError(
                "Generated calculation differs from independent recomputation"
            )
        sid = f"C{number}"
        period_label = "" if metadata["period"] == "FY" else " " + metadata["period"]
        label = f"{metadata['company']} FY{metadata['fiscal_year']}{period_label} {metadata['metric'].replace('_', ' ')}"
        if row.kind in ("growth", "difference"):
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
