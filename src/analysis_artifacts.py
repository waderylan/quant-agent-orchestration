"""Content-addressed analysis ledgers, CSV tables, code, and Matplotlib PNG charts."""

from __future__ import annotations

import csv
import io
import json
import os
import re
import threading
from decimal import Decimal
from pathlib import Path

from src.source_collection import ROOT, digest, now, write_json

_plot_lock = threading.Lock()


def chart_data(calculations):
    groups = {}
    for row in calculations:
        scale = Decimal(1000000) if row["unit"] == "USD" else Decimal(1)
        groups.setdefault((row["metric"], row["unit"]), []).append(
            {
                "source_id": row["source_id"],
                "label": row["label"].replace(
                    " " + row["metric"].replace("_", " "), ""
                ),
                "value": str(Decimal(row["value"]) / scale),
                "scale": str(scale),
            }
        )
    if len(groups) > 8:
        raise ValueError("At most eight metric groups per chart; narrow the analysis")
    return [
        {"metric": metric, "unit": unit, "rows": rows}
        for (metric, unit), rows in groups.items()
    ]


def render_chart(series):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from matplotlib import rc_context

    with _plot_lock, rc_context({"text.parse_math": False}):
        figure = Figure(figsize=(10, max(3.2, 2.6 * len(series))), layout="constrained")
        FigureCanvasAgg(figure)
        axes = figure.subplots(len(series), 1, squeeze=False)
        for axis, group in zip(axes.flat, series):
            labels = [r["label"] for r in group["rows"]]
            values = [float(Decimal(r["value"])) for r in group["rows"]]
            bars = axis.barh(labels, values, color="#174a8b")
            axis.bar_label(
                bars,
                labels=[f"{Decimal(r['value']):,.2f}" for r in group["rows"]],
                padding=3,
            )
            axis.margins(x=0.2)
            axis.axvline(0, color="#444444", linewidth=0.7)
            axis.invert_yaxis()
            axis.set_title(group["metric"].replace("_", " ").title())
            axis.set_xlabel(
                "USD millions"
                if group["unit"] == "USD"
                else group["unit"].replace("_", " ")
            )
        output = io.BytesIO()
        figure.savefig(output, format="png", dpi=120)
        figure.clear()
        return output.getvalue()


class ArtifactStore:
    def __init__(self, path=None):
        self.path = Path(
            path or os.getenv("QUANT_ARTIFACT_DIR", ROOT / "artifacts/quant")
        ).resolve()

    def publish(self, code, calculations, sources):
        series = chart_data(calculations)
        table = io.StringIO(newline="")
        fields = [
            "source_id",
            "label",
            "company",
            "fiscal_year",
            "period",
            "basis",
            "start",
            "end",
            "metric",
            "value",
            "unit",
            "formula",
            "inputs",
            "source_ids",
        ]
        writer = csv.DictWriter(table, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in calculations:
            writer.writerow(
                {
                    **row,
                    "inputs": " ".join(row["inputs"]),
                    "source_ids": " ".join(row["source_ids"]),
                }
            )
        files = {
            "table.csv": table.getvalue().encode(),
            "chart.png": render_chart(series),
            "analysis.py": code.encode(),
        }
        bundle = {
            "schema_version": 1,
            "created_at": now(),
            "code": code,
            "calculations": calculations,
            "sources": sources,
            "chart_series": series,
            "files": {name: digest(body) for name, body in files.items()},
        }
        identity = digest(json.dumps(bundle, sort_keys=True).encode())
        folder = self.path / identity
        folder.mkdir(parents=True, exist_ok=True)
        for name, body in files.items():
            (folder / name).write_bytes(body)
        write_json(
            folder / "bundle.json", bundle
        )  # Publication marker is written last.
        return identity, bundle

    def load(self, identity):
        if not re.fullmatch(r"[0-9a-f]{64}", identity):
            raise KeyError("Invalid analysis artifact identifier")
        folder = self.path / identity
        if not folder.resolve().is_relative_to(self.path):
            raise ValueError("Analysis artifact path escapes its directory")
        bundle = json.loads((folder / "bundle.json").read_text(encoding="utf-8"))
        if digest(json.dumps(bundle, sort_keys=True).encode()) != identity:
            raise ValueError("Analysis ledger checksum mismatch")
        return bundle

    def file(self, identity, name):
        bundle = self.load(identity)
        if name == "bundle.json":
            return self.path / identity / name
        if (
            name not in {"table.csv", "chart.png", "analysis.py"}
            or name not in bundle["files"]
        ):
            raise KeyError("Unknown analysis artifact")
        path = self.path / identity / name
        if digest(path.read_bytes()) != bundle["files"][name]:
            raise ValueError("Analysis artifact checksum mismatch")
        return path

    def calculation(self, identity, sid):
        bundle = self.load(identity)
        row = next((r for r in bundle["calculations"] if r["source_id"] == sid), None)
        if row is None:
            raise KeyError("Unknown calculation identifier")
        inputs = {
            **{
                sid: self.observation_source(identity, source)
                for sid, source in bundle["sources"].items()
            },
            **{
                r["source_id"]: self.source(identity, r) for r in bundle["calculations"]
            },
        }
        return {
            **row,
            "input_sources": [inputs[s] for s in row["inputs"]],
            "bundle_id": identity,
        }

    @staticmethod
    def observation_source(identity, source):
        return {
            **source,
            "inspection_url": f"/api/analysis/{identity}/observations/{source['source_id']}",
            "original_url": f"/api/originals/{source['document_id']}",
            "snapshot_url": f"/api/analysis/{identity}/snapshots/{source['snapshot_sha256']}",
        }

    @staticmethod
    def source(identity, row):
        return {
            **row,
            "bundle_id": identity,
            "inspection_url": f"/api/analysis/{identity}/calculations/{row['source_id']}",
            "text": f"{row['label']}: {row['value']} {row['unit']}; {row['formula']}",
        }

    @staticmethod
    def downloads(identity):
        return [
            {"name": name, "url": f"/api/analysis/{identity}/files/{file}"}
            for name, file in [
                ("CSV table", "table.csv"),
                ("PNG chart", "chart.png"),
                ("Analysis code", "analysis.py"),
                ("Calculation ledger", "bundle.json"),
            ]
        ]
