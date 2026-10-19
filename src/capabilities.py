"""Local descriptions of implemented behavior, without provider acquisition."""

import re


AGENTS = {
    "research": ("Filings Research", r"filings? research|research agent", "Searches the collected 10-K and 10-Q filings and earnings releases and explains what they say, citing the exact passage (S citations you can click). If you ask whether a filed statement is still current, it can run one web search for an official update (W citations)."),
    "data": ("Financial Data", r"financial data|data agent", "Looks up exact reported GAAP figures from SEC data: revenue, gross profit, operating income, net income and operating cash flow (F citations). Each figure shows its company and actual fiscal dates. If a figure is not in the data, the answer says so."),
    "quant": ("Financial Analysis / Quant", r"financial analysis(?:\s*/\s*quant)?|quant(?: agent)?", "Calculates growth, changes, margins, ratios and simple what-if scenarios from those reported figures. Every result is recomputed by a separate check before it is shown (C citations), with a chart, a CSV table and the code you can download. It does not value companies."),
    "risk": ("Risk Summary", r"risk summary|risk agent", "Compares the full risk-factor sections of two annual filings and cites what was added, removed or reworded. Whether a change matters is the model's judgment, and the answer says so."),
    "current": ("Current Developments", r"current developments|news agent|live research", "Searches the web for recent developments and for what outside analysts, reporters or customers said, within the time window you ask about. Each web source shows its publisher and date (W citations)."),
    "supervisor": ("Supervisor", r"supervisor|router", "Splits your question into parts, picks the agents each part needs and runs them in order, passing each one the evidence from the earlier steps. The page shows this plan, which agent is working, and anything that could not be answered. If one agent fails, findings from the others are kept."),
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
    answer += "\n- **Combined answers:** One question can mix several parts, for example a revenue comparison plus recent news. Each part goes to its agent, and the Supervisor combines their sections into one answer."
    answer += "\n- **How to check the numbers:** Click any citation to see the exact filing passage or SEC figure behind it. Calculations are recomputed independently, and an Answer Reviewer checks the final answer against its sources and removes anything they do not support."
    answer += "\n- **Scope:** NVIDIA, AMD, Intel and Qualcomm. Use the company controls to select one or several. Fiscal years select which filings and figures are used; web research follows the time window in your question. Stock prices, valuations and investment advice are outside scope. Each request is self-contained: it does not remember earlier questions."
    return {"answer": answer, "question": "; ".join(work)}
