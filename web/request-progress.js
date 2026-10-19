/* Request plan, per-agent answer sections and a readable trace for one turn. */

function sourceRanges(ids) {
  const groups = new Map();
  for (const id of ids) {
    const match = /^([SFCW])(\d+)$/.exec(id);
    if (!match) continue;
    if (!groups.has(match[1])) groups.set(match[1], []);
    groups.get(match[1]).push(Number(match[2]));
  }
  const parts = [];
  for (const letter of ["F", "C", "S", "W"]) {
    const numbers = [...new Set(groups.get(letter) || [])].sort((a, b) => a - b);
    for (let i = 0; i < numbers.length; i++) {
      let j = i;
      while (j + 1 < numbers.length && numbers[j + 1] === numbers[j] + 1) j++;
      parts.push(j > i ? `${letter}${numbers[i]}–${letter}${numbers[j]}` : `${letter}${numbers[i]}`);
      i = j;
    }
  }
  return parts.join(", ");
}

function hostname(url) {
  try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return "a web page"; }
}

function clip(text, length = 90) {
  text = String(text ?? "").replace(/\s+/g, " ").trim();
  return text.length > length ? text.slice(0, length - 1) + "…" : text;
}

/* One plain-language sentence for a tool call; unknown tools keep their name. */
function describeTool(name, args = {}) {
  args = args && typeof args === "object" && !Array.isArray(args) ? args : {};
  const metrics = (args.metrics || []).map((m) => m.replaceAll("_", " ")).join(", ");
  switch (name) {
    case "initial_financial_query": return "Loading financial observations for the selected scope";
    case "query_financials": return `Looking up ${[args.company, args.year && "FY" + args.year].filter(Boolean).join(" ")} ${metrics}`.trim();
    case "run_analysis": return "Running checked calculation code";
    case "inspect_calculation": return `Checking calculation ${args.source_id || ""}`.trim();
    case "initial_retrieval": return "Retrieving filing passages for the selected companies and years";
    case "search_sources": return `Searching filings: ${clip(args.query)}`;
    case "inspect_source": return `Reading passage ${args.source_id || ""}`.trim();
    case "extract_revenue_component": return "Extracting a revenue component from a filing table";
    case "search_web": return `Searching the web: ${clip(args.query)}`;
    case "extract_page": return `Reading ${hostname(args.url)}`;
    case "inspect_live_source": return `Re-reading web source ${args.source_id || ""}`.trim();
    case "inspect_risk": return "Reading a complete risk-factor section";
    case "risk_pairs": return "Pairing risk factors across years";
    case "record_risk_change": return `Recording a risk change${args.change ? ": " + args.change : ""}`;
    case "report_outcome": return `Reporting outcome: ${args.status || "done"}${args.missing?.length ? " with gaps" : ""}`;
    default: return String(name || "tool").replaceAll("_", " ");
  }
}

class RequestProgress {
  static labels = {
    data: "Reported figures", filing_inputs: "Filing table inputs", quant: "Financial analysis",
    research: "From the filings", current: "Outside research", risk: "Changes in filing risks",
  };
  static stepStates = {
    queued: "Queued", running: "Working", completed: "Done", partial: "Done · reported a gap",
    failed: "Failed", unverified: "Unverified", needs_clarification: "Needs clarification", stopped: "Stopped",
  };

  constructor({render, selectCall, colors}) {
    this.render = render;
    this.selectCall = selectCall;
    this.colors = colors;
    this.card = document.getElementById("request-plan");
    this.answer = document.getElementById("answer");
    this.intermediate = document.getElementById("intermediate-drafts");
    this.reset();
  }

  reset() {
    this.active = false;
    this.finalized = false;
    this.plan = null;
    this.steps = new Map();
    this.outputs = new Map();
    this.current = null;
    this.reviewState = "pending";
    this.stepsOpen = true;
    this.frame = null;
    this.dirty = new Set();
    this.card.replaceChildren();
    this.card.hidden = true;
    this.intermediate.hidden = true;
    this.intermediate.querySelector(":scope > ol").replaceChildren();
  }

