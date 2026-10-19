/* Request-local activity, using server elapsed time and explicit lifecycle events. */
class AgentActivity {
  static colors = {
    "Financial Data": "#2864c5",
    "Financial Analysis / Quant": "#7850b5",
    "Filings Research": "#087f70",
    "Risk Summary": "#9a5a0b",
    "Current Developments": "#c04f64",
  };
  static statuses = {
    running: "Working", completed: "Complete", partial: "Done · reported a gap",
    failed: "Failed", stopped: "Stopped", unverified: "Unverified",
    needs_clarification: "Clarification needed",
  };

  constructor(inspect) {
    this.inspect = inspect;
    this.list = document.getElementById("agent-activity");
    this.chart = document.getElementById("agent-timeline");
    this.details = document.getElementById("agent-details");
    this.reset();
  }

  reset() {
    clearInterval(this.timer);
    this.calls = new Map();
    this.selected = null;
    this.active = null;
    this.elapsed = 0;
    this.received = performance.now();
    this.running = false;
    this.list.replaceChildren();
    this.chart.replaceChildren();
    this.details.replaceChildren();
    this.details.hidden = true;
    document.getElementById("activity-panel").hidden = true;
    document.getElementById("activity-panel").setAttribute("aria-busy", "false");
    document.getElementById("agent-announcement").textContent = "";
    document.getElementById("agent-elapsed").textContent = "";
  }

  start() {
    this.reset();
    this.running = true;
    document.getElementById("activity-panel").hidden = false;
    document.getElementById("activity-panel").setAttribute("aria-busy", "true");
    const waiting = document.createElement("li");
    waiting.className = "activity-waiting";
    waiting.textContent = "Waiting";
    this.list.append(waiting);
    this.timer = setInterval(() => this.tick(), 250);
  }

  /* The reviewer's partial outcome means it found a gap, not that it failed. */
  label(call) {
    if (call.agent === "Answer Reviewer" && call.status === "partial") return "Found a gap";
    return AgentActivity.statuses[call.status] || call.status;
  }

  seconds(milliseconds) {
    return `${(milliseconds / 1000).toFixed(1)}s`;
  }

  now() {
    return this.elapsed + (this.running ? performance.now() - this.received : 0);
  }

  receive(type, data) {
    if (type === "activity") {
      document.getElementById("activity-panel").hidden = false;
      this.elapsed = data.elapsed_ms ?? this.elapsed;
      this.received = performance.now();
      let call = this.calls.get(data.id);
      if (!call) {
        call = {id: data.id, agent: data.agent, start: this.elapsed, tools: [], sources: []};
        this.calls.set(data.id, call);
      }
      Object.assign(call, data);
      document.getElementById("agent-announcement").textContent = `${call.agent}: ${this.label(call)}`;
      if (data.status === "running") this.active = call.id;
      else {
        call.end = this.elapsed;
        if (this.active === call.id) this.active = null;
      }
      this.render();
    } else if (type === "trace" && (data.provider || data.model) && this.active) {
      Object.assign(this.calls.get(this.active), {provider: data.provider, model: data.model});
      if (this.selected === this.active) this.renderDetails();
    } else if (type === "tool" && this.active) {
      this.calls.get(this.active).tools.push(data.name);
      if (this.selected === this.active) this.renderDetails();
    } else if (type === "complete") this.finish("failed");
  }

  finish(status) {
    if (!this.running && !this.active) return;
    this.elapsed = this.now();
    this.running = false;
    clearInterval(this.timer);
    document.getElementById("activity-panel").setAttribute("aria-busy", "false");
    for (const call of this.calls.values()) {
      if (call.status === "running") {
        call.status = status;
        call.end = this.elapsed;
      }
    }
    this.active = null;
    this.render();
  }

  select(id) {
    this.selected = this.selected === id ? null : id;
    for (const element of this.list.querySelectorAll("button"))
      element.setAttribute("aria-expanded", String(element.dataset.call === this.selected));
    for (const element of this.chart.querySelectorAll("button"))
      element.setAttribute("aria-expanded", String(element.dataset.call === this.selected));
    this.renderDetails();
  }

