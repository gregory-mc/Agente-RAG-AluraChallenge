"use strict";

// Estado de conversación, persistido en localStorage (issue #6: historial).
const STORE_KEY = "rag_chat_v1";
let state = loadState();

const chat = document.getElementById("chat");
const empty = document.getElementById("empty");
const form = document.getElementById("composer");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send");

function loadState() {
  try {
    return JSON.parse(localStorage.getItem(STORE_KEY)) || { conversationId: null, messages: [] };
  } catch {
    return { conversationId: null, messages: [] };
  }
}
function saveState() {
  localStorage.setItem(STORE_KEY, JSON.stringify(state));
}

function shortSource(src) {
  const parts = String(src).split(/[\\/]/);
  return parts[parts.length - 1] || src;
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// Convierte el texto del modelo en HTML seguro:
//  - escapa HTML, aplica **negritas** y viñetas "- ",
//  - reemplaza los marcadores [n] / [n,m] por citas superíndice que enlazan a la fuente.
function renderAnswer(text, sources) {
  sources = sources || [];
  const lines = escapeHtml(text).split("\n");
  let html = "";
  let inList = false;
  for (let raw of lines) {
    const line = raw.trim();
    const isItem = /^[-*]\s+/.test(line);
    if (isItem) {
      if (!inList) { html += "<ul>"; inList = true; }
      html += "<li>" + line.replace(/^[-*]\s+/, "") + "</li>";
    } else {
      if (inList) { html += "</ul>"; inList = false; }
      if (line) html += line + "<br>";
    }
  }
  if (inList) html += "</ul>";
  html = html.replace(/<br>\s*$/, "");
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

  // [1] o [1,2] -> una insignia por número.
  html = html.replace(/\[(\d+(?:\s*,\s*\d+)*)\]/g, (_, group) =>
    group.split(",").map((n) => {
      const num = n.trim();
      const src = sources[parseInt(num, 10) - 1];
      const title = src ? ` title="${escapeHtml(shortSource(src))}"` : "";
      return `<sup class="cite"${title}>${num}</sup>`;
    }).join("")
  );
  return html;
}

function confidenceLabel(c) {
  if (c == null) return null;
  const pct = Math.round(c * 100);
  let cls = "low";
  if (c >= 0.55) cls = "high";
  else if (c >= 0.4) cls = "mid";
  return { cls, text: `confianza ${pct}%` };
}

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text != null) node.textContent = text;
  return node;
}

function renderMessage(m) {
  if (empty) empty.style.display = "none";

  const wrap = el("div", `msg ${m.role}`);
  wrap.appendChild(el("div", "avatar", m.role === "bot" ? "👩‍💻" : "Tú"));

  const col = el("div", "col");
  const bubble = el("div", "bubble" + (m.no_answer ? " no-answer" : ""));
  if (m.role === "bot") {
    bubble.innerHTML = renderAnswer(m.content, m.sources);
  } else {
    bubble.textContent = m.content;
  }
  col.appendChild(bubble);

  if (m.role === "bot") {
    const meta = el("div", "meta");

    if (m.sources && m.sources.length) {
      const srcWrap = el("div", "sources");
      m.sources.forEach((s, i) => {
        const chip = el("span", "src");
        chip.title = s;
        chip.appendChild(el("span", "num", String(i + 1)));
        chip.appendChild(el("span", "name", shortSource(s)));
        srcWrap.appendChild(chip);
      });
      meta.appendChild(srcWrap);
    }

    const conf = confidenceLabel(m.confidence);
    if (conf) {
      const c = el("span", "confidence");
      c.appendChild(el("span", `dot ${conf.cls}`));
      c.appendChild(document.createTextNode(conf.text));
      meta.appendChild(c);
    }

    if (m.message_id) meta.appendChild(buildFeedback(m));
    if (meta.childNodes.length) col.appendChild(meta);

    if (m.suggestions && m.suggestions.length) {
      const sug = el("div", "followups");
      m.suggestions.forEach((q) => {
        const b = el("button", "followup", q);
        b.addEventListener("click", () => ask(q));
        sug.appendChild(b);
      });
      col.appendChild(sug);
    }
  }

  wrap.appendChild(col);
  chat.appendChild(wrap);
  chat.scrollTop = chat.scrollHeight;
  return wrap;
}

