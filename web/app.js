"use strict";
const state = {messages:[], busy:false, ready:false, mode:"single", coding:false, agency:false};
const byId = id => document.getElementById(id);
const chat = byId("chat"), prompt = byId("prompt"), send = byId("send");

function line(role, value) {
  const intro = chat.querySelector(".intro");
  if (intro) intro.remove();
  const wrapper = document.createElement("article");
  wrapper.className = "message " + role;
  const heading = document.createElement("div");
  heading.className = "message-label";
  heading.textContent = role === "user" ? "YOU" : "CHIMERA";
  const body = document.createElement("div");
  body.className = "message-content";
  body.textContent = value;
  wrapper.append(heading, body);
  chat.append(wrapper);
  chat.scrollTop = chat.scrollHeight;
  return body;
}

function updateControls() {
  const canSend = state.mode === "code" ? state.coding : state.ready;
  send.disabled = state.busy || !canSend ||
    (state.mode === "code" && !byId("code-confirm").checked);
  prompt.disabled = state.busy || !canSend;
  byId("clear").disabled = state.busy;
  byId("code-confirm").disabled = state.busy;
  for (const button of document.querySelectorAll(".mode")) button.disabled = state.busy;
}

function selectMode(mode) {
  if (state.busy || (mode === "code" && !state.coding)) return;
  state.mode = mode;
  for (const button of document.querySelectorAll(".mode"))
    button.classList.toggle("active", button.dataset.mode === mode);
  const council = mode === "council", coding = mode === "code";
  byId("council-models").hidden = !council;
  byId("council-model-label").hidden = !council;
  byId("code-confirm-label").hidden = !coding;
  byId("mode-note").textContent = coding
    ? "Real jcode + Agency Agents. Requires a clean operator-configured Git worktree. Edits are not committed."
    : council
      ? "Two live workers → synthesis → verifier. Reusing one model is not independent verification."
      : "A single actual Ollama model responds to your conversation.";
  byId("footnote").textContent = coding
    ? "Generated code is not automatically approved, committed, pushed or deployed."
    : "LLM agreement does not prove correctness. Verify important information independently.";
  prompt.placeholder = coding ? "Describe a bounded change to the configured worktree…"
    : council ? "Ask the full live model council…" : "Ask Chimera anything…";
  byId("activity").textContent = coding ? "Local coding available"
    : council ? "Live council mode" : "Single-model mode";
  updateControls();
}

for (const button of document.querySelectorAll(".mode"))
  button.addEventListener("click", () => selectMode(button.dataset.mode));
byId("code-confirm").addEventListener("change", updateControls);

async function health() {
  try {
    const [res, featuresResponse] = await Promise.all([
      fetch("/api/health", {cache:"no-store"}),
      fetch("/api/features", {cache:"no-store"}),
    ]);
    const data = await res.json();
    const features = await featuresResponse.json();
    state.ready = res.ok && data.status === "ready";
    state.coding = features.coding === true;
    state.agency = features.agency_roles === true;
    byId("code-mode").hidden = !state.coding;
    byId("connection").className = "status " + (state.ready ? "online" : "offline");
    byId("connection").textContent = state.ready ? "● Model online" : "● Model unavailable";
    byId("model").textContent = data.model || "No model configured";
    byId("setup").textContent = state.ready
      ? (state.agency ? "Live model and Agency Agents role prompts configured."
         : "Live Ollama model connected. Council uses local role instructions.")
      : "Start Ollama and install the configured model, then refresh.";
  } catch (error) {
    state.ready = false;
    byId("connection").textContent = "● Backend offline";
    byId("connection").className = "status offline";
    byId("setup").textContent = "Start Chimera and Ollama, then refresh.";
  }
  updateControls();
}

byId("composer").addEventListener("submit", async event => {
  event.preventDefault();
  const message = prompt.value.trim();
  if (!message || state.busy || (state.mode === "code" ? !state.coding : !state.ready)
      || (state.mode === "code" && !byId("code-confirm").checked)) return;
  state.busy = true;
  const mode = state.mode;
  prompt.value = "";
  line("user", message);
  if (mode !== "code") {
    state.messages.push({role:"user", content:message});
    state.messages = state.messages.slice(-16);
  }
  const answer = line("assistant", mode === "code" ? "Running local jcode specialist workflow…"
    : mode === "council" ? "Running live worker, synthesizer and verifier inference…" : "Generating…");
  byId("activity").textContent = "Working with the configured real runtime";
  updateControls();
  try {
    const path = mode === "code" ? "/api/code" : mode === "council" ? "/api/council" : "/api/chat";
    const body = mode === "code" ? {task:message, confirm:true}
      : mode === "council" ? {
        messages:state.messages,
        models:byId("council-models").value.trim()
          ? byId("council-models").value.trim().split(/\s+/) : undefined,
      } : {messages:state.messages};
    const headers = {"Content-Type":"application/json"};
    if (mode === "code") headers["X-Chimera-Intent"] = "explicit-code-run";
    const response = await fetch(path, {method:"POST", headers, body:JSON.stringify(body)});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || data.status || "Runtime request failed");
    if (mode === "code") {
      answer.textContent = "Coding status: " + data.status + "\n" +
        data.phases.map(p => p.name + ": " + p.status +
          (p.output_preview ? "\n" + p.output_preview : "")).join("\n\n") +
        "\n\nReview the workspace diff before committing.";
      byId("code-confirm").checked = false;
      byId("activity").textContent = data.status + " · manual approval required";
    } else {
      answer.textContent = data.reply || "No answer returned.";
      if (mode === "council") {
        answer.textContent += "\n\nCouncil status: " + data.status +
          (data.verified_by_independent_model
            ? " · independent model agreed (not proof of truth)"
            : " · independent verification NOT established") +
          "\nLive model calls: " + data.requests_used +
          "\nModels: " + JSON.stringify(data.models);
      }
      state.messages.push({role:"assistant", content:data.reply});
      state.messages = state.messages.slice(-16);
      byId("activity").textContent = mode === "council"
        ? "Live council completed" : "Model: " + data.model;
    }
  } catch (error) {
    answer.textContent = "Request failed: " + error.message;
    if (mode !== "code") state.messages.pop();
    byId("activity").textContent = "Runtime request failed";
  } finally {
    state.busy = false;
    updateControls();
    prompt.focus();
    chat.scrollTop = chat.scrollHeight;
  }
});

prompt.addEventListener("keydown", event => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    byId("composer").requestSubmit();
  }
});
byId("clear").addEventListener("click", () => {
  state.messages = [];
  chat.replaceChildren();
  const intro = document.createElement("div");
  intro.className = "intro";
  const title = document.createElement("h1");
  title.textContent = "New conversation.";
  intro.append(title);
  chat.append(intro);
  prompt.focus();
});
health();