  chip(agent) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "agent-chip";
    button.textContent = agent;
    button.style.setProperty("--agent", this.colors[agent] || "#586575");
    return button;
  }

  text(tag, className, value) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    element.textContent = value;
    return element;
  }

  /* Returns true when the event belongs to sectioned mode. */
  receive(type, data) {
    if (type === "plan") return this.receivePlan(data), true;
    if (type === "answer_sections") return this.finalize(data), true;
    if (!this.active) return false;
    if (type === "activity") this.receiveActivity(data);
    else if (type === "draft" || type === "draft_replace" || type === "draft_final") this.receiveDraft(type, data);
    else if (type === "tool") this.narrate(describeTool(data.name, data.arguments));
    else if (type === "trace") this.receiveTrace(data);
    return type.startsWith("draft") || type === "token" || type === "answer";
  }

  receivePlan(plan) {
    const first = !this.active;
    this.active = true;
    this.plan = plan;
    if (first) this.answer.replaceChildren();
    for (const output of plan.outputs) {
      const previous = this.outputs.get(output.id) || {gaps: [], result: null};
      this.outputs.set(output.id, {...previous, ...output});
    }
    for (const step of plan.steps) {
      const previous = this.steps.get(step.id);
      this.steps.set(step.id, previous ? {...previous, ...step} : {...step, state: "queued", markdown: "", now: "", handoff: null, provider: "", model: "", routing: "", node: null});
    }
    this.renderCard();
  }

  receiveActivity(data) {
    if (data.id === "review") {
      this.reviewState = data.status === "running" ? "checking" : data.status;
      for (const step of this.steps.values()) if (step.node) this.badge(step);
      this.renderCard();
      return;
    }
    const step = this.steps.get(data.id);
    if (!step) return;
    step.state = data.status;
    if (data.status === "running") {
      this.current = step.id;
      this.section(step);
    } else if (this.current === step.id) {
      this.current = null;
      step.now = "";
    }
    if (step.node) this.badge(step);
    this.renderCard();
  }

  receiveTrace(data) {
    const step = this.steps.get(this.current);
    if (!step) {
      if (data.node === "answer_coverage") this.coverage(data.results || []);
      return;
    }
    if (data.node === "handoff") {
      const ids = (data.evidence || []).map((ref) => ref.source_id);
      step.handoff = {count: ids.length, ranges: sourceRanges(ids)};
    } else if (data.node === "live_mcp" && !data.result_count) {
      this.narrate(`${data.tool === "tavily_extract" ? hostname(data.arguments?.urls?.[0]) + " returned no content" : "Web search returned no results"}`);
      return;
    } else if ((data.provider || data.model) && data.agent === step.agent) {
      Object.assign(step, {provider: data.provider || "", model: data.model || "", routing: data.routing_reason || ""});
    } else if (data.node === "answer_coverage") this.coverage(data.results || []);
    this.renderCard();
  }

  coverage(results) {
    for (const result of results) {
      const output = this.outputs.get(result.id);
      if (output) output.result = result;
    }
    this.renderCard();
  }

  narrate(text) {
    const step = this.steps.get(this.current);
    if (!step) return;
    step.now = text;
    this.renderCard();
  }

  receiveDraft(type, data) {
    const step = this.steps.get(data.step);
    if (!step || this.finalized) return;
    if (type === "draft") {
      step.markdown += data.delta;
      if (step.id === this.current && step.now !== "Writing its answer") this.narrate("Writing its answer");
    }
    else if (type === "draft_replace") step.markdown = data.markdown;
    else {
      if (data.markdown) step.markdown = data.markdown;
      step.outcome = data.outcome;
      step.evidence = data.evidence || [];
      step.final = true;
    }
    this.section(step);
    this.badge(step);
    this.schedule(step.id);
  }

  schedule(id) {
    this.dirty.add(id);
    if (!this.frame) this.frame = requestAnimationFrame(() => {
      this.frame = null;
      for (const id of this.dirty) this.renderSection(this.steps.get(id));
      this.dirty.clear();
    });
  }

  section(step) {
    if (step.node) return step.node;
    const node = document.createElement("article");
    node.className = "answer-section";
    node.dataset.step = step.id;
    node.style.setProperty("--agent", this.colors[step.agent] || "#586575");
    const header = document.createElement("header");
    const title = this.text("h3", "", RequestProgress.labels[step.worker] || step.agent);
    const chip = this.chip(step.agent);
    chip.onclick = () => this.selectCall(step.id);
    const badge = this.text("span", "section-badge", "");
    header.append(title, chip, badge);
    const body = document.createElement("div");
    body.className = "section-body";
    const removed = document.createElement("details");
    removed.className = "section-removed";
    removed.hidden = true;
    removed.append(document.createElement("summary"), document.createElement("ul"));
    const note = this.text("p", "section-note", "");
    note.hidden = true;
    node.append(header, note, body, removed);
    step.node = node;
    this.answer.append(node);
    this.badge(step);
    this.renderSection(step);
    return node;
  }

  badge(step) {
    const badge = step.node.querySelector(".section-badge");
    let text, state;
    const gaps = (step.serves || []).reduce((n, id) => n + (this.outputs.get(id)?.gaps?.length ? 1 : 0), 0);
    if (step.checked === "Reviewed" && gaps) [text, state] = ["Reviewed · gap noted above", "checked"];
    else if (step.checked) [text, state] = [step.checked, "checked"];
    else if (step.state === "running") [text, state] = ["Draft · writing", "drafting"];
    else if (["failed", "unverified"].includes(step.state)) [text, state] = [RequestProgress.stepStates[step.state], "failed"];
    else if (this.reviewState === "checking") [text, state] = ["Draft · being checked", "checking"];
    else [text, state] = ["Draft · waiting for review", "waiting"];
    badge.textContent = text;
    step.node.dataset.state = state;
  }

  renderSection(step) {
    if (!step?.node) return;
    const body = step.node.querySelector(".section-body");
    if (step.markdown) this.render(body, step.markdown);
    else body.replaceChildren(this.text("p", "section-waiting", step.final ? "No verified answer from this agent." : `${step.agent} is working…`));
    step.node.setAttribute("aria-busy", String(step.state === "running"));
  }

  rerender() {
    for (const step of this.steps.values()) this.renderSection(step);
  }

  /* Finalize each reviewed section in the DOM node that held its draft. */
  finalize(data) {
    this.active = true;
    this.finalized = true;
    cancelAnimationFrame(this.frame);
    this.frame = null;
    const review = data.review || {};
    const checked = review.status === "completed" || review.status === "partial" ? "Reviewed"
      : review.status === "failed" ? "Not reviewed · review unavailable" : "Final";
    for (const gap of data.gaps || []) {
      const output = gap.output && this.outputs.get(gap.output);
      if (output) output.gaps.push(gap);
    }
    const shown = new Set();
    for (const section of data.sections) {
      let step = this.steps.get(section.id);
      if (!step) {
        step = {id: section.id, worker: section.worker, agent: section.agent, state: "completed", markdown: "", node: null, extra: true};
        this.steps.set(section.id, step);
      }
      this.section(step);
      step.markdown = section.markdown;
      step.checked = checked;
      step.state = "completed";
      step.node.querySelector("h3").textContent = section.label || RequestProgress.labels[section.worker] || section.agent;
      step.node.querySelector(".section-note").hidden = true;
      this.removed(step, section.removed || []);
      this.badge(step);
      this.renderSection(step);
      this.answer.append(step.node);
      shown.add(section.id);
    }
    const reasons = new Map((data.folded || []).map((row) => [row.id, row.reason]));
    for (const step of this.steps.values()) {
      if (shown.has(step.id) || !step.node) continue;
      const reason = reasons.get(step.id) || (data.fallback ? "Shown combined in the answer above: a reviewer edit spanned more than one agent's section." : "Not used in the final answer.");
      if (!step.markdown) { step.node.remove(); step.node = null; continue; }
      const note = step.node.querySelector(".section-note");
      note.textContent = reason;
      note.hidden = false;
      step.checked = "Intermediate draft";
      this.badge(step);
      const item = document.createElement("li");
      item.append(step.node);
      this.intermediate.querySelector(":scope > ol").append(item);
      this.intermediate.hidden = false;
      this.intermediate.querySelector(":scope > summary").textContent = `Intermediate drafts (${this.intermediate.querySelectorAll(".answer-section").length})`;
    }
    this.coverage(review.results || []);
    this.answer.prepend(this.finalSummary(data));
    this.reviewState = review.status || "skipped";
    this.stepsOpen = false;
    this.renderCard();
  }

  finalSummary(data) {
    const review = data.review || {};
    const gaps = data.gaps || [];
    const box = document.createElement("section");
    box.className = "final-summary";
    box.dataset.state = gaps.length ? "partial" : review.status === "failed" ? "unreviewed" : "complete";
    box.setAttribute("aria-label", "Final answer summary");
    box.append(this.text("h3", "", gaps.length ? "Final answer · partly complete" : "Final answer"));
    const lead = gaps.length
      ? "This is the finished, reviewed answer. What it states is backed by its cited sources. Some of what you asked for could not be confirmed:"
      : review.status === "completed" || review.status === "partial" ? "This is the finished answer. The Answer Reviewer checked every requested part against the cited sources."
      : review.status === "failed" ? "This is the finished answer, but the review step was unavailable, so it was not checked. Its citations still point to registered sources."
      : "This is the finished answer.";
    box.append(this.text("p", "final-lead", lead));
    if (!gaps.length) return box;
    const why = {
      "Answer Reviewer": "Raised by the Answer Reviewer, which compares the answer with its cited sources. It means this point is unconfirmed, not that the findings shown are wrong.",
      Agent: "Reported by the agent that did the research, before review.",
      Supervisor: "System note: outside what this tool covers, or a step that did not finish.",
    };
    const list = document.createElement("ul");
    list.className = "final-gaps";
    const groups = new Map();
    for (const gap of gaps) {
      const key = gap.output || "";
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(gap);
    }
    for (const [key, rows] of groups) {
      const output = this.outputs.get(key);
      const index = this.plan?.outputs.findIndex((o) => o.id === key) ?? -1;
      const item = document.createElement("li");
      item.dataset.output = key;
      item.append(this.text("strong", "", output ? `Part ${index + 1} · ${output.title}` : "Other limits"));
      for (const gap of rows) {
        const row = document.createElement("p");
        row.append(this.text("span", "gap-text", gap.text), this.text("span", "gap-why", why[gap.source] || why.Supervisor));
        item.append(row);
      }
      list.append(item);
    }
    box.append(list);
    return box;
  }

  removed(step, claims) {
    const box = step.node.querySelector(".section-removed");
    box.hidden = !claims.length;
    box.querySelector("summary").textContent = `${claims.length} ${claims.length === 1 ? "sentence" : "sentences"} removed by the Answer Reviewer`;
    box.querySelector("ul").replaceChildren(...claims.map((claim) => {
      const item = document.createElement("li");
      item.append(this.text("del", "", claim), document.createTextNode(" — not supported by its cited sources"));
      return item;
    }));
  }

  partState(output) {
    const steps = [...this.steps.values()].filter((step) => step.serves?.includes(output.id));
    const step = steps.at(-1);
    if (output.result) return output.result.addressed ? ["Confirmed", "checked"] : ["Gap noted · see answer", "gap"];
    if (output.gaps?.length) return ["Gap noted · see answer", "gap"];
    if (output.kind === "capabilities") return [this.finalized ? "Answered locally" : "Supervisor", "checked"];
    if (output.kind === "unsupported") return ["Outside supported scope", "gap"];
    if (!step) return [this.finalized ? "Not assigned" : "Not assigned to an agent", "gap"];
    if (step.state === "running") return ["Working", "running"];
    if (["failed", "unverified"].includes(step.state)) return [RequestProgress.stepStates[step.state], "gap"];
    if (step.state !== "queued") return [this.reviewState === "checking" ? "Being checked" : this.finalized ? "Done" : "Drafted", "drafted"];
    return ["Queued", "queued"];
  }

  renderCard() {
    if (!this.plan) return;
    const plan = this.plan;
    this.card.hidden = false;
    const open = new Set(Array.from(this.card.querySelectorAll(".plan-parts details[open]"), (d) => d.closest("li").dataset.output));
    const focused = document.activeElement?.closest?.("#request-plan [data-step], #request-plan [data-output]");
    const focusKey = focused && (focused.dataset.step ? `[data-step="${focused.dataset.step}"]` : `[data-output="${focused.dataset.output}"]`);
    const head = document.createElement("div");
    head.className = "plan-head";
    const parts = plan.outputs.length;
    head.append(
      this.text("h3", "", `The supervisor split your request into ${parts} ${parts === 1 ? "part" : "parts"}`),
      this.text("p", "plan-route", plan.steps.length ? `Route: ${plan.route}` : "Route: answered by the Supervisor without agent calls"),
    );
    if (plan.reason) head.append(this.text("p", "plan-reason", `Why: ${plan.reason}`));

    const list = document.createElement("ol");
    list.className = "plan-parts";
    plan.outputs.forEach((output, index) => {
      output = this.outputs.get(output.id) || output;
      const item = document.createElement("li");
      item.dataset.output = output.id;
      const [label, state] = this.partState(output);
      const line = document.createElement("div");
      line.className = "part-line";
      line.append(this.text("span", "part-number", String(index + 1)), this.text("span", "part-title", output.title));
      if (output.agent) {
        const chip = this.chip(output.agent);
        const step = [...this.steps.values()].filter((s) => s.serves?.includes(output.id)).at(-1);
        if (step) chip.onclick = () => this.selectCall(step.id);
        else chip.disabled = true;
        line.append(chip);
      }
      const status = this.text("span", "part-status", label);
      status.dataset.state = state;
      line.append(status);
      item.append(line);
      const details = document.createElement("details");
      details.open = open.has(output.id);
      details.append(this.text("summary", "", "What the planner understood"), this.text("p", "", output.description));
      if (output.timeframe) details.append(this.text("p", "", `Timeframe: ${output.timeframe}`));
      item.append(details);
      list.append(item);
    });

    const steps = document.createElement("details");
    steps.className = "plan-steps";
    steps.open = this.stepsOpen;
    steps.ontoggle = () => { this.stepsOpen = steps.open; };
    steps.append(this.text("summary", "", plan.steps.length ? `How the agents work on it (${plan.steps.length} ${plan.steps.length === 1 ? "step" : "steps"})` : "No agent steps"));
    const ordered = document.createElement("ol");
    for (const step of plan.steps.map((s) => this.steps.get(s.id))) {
      const item = document.createElement("li");
      item.dataset.step = step.id;
      item.dataset.state = step.state;
      item.style.setProperty("--agent", this.colors[step.agent] || "#586575");
      const row = document.createElement("button");
      row.type = "button";
      row.className = "step-row";
      row.onclick = () => this.selectCall(step.id);
      row.append(this.text("span", "step-name", `Step ${step.position} · ${step.agent}`), this.text("span", "step-state", RequestProgress.stepStates[step.state] || step.state));
      item.append(row);
      const names = (ids) => ids.map((id) => { const s = this.steps.get(id); return s ? `Step ${s.position} (${s.agent})` : id; }).join(", ");
      item.append(this.text("p", "step-meta", `Called by ${step.called_by}${step.after.length ? " after " + names(step.after) : " first"}.`));
      const work = step.serves.map((id) => { const o = this.outputs.get(id); return o ? `${plan.outputs.findIndex((p) => p.id === id) + 1} · ${o.title}` : id; });
      item.append(this.text("p", "step-meta", work.length ? `Works on part ${work.join(", ")}.` : `Supplies inputs to ${names(step.feeds) || "the final answer"}.`));
      item.append(this.text("p", "step-meta", `Task: ${step.reason}`));
      if (step.handoff) item.append(this.text("p", "step-meta", step.handoff.count ? `Received ${step.handoff.count} evidence ${step.handoff.count === 1 ? "item" : "items"}: ${step.handoff.ranges}` : "Received no earlier evidence."));
      if (step.provider || step.model) item.append(this.text("p", "step-meta", `Model: ${[step.model, step.provider].filter(Boolean).join(" · ")}${step.routing ? " — " + step.routing : ""}`));
      if (step.evidence?.length) item.append(this.text("p", "step-meta", `Registered ${sourceRanges(step.evidence)}`));
      if (step.now && step.state === "running") item.append(this.text("p", "step-now", `Now: ${step.now}`));
      ordered.append(item);
    }
    steps.append(ordered);
    this.card.replaceChildren(head, list, steps);
    if (focusKey) this.card.querySelector(`${focusKey} button`)?.focus({preventScroll: true});
  }

  statusText() {
    if (!this.active || this.finalized) return "";
    if (this.reviewState === "checking") return "Answer Reviewer is checking the drafts";
    const step = this.steps.get(this.current);
    return step ? `Step ${step.position} of ${this.plan.steps.length} · ${step.agent} is working` : "";
  }

  summary(complete) {
    const status = complete.status;
    const needed = [...this.outputs.values()].filter((o) => this.partState(o)[1] === "gap").length;
    const label = {completed: "Final answer ready", partial: "Final answer ready", coverage_gap: "Coverage gap", needs_clarification: "Clarification needed", unverified: "Response unverified", failed: "Failed"}[status] || status;
    if (needed) return `${label} · ${needed} ${needed === 1 ? "gap" : "gaps"} noted`;
    return status === "completed" && complete.coverage_checked ? `${label} · every part confirmed` : label;
  }

  /* A stream that ended without reviewed sections keeps the latest answer, marked unreviewed. */
  unreviewed(markdown) {
    if (!this.active || this.finalized || !markdown) return;
    this.finalize({sections: [{id: "unreviewed", worker: null, agent: "Supervisor", label: "Answer", markdown, removed: []}], folded: [], review: {status: "failed"}, gaps: []});
  }
}

