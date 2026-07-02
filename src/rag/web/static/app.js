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
  const uploadBtn = document.getElementById("upload-btn");
  if (uploadBtn) uploadBtn.disabled = busy;
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

// --- Subida y Re-indexación de Archivos (Drag & Drop + Input) ---
const fileInput = document.getElementById("file-input");
const uploadBtn = document.getElementById("upload-btn");
const dropOverlay = document.getElementById("drop-overlay");

function appendUploadStatusMessage(text, isError) {
  if (empty) empty.style.display = "none";

  const wrap = el("div", "msg bot");
  wrap.appendChild(el("div", "avatar", "👩‍💻"));

  const col = el("div", "col");
  const bubble = el("div", "bubble upload-status" + (isError ? " no-answer" : ""));
  bubble.innerHTML = renderAnswer(text, []);
  
  col.appendChild(bubble);
  wrap.appendChild(col);
  chat.appendChild(wrap);
  chat.scrollTop = chat.scrollHeight;
  return bubble;
}

function updateUploadStatusMessage(bubbleNode, text, isError) {
  bubbleNode.innerHTML = renderAnswer(text, []);
  bubbleNode.className = "bubble upload-status" + (isError ? " no-answer" : "");
  chat.scrollTop = chat.scrollHeight;
}

async function handleFileUpload(file) {
  const MAX_SIZE = 20 * 1024 * 1024; // 20 MB
  if (file.size > MAX_SIZE) {
    appendUploadStatusMessage(`⚠ El archivo **${file.name}** supera el límite de 20 MB.`, true);
    return;
  }

  const allowedExts = [".pdf", ".docx", ".xlsx", ".pptx", ".md", ".markdown", ".csv", ".json", ".html"];
  const ext = "." + file.name.split(".").pop().toLowerCase();
  if (!allowedExts.includes(ext)) {
    appendUploadStatusMessage(`⚠ El formato del archivo **${file.name}** no está soportado.`, true);
    return;
  }

  setBusy(true);
  const bubbleNode = appendUploadStatusMessage(`📤 Subiendo e indexando **${file.name}**...`, false);

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch("/api/documents/upload", {
      method: "POST",
      body: formData
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || res.statusText);
    }
    const data = await res.json();
    const statusText = `✅ Documento **${data.filename}** indexado con éxito (${data.chunks_added} fragmentos).`;
    updateUploadStatusMessage(bubbleNode, statusText, false);
    
    // Guardar en el historial local para persistencia
    const botMsg = { role: "bot", content: statusText };
    state.messages.push(botMsg);
    saveState();

    // Recargar lista de documentos si el panel está abierto
    if (docsPanel && docsPanel.classList.contains("open")) {
      loadDocuments();
    }
  } catch (err) {
    const errorText = `⚠ Error al procesar **${file.name}**: ${err.message}`;
    updateUploadStatusMessage(bubbleNode, errorText, true);
    
    // Guardar el error en el historial
    const botMsg = { role: "bot", content: errorText, no_answer: true };
    state.messages.push(botMsg);
    saveState();
  } finally {
    setBusy(false);
    input.focus();
  }
}

// --- Lógica del Panel de Documentos (Listar, Eliminar, Reindexar) ---
const docsBtn = document.getElementById("docs-btn");
const docsPanel = document.getElementById("docs-panel");
const docsClose = document.getElementById("docs-close");
const docsUploadBox = document.getElementById("docs-upload-box");
const reindexBtn = document.getElementById("reindex-btn");

