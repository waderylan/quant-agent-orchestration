"""Source-checked annual revenue components from explicitly supported filing tables.

The model selects a passage, never a value or scale. Table adapters independently
read the immutable prepared filing and bind each number to its header and row.
"""

from __future__ import annotations

import json
import re
from contextlib import aclosing

from src.codex_model import stream as codex_stream
from src.financial_workflow import FinancialTools
from src.source_collection import ROOT, digest

QCT_ROWS = {
    "automotive": "Automotive",
    "handsets": "Handsets",
    "iot": "IoT (internet of things)",
    "qct_total": "Total QCT revenues",
}


def qct_revenue_row(text, year, component):
    """Require a revenue title, explicit USD scale, unique annual headers and row.

    Quarterly releases with repeated year columns, percentages, duplicate matching
    tables, and other tables are deliberately not accepted by this annual adapter.
    """
    if component not in QCT_ROWS:
        raise ValueError("Unsupported revenue component")
    lines = text.splitlines(keepends=True)
    offsets, position = [], 0
    for line in lines:
        offsets.append(position)
        position += len(line)
    found = []
    for title_index, title in enumerate(lines):
        pattern = (
            r"QCT\s+revenue\s+streams\s+were\s+as\s+follows\s*\(in\s+mi\s*llions\)"
        )
        title_start = title_index
        if not re.search(pattern, title, re.I):
            if (
                not title_index
                or not re.match(r"\s*revenue\b", title, re.I)
                or not re.search(pattern, lines[title_index - 1] + title, re.I)
            ):
                continue
            title_start -= 1
        for header_index in range(title_index + 1, min(title_index + 5, len(lines))):
            header = lines[header_index].strip()
            if not re.fullmatch(r"20\d{2}(?:\s+20\d{2}){1,3}", header):
                continue
            years = [int(y) for y in header.split()]
            if len(set(years)) != len(years) or year not in years:
                continue
            for row_index in range(header_index + 1, min(header_index + 8, len(lines))):
                row = lines[row_index]
                label = re.escape(QCT_ROWS[component]).replace(r"\ ", r"\s+")
                match = re.fullmatch(
                    r"\s*" + label + r"\s*(?:\(\d+\))?\s+([\s\d,$]+)\s*", row
                )
                if not match:
                    continue
                amounts = re.findall(r"\d[\d,]*", match[1])
                if len(amounts) != len(years) or any(
                    not re.fullmatch(r"\d+|\d{1,3}(?:,\d{3})+", amount)
                    for amount in amounts
                ):
                    raise ValueError(
                        "Revenue row does not align with annual year columns"
                    )
                value = int(amounts[years.index(year)].replace(",", "")) * 1_000_000
                found.append(
                    {
                        "value": value,
                        "start": offsets[row_index],
                        "end": offsets[row_index] + len(row),
                        "quote": "".join(lines[title_start : row_index + 1]),
                        "column_years": years,
                        "row_values_millions": amounts,
                        "row_label": QCT_ROWS[component],
                        "scale": 1_000_000,
                        "table": "QCT revenue streams",
                    }
                )
    if len(found) != 1:
        raise ValueError(
            "A unique supported annual revenue table and requested row were not found"
        )
    return found[0]