class TraceLog {
  constructor(clock, agent) {
    this.clock = clock;
    this.agent = agent;
    this.list = document.getElementById("trace");
    this.events = [];
    document.getElementById("trace-download").onclick = () => this.download();
  }

  reset() {
    this.events = [];
    this.list.replaceChildren();
  }

  summary(type, data) {
    if (type === "trace") {
      const agent = data.agent || "Supervisor";
      if (data.provider || data.model) return [agent, `${[data.provider, data.model].filter(Boolean).join(" · ")} — ${data.reason || "model call"}`];
      switch (data.node) {
        case "handoff": {
          const ids = (data.evidence || []).map((ref) => ref.source_id);
          return [agent, `handoff → ${data.decision} · ${ids.length} evidence ${ids.length === 1 ? "item" : "items"}${ids.length ? " (" + sourceRanges(ids) + ")" : ""}`];
        }
        case "task_selection": return [agent, `route: ${data.decision} — ${data.reason || ""}`];
        case "request_understanding": return [agent, `understood ${data.plan?.outputs?.length || 0} requested outputs`];
        case "worker_outcome": return [agent, `${data.worker} ${data.outcome} · ${data.evidence_count} evidence · ${data.tool_calls} tool calls`];
        case "answer_coverage": return [agent, "review: " + (data.results || []).map((r) => `${r.id} ${r.addressed ? "✓" : "still needed"}`).join(" ")];
        case "live_mcp": return [agent, `${data.tool} · ${data.result_count} results${data.cache ? " · cached" : ""}`];
        case "worker_failure": return [agent, `failure: ${data.reason}`];
        default: return [agent, [data.node, data.decision, data.reason].filter(Boolean).join(" · ")];
      }
    }
    if (type === "tool") return [this.agent() || "Agent", `${data.name} · ${describeTool(data.name, data.arguments)}`];
    if (type === "evidence") return [this.agent() || "Agent", data.sources ? `${data.sources.length} sources returned` : data.calculations ? `${data.calculations.length} calculations checked` : data.source_id ? `inspected ${data.source_id}` : data.status ? `outcome ${data.status}` : "evidence"];
    if (type === "plan") return ["Supervisor", `plan · ${data.outputs.length} parts, ${data.steps.length} steps`];
    if (type === "draft_final") return [data.agent, `draft complete · ${data.outcome}`];
    if (type === "answer_sections") return ["Supervisor", `final answer · ${data.sections.length} sections, ${data.folded.length} folded, review ${data.review?.status}`];
    if (type === "complete") return ["Supervisor", `complete · ${data.status}`];
    if (type === "error") return ["Supervisor", `error · ${data}`];
    if (type === "scope") return ["Supervisor", `scope · ${data.message}`];
    if (type === "sources") return [this.agent() || "Supervisor", `${data.length} cited sources`];
    if (type === "artifacts") return ["Financial Analysis / Quant", `${data.calculations?.length || 0} verified calculations`];
    return [null, null];
  }

  add(type, data) {
    const elapsed = Math.round(this.clock());
    this.events.push({type, data, elapsed_ms: elapsed});
    if (["draft", "token", "answer", "activity", "draft_replace"].includes(type)) return;
    const [agent, text] = this.summary(type, data);
    if (!text) return;
    const item = document.createElement("li");
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    const time = document.createElement("span");
    time.className = "trace-time";
    time.textContent = `${(elapsed / 1000).toFixed(1)}s`;
    const who = document.createElement("span");
    who.className = "trace-agent";
    who.textContent = agent;
    summary.append(time, who, document.createTextNode(" " + text));
    details.append(summary);
    details.ontoggle = () => {
      if (!details.open || details.querySelector("pre")) return;
      const pre = document.createElement("pre");
      pre.textContent = JSON.stringify({event: type, data}, null, 2);
      details.append(pre);
    };
    item.append(details);
    this.list.append(item);
  }

  download() {
    const blob = new Blob([JSON.stringify(this.events, null, 2)], {type: "application/json"});
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "agent-trace.json";
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  }
}
