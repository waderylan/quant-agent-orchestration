"""Model-facing assigned requests; original questions remain available to review."""


def assigned_question(state: dict, *kinds: str) -> str:
    descriptions = [output["description"] for output in state.get("request_plan", {}).get("outputs", [])
                    if output["kind"] in kinds and output.get("description")]
    return "\n".join(descriptions) if descriptions else state["question"]