class FilingRevenueTools:
    def __init__(self, index, store, state):
        from src.research_workflow import ResearchTools

        self.index, self.state = index, state
        self.research = ResearchTools(index, state["companies"], state["years"])
        self.financial = FinancialTools(store, state["companies"], state["years"])
        self.financial.register(list(state.get("financial_sources", {}).values()))
        self.extracted = set()
        self.components = list(
            state.get("revenue_components") or [state["revenue_component"]]
        )
        if (
            state.get("revenue_denominator") == "qct" or len(self.components) > 1
        ) and "qct_total" not in self.components:
            self.components.append("qct_total")
        self.max_tool_calls = self.research.max_tool_calls

    def __call__(self, name, arguments):
        if name != "extract_revenue_component":
            return self.research(name, arguments)
        if (
            not isinstance(arguments, dict)
            or set(arguments) - {"source_id", "component"}
            or "source_id" not in arguments
        ):
            raise ValueError(
                "Extraction requires source_id and an optional requested component"
            )
        components = (
            [arguments["component"]] if arguments.get("component") else self.components
        )
        if any(component not in self.components for component in components):
            raise ValueError("Component exceeds the requested financial scope")
        rows, gaps = [], []
        for component in components:
            try:
                rows.append(
                    self._extract({"source_id": arguments["source_id"]}, component)
                )
            except ValueError as error:
                gaps.append({"component": component, "error": str(error)})
        if not rows:
            raise ValueError(json.dumps(gaps))
        return {**rows[0], "sources": rows, "missing_components": gaps}

    def _extract(self, arguments, component):
        if (
            not isinstance(arguments, dict)
            or set(arguments) != {"source_id"}
            or not isinstance(arguments["source_id"], str)
        ):
            raise ValueError("Extraction requires a registered source_id only")
        passage = self.research.sources[arguments["source_id"]]
        inspected = self.index.inspect(passage["chunk_id"])
        document = self.index.documents[inspected["document_id"]]
        if (
            document["company"] != "QCOM"
            or document["form"] != "10-K"
            or document["version"] != "original"
        ):
            raise ValueError(
                "Verified revenue-component extraction currently supports original Qualcomm annual QCT tables only"
            )
        parsed = qct_revenue_row(
            self.index.text(document), document["fiscal_year"], component
        )
        if inspected["end"] <= parsed["start"] or inspected["start"] >= parsed["end"]:
            raise ValueError(
                "Selected passage does not contain the requested annual note row. Search form=10-K, section=other for 'QCT revenue streams were as follows'."
            )
        totals = [
            s
            for s in self.financial.sources.values()
            if s["company"] == document["company"]
            and s["fiscal_year"] == document["fiscal_year"]
            and s["metric"] == "revenue"
            and s["basis"] == "annual"
        ]
        if len(totals) != 1 or totals[0]["accession"] != document["accession"]:
            raise ValueError(
                "No same-filing annual consolidated revenue denominator is available"
            )
        total = totals[0]
        row = {
            k: total[k]
            for k in (
                "company",
                "fiscal_year",
                "period",
                "basis",
                "start",
                "end",
                "fiscal_start",
                "fiscal_end",
                "filed",
                "unit",
                "revision_basis",
                "accounting_basis",
                "document_id",
                "accession",
                "form",
                "version",
                "canonical_url",
                "warnings",
            )
        }
        row.update(
            kind="financial_observation",
            metric="qct_revenue" if component == "qct_total" else "revenue_component",
            component=component,
            parent_metric="revenue",
            parent_scope="consolidated",
            status="available",
            value=parsed["value"],
            provenance="filing_revenue_table",
            inputs=[],
            conflicting_comparatives=[],
            filing_evidence={
                **parsed,
                "chunk_id": passage["chunk_id"],
                "page": inspected.get("page"),
                "text_sha256": document["extraction"]["text_sha256"],
                "inspection_url": f"/api/sources/{passage['chunk_id']}",
            },
        )
        row["observation_id"] = digest(json.dumps(row, sort_keys=True).encode())
        registered = self.financial.register([row])[0]
        # Before a bundle exists, inspection opens the actual retrieved passage.
        registered["inspection_url"] = f"/api/sources/{passage['chunk_id']}"
        self.extracted.add((row["company"], row["fiscal_year"], component))
        return registered


async def filing_revenue_turn(
    index, store, state, writer, *, model_stream=codex_stream
):
    from src.research_workflow import TOOLS

    tools = FilingRevenueTools(index, store, state)
    writer(
        {
            "type": "tool",
            "data": {
                "name": "initial_revenue_filing_retrieval",
                "arguments": {
                    "companies": state["companies"],
                    "years": state["years"],
                    "component": state["revenue_component"],
                    "form": "10-K",
                    "section": "other",
                },
            },
        }
    )
    for company in state["companies"]:
        for year in state["years"]:
            result = tools(
                "search_sources",
                {
                    "query": f"QCT revenue streams {state['revenue_component']} annual {year}",
                    "company": company,
                    "year": year,
                    "form": "10-K",
                    "section": "other",
                },
            )
            writer({"type": "evidence", "data": result})
    schema = [
        *TOOLS,
        {
            "type": "function",
            "name": "extract_revenue_component",
            "description": "Independently extract the requested revenue component from a retrieved original annual table. The application verifies the row, year columns, scale, passage and matching consolidated filing; never supply a number.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "source_id": {"type": "string"},
                    "component": {"type": "string", "enum": list(QCT_ROWS)},
                },
                "required": ["source_id"],
                "additionalProperties": False,
            },
        },
    ]
    prompt = (
        (ROOT / "prompts/filing_revenue_inputs.md").read_text(encoding="utf-8")
        + "\nRequest: "
        + json.dumps(state)
        + "\nRetrieved passages: "
        + json.dumps(tools.research.sources)
    )
    expected = {
        (c, y, component)
        for c in state["companies"]
        for y in state["years"]
        for component in tools.components
    }
    async with aclosing(
        model_stream(
            prompt,
            schema,
            tools,
            agent="Filings Research",
            reason="Establish filing-only revenue inputs with independent table extraction before Quant",
        )
    ) as stream:
        async for event in stream:
            if event["type"] != "token":
                writer(event)
            if event["type"] == "evidence" and tools.extracted == expected:
                # The worker's contract is satisfied by verified inputs. Its unused
                # prose is not a dependency; closing the stream reaps its model child.
                break
    if tools.extracted != expected:
        return {
            "needs_evidence": {
                "kind": "unverified_revenue_component",
                "message": "A compatible annual revenue component could not be independently established for every selected company/year.",
            },
            "partial": True,
        }
    writer(
        {
            "type": "evidence",
            "data": {"sources": list(tools.financial.sources.values())},
        }
    )
    return {"financial_sources": tools.financial.sources, "needs_evidence": None}