  button(call, className) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = className;
    button.dataset.call = call.id;
    button.style.setProperty("--agent", AgentActivity.colors[call.agent] || "#586575");
    button.setAttribute("aria-controls", "agent-details");
    button.setAttribute("aria-expanded", String(this.selected === call.id));
    button.onclick = () => this.select(call.id);
    return button;
  }

  render() {
    if (!this.calls.size) return;
    const focused = document.activeElement;
    const focusId = focused.dataset?.call;
    const focusInChart = focused.classList.contains("timeline-call");
    this.list.replaceChildren();
    this.chart.replaceChildren();
    for (const call of this.calls.values()) {
      const item = document.createElement("li");
      item.dataset.status = call.status;
      const button = this.button(call, "agent-call");
      const name = document.createElement("strong");
      name.className = "agent-name";
      name.textContent = call.agent;
      const time = document.createElement("span");
      time.className = "agent-duration";
      const status = document.createElement("span");
      status.className = "agent-status";
      status.textContent = this.label(call);
      button.append(name, time, status);
      item.append(button);
      this.list.append(item);

      const row = this.button(call, "timeline-call");
      row.setAttribute("aria-label", `${call.agent}, ${status.textContent}`);
      const label = document.createElement("span");
      label.className = "timeline-name";
      label.textContent = call.agent;
      const track = document.createElement("span");
      track.className = "timeline-track";
      const bar = document.createElement("span");
      bar.className = "timeline-bar";
      track.append(bar);
      row.append(label, track);
      this.chart.append(row);
    }
    this.tick();
    this.renderDetails();
    if (focusId) {
      const container = focusInChart ? this.chart : this.list;
      Array.from(container.querySelectorAll("button")).find((button) => button.dataset.call === focusId)?.focus({preventScroll: true});
    }
  }

  tick() {
    if (!this.calls.size) return;
    const elapsed = Math.max(1, this.now());
    document.getElementById("agent-elapsed").textContent = this.seconds(elapsed);
    document.getElementById("timeline-end").textContent = this.seconds(elapsed);
    for (const call of this.calls.values()) {
      const duration = Math.max(0, (call.end ?? elapsed) - call.start);
      const item = Array.from(this.list.children).find((item) => item.firstChild.dataset.call === call.id);
      item.querySelector(".agent-duration").textContent = this.seconds(duration);
      const row = Array.from(this.chart.children).find((row) => row.dataset.call === call.id);
      const bar = row.querySelector(".timeline-bar");
      bar.style.left = `${Math.min(100, call.start / elapsed * 100)}%`;
      bar.style.width = `${Math.min(100, duration / elapsed * 100)}%`;
      row.title = `${call.agent} · ${this.label(call)} · ${this.seconds(duration)}`;
    }
  }

  renderDetails() {
    const call = this.calls.get(this.selected);
    this.details.hidden = !call;
    this.details.replaceChildren();
    if (!call) return;
    const heading = document.createElement("h3");
    heading.textContent = call.agent;
    this.details.append(heading);
    for (const text of [call.task, [call.provider, call.model].filter(Boolean).join(" · ")]) {
      if (!text) continue;
      const line = document.createElement("p");
      line.textContent = text;
      this.details.append(line);
    }
    if (call.tools.length) {
      const tools = document.createElement("ul");
      const counts = new Map();
      for (const name of call.tools) counts.set(name, (counts.get(name) || 0) + 1);
      for (const [name, count] of counts) {
        const item = document.createElement("li");
        item.textContent = `${name}${count > 1 ? ` × ${count}` : ""}`;
        tools.append(item);
      }
      this.details.append(tools);
    }
    for (const source of call.sources) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "activity-source";
      button.textContent = `[${source.source_id}]`;
      button.onclick = () => this.inspect(source);
      this.details.append(button);
    }
  }
}