function buildFeedback(m) {
  const fb = el("div", "feedback");
  const up = el("button", null, "👍");
  const down = el("button", null, "👎");
  up.title = "Respuesta útil";
  down.title = "Respuesta no útil";

  function send(rating, btn) {
    fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversation_id: state.conversationId,
        message_id: m.message_id,
        rating,
      }),
    }).catch(() => {});
    m.feedback = rating;
    up.disabled = down.disabled = true;
    btn.classList.add("active");
    saveState();
  }

  if (m.feedback === 1) { up.classList.add("active"); up.disabled = down.disabled = true; }
  if (m.feedback === -1) { down.classList.add("active"); up.disabled = down.disabled = true; }
  up.addEventListener("click", () => send(1, up));
  down.addEventListener("click", () => send(-1, down));
  fb.appendChild(up);
  fb.appendChild(down);
  return fb;
}

function showTyping() {
  const wrap = el("div", "msg bot typing");
  wrap.appendChild(el("div", "avatar", "👩‍💻"));
  const col = el("div", "col");
  const bubble = el("div", "bubble");
  bubble.appendChild(el("span", "d"));
  bubble.appendChild(el("span", "d"));
  bubble.appendChild(el("span", "d"));
  col.appendChild(bubble);
  wrap.appendChild(col);
  chat.appendChild(wrap);
  chat.scrollTop = chat.scrollHeight;
  return wrap;
}

async function ask(question) {
  const userMsg = { role: "user", content: question };
  state.messages.push(userMsg);
  renderMessage(userMsg);
  saveState();

  input.value = "";
  setBusy(true);
  const typing = showTyping();

  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, conversation_id: state.conversationId }),
    });
    typing.remove();
    if (!res.ok) {
      const detail = (await res.json().catch(() => ({}))).detail || res.statusText;
      throw new Error(detail);
    }
    const data = await res.json();
    state.conversationId = data.conversation_id;
    const botMsg = {
      role: "bot",
      content: data.answer,
      sources: data.sources,
      suggestions: data.suggestions,
      confidence: data.confidence,
      no_answer: data.no_answer,
      message_id: data.message_id,
    };
    state.messages.push(botMsg);
    renderMessage(botMsg);
    saveState();
  } catch (err) {
    typing.remove();
    const botMsg = { role: "bot", content: "⚠ " + err.message, no_answer: true };
    state.messages.push(botMsg);
    renderMessage(botMsg);
    saveState();
  } finally {
    setBusy(false);
    input.focus();
  }
}

function setBusy(busy) {
  input.disabled = busy;
  sendBtn.disabled = busy;
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const q = input.value.trim();
  if (q) ask(q);
});

document.querySelectorAll(".suggestion").forEach((b) =>
  b.addEventListener("click", () => ask(b.textContent.trim()))
);

document.getElementById("clear").addEventListener("click", () => {
  state = { conversationId: null, messages: [] };
  saveState();
  chat.querySelectorAll(".msg").forEach((n) => n.remove());
  if (empty) empty.style.display = "";
});

// Panel "¿Qué es el Agente RAG?" (botón flotante).
const aboutBtn = document.getElementById("about-btn");
const aboutPanel = document.getElementById("about-panel");
const aboutClose = document.getElementById("about-close");

function setAbout(open) {
  aboutPanel.hidden = !open;
  aboutBtn.setAttribute("aria-expanded", String(open));
}
aboutBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  setAbout(aboutPanel.hidden);
});
aboutClose.addEventListener("click", () => setAbout(false));
aboutPanel.querySelectorAll(".hint").forEach((h) =>
  h.addEventListener("click", () => { setAbout(false); ask(h.textContent.trim()); })
);
document.addEventListener("click", (e) => {
  if (!aboutPanel.hidden && !aboutPanel.contains(e.target) && e.target !== aboutBtn) {
    setAbout(false);
  }
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape") setAbout(false); });

// Rehidratar el historial guardado al cargar.
state.messages.forEach(renderMessage);
input.focus();
