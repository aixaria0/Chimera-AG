"use strict";
const state = { messages: [], busy: false, ready: false };
const byId = (id) => document.getElementById(id);
const chat = byId("chat");
const prompt = byId("prompt");
const send = byId("send");

function line(role, value) {
  const initial = chat.querySelector(".intro");
  if (initial) initial.remove();
  const wrapper = document.createElement("article");
  wrapper.className = "message " + role;
  const heading = document.createElement("div");
  heading.className = "message-label";
  heading.textContent = role === "user" ? "YOU" : "CHIMERA";
  const text = document.createElement("div");
  text.className = "message-content";
  text.textContent = value;
  wrapper.append(heading, text);
  chat.append(wrapper);
  chat.scrollTop = chat.scrollHeight;
  return text;
}

function updateControls() {
  send.disabled = state.busy || !state.ready;
  prompt.disabled = state.busy || !state.ready;
  byId("clear").disabled = state.busy;
}

async function health() {
  try {
    const res = await fetch("/api/health", {cache:"no-store"});
    const data = await res.json();
    state.ready = res.ok && data.status === "ready";
    byId("connection").className = "status " + (state.ready ? "online" : "offline");
    byId("connection").textContent = state.ready ? "● Model online" : "● Model unavailable";
    byId("model").textContent = data.model || "No model configured";
    byId("setup").textContent = state.ready
      ? "Inference is connected to the configured Ollama instance."
      : (data.status === "model_missing"
          ? "Pull this model into Ollama first, then refresh this page."
          : "Start Ollama, install the configured model, and refresh.");
    byId("activity").textContent = state.ready ? "Local inference available" : "Model not ready";
  } catch (error) {
    state.ready = false;
    byId("connection").textContent = "● Backend offline";
    byId("connection").className = "status offline";
    byId("setup").textContent = "Start the Chimera and Ollama services, then refresh.";
    byId("activity").textContent = "Backend unavailable";
  }
  updateControls();
}

byId("composer").addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = prompt.value.trim();
  if (!message || state.busy || !state.ready) return;
  state.busy = true;
  prompt.value = "";
  line("user", message);
  state.messages.push({role:"user", content:message});
  state.messages = state.messages.slice(-16);
  const answer = line("assistant", "Thinking with your model…");
  byId("activity").textContent = "Generating an actual model response";
  updateControls();
  try {
    const res = await fetch("/api/chat", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({messages:state.messages}),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Model request failed");
    answer.textContent = data.reply;
    state.messages.push({role:"assistant", content:data.reply});
    state.messages = state.messages.slice(-16);
    byId("activity").textContent = "Model: " + data.model +
      (typeof data.eval_count === "number" ? " · " + data.eval_count + " generated tokens" : "");
  } catch (error) {
    answer.textContent = "Model request failed: " + error.message;
    state.messages.pop();
    byId("activity").textContent = "Request failed; retry after checking Ollama";
  } finally {
    state.busy = false;
    updateControls();
    prompt.focus();
  }
});

prompt.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    byId("composer").requestSubmit();
  }
});

byId("clear").addEventListener("click", () => {
  state.messages = [];
  chat.replaceChildren();
  const welcome = document.createElement("div");
  welcome.className = "intro";
  const title = document.createElement("h1");
  title.textContent = "New conversation.";
  const subtitle = document.createElement("p");
  subtitle.textContent = "Your model is ready for a fresh question.";
  welcome.append(title, subtitle);
  chat.append(welcome);
  prompt.focus();
});

health();