async function loadDocuments() {
  const docsList = document.getElementById("docs-list");
  const docsCount = document.getElementById("docs-count");
  if (!docsList) return;

  try {
    const res = await fetch("/api/documents");
    if (!res.ok) throw new Error("No se pudo obtener la lista de documentos");
    const data = await res.json();
    
    docsCount.textContent = data.length;
    docsList.innerHTML = "";
    
    if (data.length === 0) {
      const emptyLi = el("li", "doc-empty-state");
      emptyLi.style.textAlign = "center";
      emptyLi.style.padding = "20px";
      emptyLi.style.color = "var(--muted)";
      emptyLi.style.fontSize = "13px";
      emptyLi.textContent = "No hay documentos indexados.";
      docsList.appendChild(emptyLi);
      return;
    }
    
    data.forEach(doc => {
      const li = el("li", "doc-item");
      
      const mainDiv = el("div", "doc-item-main");
      
      const nameSpan = el("span", "doc-name", doc.filename);
      mainDiv.appendChild(nameSpan);
      
      const deleteBtn = el("button", "doc-delete-btn", "🗑");
      deleteBtn.title = "Eliminar documento del índice";
      deleteBtn.addEventListener("click", async (e) => {
        e.stopPropagation();
        if (confirm(`¿Estás seguro de que quieres eliminar el documento "${doc.filename}"? Esto también borrará sus fragmentos del índice.`)) {
          try {
            deleteBtn.disabled = true;
            deleteBtn.textContent = "⏳";
            const delRes = await fetch(`/api/documents/${encodeURIComponent(doc.filename)}`, {
              method: "DELETE"
            });
            if (!delRes.ok) {
              const errData = await delRes.json().catch(() => ({}));
              throw new Error(errData.detail || "Error al eliminar");
            }
            appendUploadStatusMessage(`✅ Documento **${doc.filename}** eliminado correctamente del índice.`, false);
            loadDocuments();
          } catch (err) {
            alert(`Error al eliminar documento: ${err.message}`);
            deleteBtn.disabled = false;
            deleteBtn.textContent = "🗑";
          }
        }
      });
      mainDiv.appendChild(deleteBtn);
      
      li.appendChild(mainDiv);
      
      const metaInfo = el("div", "doc-meta-info");
      
      // Tamaño formateado
      const sizeKB = (doc.size_bytes / 1024).toFixed(1);
      const sizeStr = sizeKB > 1024 ? `${(sizeKB / 1024).toFixed(1)} MB` : `${sizeKB} KB`;
      const sizeSpan = el("span", null, sizeStr);
      metaInfo.appendChild(sizeSpan);
      
      metaInfo.appendChild(el("span", null, "·"));
      
      // Chunks
      const chunksSpan = el("span", null, `${doc.chunks || 0} frag.`);
      metaInfo.appendChild(chunksSpan);
      
      if (doc.last_ingested) {
        metaInfo.appendChild(el("span", null, "·"));
        try {
          const date = new Date(doc.last_ingested);
          const dateStr = date.toLocaleDateString("es-ES", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
          const dateSpan = el("span", null, dateStr);
          metaInfo.appendChild(dateSpan);
        } catch {
          // ignore date parse errors
        }
      }
      
      const badge = el("span", `doc-badge ${doc.status}`, doc.status === "indexed" ? "Indexado" : "No indexado");
      metaInfo.appendChild(badge);
      
      li.appendChild(metaInfo);
      docsList.appendChild(li);
    });
  } catch (err) {
    console.error(err);
    docsList.innerHTML = `<li style="color:var(--danger); padding:10px; font-size:13px;">Error: ${err.message}</li>`;
  }
}

function setDocsPanel(open) {
  if (docsPanel) {
    if (open) {
      docsPanel.classList.add("open");
      loadDocuments();
    } else {
      docsPanel.classList.remove("open");
    }
  }
}

if (docsBtn) {
  docsBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    setAbout(false); // Cerrar ayuda si está abierta
    setDocsPanel(!docsPanel.classList.contains("open"));
  });
}

if (docsClose) {
  docsClose.addEventListener("click", () => setDocsPanel(false));
}

// Cerrar al hacer click fuera del panel
document.addEventListener("click", (e) => {
  if (docsPanel && docsPanel.classList.contains("open") && !docsPanel.contains(e.target) && e.target !== docsBtn) {
    setDocsPanel(false);
  }
});

if (docsUploadBox && fileInput) {
  docsUploadBox.addEventListener("click", () => fileInput.click());
}

if (reindexBtn) {
  reindexBtn.addEventListener("click", async () => {
    try {
      reindexBtn.disabled = true;
      reindexBtn.innerHTML = `<span class="btn-icon">⏳</span> Reindexando...`;
      
      const res = await fetch("/api/documents/reindex?force=true", {
        method: "POST"
      });
      if (!res.ok) throw new Error("Error al reindexar");
      
      const data = await res.json();
      const statusText = `✅ Reindexado general completado. Indexados: ${data.indexed.length}, Sin cambios: ${data.unchanged.length}, Errores: ${data.errors.length}.`;
      appendUploadStatusMessage(statusText, data.errors.length > 0);
      
      loadDocuments();
    } catch (err) {
      alert(`Error al reindexar: ${err.message}`);
    } finally {
      reindexBtn.disabled = false;
      reindexBtn.innerHTML = `<span class="btn-icon">🔄</span> Reindexar todo`;
    }
  });
}

if (uploadBtn && fileInput) {
  uploadBtn.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", () => {
    if (fileInput.files.length > 0) {
      handleFileUpload(fileInput.files[0]);
      fileInput.value = "";
    }
  });
}

if (dropOverlay) {
  let dragCounter = 0;

  window.addEventListener("dragenter", (e) => {
    e.preventDefault();
    dragCounter++;
    if (dragCounter === 1) {
      dropOverlay.hidden = false;
    }
  });

  window.addEventListener("dragover", (e) => {
    e.preventDefault();
  });

  window.addEventListener("dragleave", (e) => {
    e.preventDefault();
    dragCounter--;
    if (dragCounter === 0) {
      dropOverlay.hidden = true;
    }
  });

  window.addEventListener("drop", (e) => {
    e.preventDefault();
    dragCounter = 0;
    dropOverlay.hidden = true;
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  });
}

// Rehidratar el historial guardado al cargar.
state.messages.forEach(renderMessage);
input.focus();
