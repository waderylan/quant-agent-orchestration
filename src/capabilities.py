"""Local descriptions of implemented behavior, without provider acquisition."""

import re


AGENTS = {
    "research": ("Filings Research", r"filings? research|research agent", "Finds and explains passages in the selected companies' collected filings and earnings releases with S citations. Inspects original/amended disclosures. A verification request permits one Tavily search for an official update to a specific filed statement, with separate W citations."),
    "data": ("Financial Data", r"financial data|data agent", "Looks up original-report GAAP revenue, gross profit, operating income, parent-attributable net income and operating cash flow. Values retain company, currency and actual fiscal dates. Missing observations remain explicit."),
    "quant": ("Financial Analysis / Quant", r"financial analysis(?:\s*/\s*quant)?|quant(?: agent)?", "Calculates supported growth, changes, margins, ratios and explicit scenarios from compatible source inputs. Publishes independently checked calculations with charts, CSV, code and replayable ledgers. Missing inputs remain explicit. Valuation is unsupported."),
    "risk": ("Risk Summary", r"risk summary|risk agent", "Compares complete original risk sections and cites changed, added, removed, relocated or unchanged wording. Quarterly omissions do not prove an annual risk disappeared; semantic materiality is a model judgment."),
    "current": ("Current Developments", r"current developments|news agent|live research", "Finds recent developments and identifiable outside reactions using Tavily search and extraction. Uses the requested event or calendar window and shows source dates and freshness."),
    "supervisor": ("Supervisor", r"supervisor|router", "Uses the selected companies and fiscal years, chooses the specialists required by the question, orders dependent work and checks evidence handoffs. Shows routing, worker outcomes and missing outputs; a failed worker preserves earlier verified findings. Answers capability questions locally without model or external-provider calls."),
}

SUBJECT = r"(?:you|your(?:self)?|(?:this|the) (?:whole )?(?:system|app|assistant)|(?:each|every|all(?: the)?) agents?|(?:the )?(?:" + "|".join(value[1] for value in AGENTS.values()) + r")(?:'s)?(?: agent)?)"
INTENTS = [
    rf"what (?:can|could) {SUBJECT} (?:do|help(?: me)? with)",
    rf"what (?:does|do) {SUBJECT} do",
    rf"what (?:is|are) {SUBJECT} capable of",
    rf"how (?:does|do) {SUBJECT} (?:work|route|cooperate|help)",
    rf"what (?:are|is) (?:the )?{SUBJECT}(?:'s)? (?:capabilities|limitations|features|roles?|purpose)",
    rf"(?:describe|explain|list|summarize|tell me about) (?:the )?(?:capabilities|limitations|features|roles?) (?:of |for )?{SUBJECT}",
    rf"(?:describe|explain|list|summarize|tell me about) {SUBJECT}(?:'s)? (?:capabilities|limitations|features|roles?)",
    rf"(?:describe|explain|tell me about) (?:the )?(?:system|agents)\b",
    r"(?:what|which) agents? (?:are available|do you have|does (?:the|this) system have)",
    rf"can (?:the )?(?:{'|'.join(value[1] for value in AGENTS.values())})(?: agent)? (?:calculate|compare|retrieve|search|trade|remember|provide|give)",
]


def capability_request(question):
    """Recognize self-description while retaining any requested research output.

    Conjunctions split only before a new interrogative/action. A question such as
    'What can you tell me about its stock price?' remains a research request.
    """
    clauses = re.split(r"[?;\n]+|\.\s+|\s+and\s+(?=(?:what|which|how|show|give|compare|calculate|explain)\b)|\s+then\s+", question, flags=re.I)
    descriptions, work = [], []
    for clause in clauses:
        clause = clause.strip(" .,! ")
        if not clause:
            continue
        if any(re.match(r"^(?:please\s+)?" + pattern + r"\b", clause, re.I) for pattern in INTENTS):
            descriptions.append(clause)
        else:
            work.append(clause)
    if not descriptions:
        return None
    description = " ".join(descriptions)
    selected = [key for key, (_, alias, _) in AGENTS.items() if re.search(r"\b(?:" + alias + r")\b", description, re.I)]
    if not selected or re.search(r"\b(each|every|all)\b.*\bagents?\b|\b(?:system|as a whole)\b", description, re.I):
        selected = list(AGENTS)
    answer = "\n".join(f"- **{AGENTS[key][0]}:** {AGENTS[key][2]}" for key in selected)
    answer += "\n- **Combined answers:** One request can combine a revenue comparison and current news. Financial Data retrieves reported figures, Quant checks changes, Filings Research explains filed drivers, and Current Developments researches outside events or reactions. The Supervisor combines their findings and reports any missing part."
    answer += "\n- **Scope:** NVIDIA, AMD, Intel and Qualcomm. Use the company controls to select one or several. Fiscal years select historical filings; outside research follows the requested event or date window. Market prices and valuation are outside scope. Each request is self-contained, with no cross-turn memory. Generation-provider routing, formal evaluation and Cloud Run deployment are pending."
    return {"answer": answer, "question": "; ".join(work)}
