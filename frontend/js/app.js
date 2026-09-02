/* Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved. */
"use strict";

function reportClientError(level, message, stack) {
  try {
    fetch("/api/logs/client", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        level,
        message,
        stack: stack || "",
        url: window.location.href,
        user_agent: navigator.userAgent,
      }),
    }).catch(() => {});
  } catch { /* не критично */ }
}

window.addEventListener("error", (e) => {
  reportClientError(
    "error",
    `JS: ${e.message} (${e.filename}:${e.lineno}:${e.colno})`,
    e.error && e.error.stack ? e.error.stack : ""
  );
});

window.addEventListener("unhandledrejection", (e) => {
  const reason = e.reason;
  const msg = reason && reason.message ? reason.message : String(reason);
  reportClientError(
    "error",
    `Unhandled promise rejection: ${msg}`,
    reason && reason.stack ? reason.stack : ""
  );
});

const nativeFetch = window.fetch;
window.fetch = async (...args) => {
  const res = await nativeFetch(...args);
  if (!res.ok && !String(args[0]).includes("/api/logs/client")) {
    reportClientError("warn", `HTTP ${res.status} ${String(args[0])}`);
  }
  return res;
};

const messagesEl = document.getElementById("messages");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("send");
const modelLabel = document.getElementById("model-label");
const modelDot = document.querySelector("#model-status .dot");
const kiwixLabel = document.getElementById("kiwix-label");
const kiwixDot = document.querySelector("#kiwix-status-line .dot");
const newChatBtn = document.getElementById("btn-new");
const btnPhoto = document.getElementById("btn-photo");
const btnDoc = document.getElementById("btn-doc");
const btnAnalysis = document.getElementById("btn-analysis");
const filePhoto = document.getElementById("file-photo");
const fileDoc = document.getElementById("file-doc");
const extractPanel = document.getElementById("extract-panel");
const extractTitle = document.getElementById("extract-title");
const extractStatus = document.getElementById("extract-status");
const extractResult = document.getElementById("extract-result");
const extractClose = document.getElementById("extract-close");
const chatView = document.getElementById("chat-view");
const cardView = document.getElementById("card-view");
const recordsEl = document.getElementById("records");
const btnRefresh = document.getElementById("btn-refresh");
const btnTrends = document.getElementById("btn-trends");
const btnExportPdf = document.getElementById("btn-export-pdf");
const trendsEl = document.getElementById("trends");
const navItems = document.querySelectorAll(".nav-item");
const articlesView = document.getElementById("articles-view");
const articlesList = document.getElementById("articles-list");
const articleStatus = document.getElementById("article-status");
const articleQuery = document.getElementById("article-query");
const btnUploadArticle = document.getElementById("btn-upload-article");
const btnRefreshArticles = document.getElementById("btn-refresh-articles");
const btnArticleSearch = document.getElementById("btn-article-search");
const fileArticle = document.getElementById("file-article");
const btnSettings = document.getElementById("btn-settings");
const btnLogs = document.getElementById("btn-logs");
const logsModal = document.getElementById("logs-modal");
const logsContent = document.getElementById("logs-content");
const logsClose = document.getElementById("logs-close");
const btnLogsRefresh = document.getElementById("btn-logs-refresh");
const btnLogsDownload = document.getElementById("btn-logs-download");
const btnLogsClear = document.getElementById("btn-logs-clear");
const modalTabs = document.querySelectorAll(".modal-tabs .tab-btn");
const auditFilters = document.getElementById("audit-filters");
const auditActionFilter = document.getElementById("audit-action-filter");
const btnAuditClear = document.getElementById("btn-audit-clear");
let logsTab = "journal";
const settingsModal = document.getElementById("settings-modal");
const settingsClose = document.getElementById("settings-close");
const settingsCancel = document.getElementById("settings-cancel");
const settingsSave = document.getElementById("settings-save");
const setOllamaUrl = document.getElementById("set-ollama-url");
const setKiwixUrl = document.getElementById("set-kiwix-url");
const setKiwixZim = document.getElementById("set-kiwix-zim");
const btnKiwixBooks = document.getElementById("btn-kiwix-books");
const kiwixStatus = document.getElementById("kiwix-status");
const setChatModel = document.getElementById("set-chat-model");
const setVisionModel = document.getElementById("set-vision-model");
const setEmbedModel = document.getElementById("set-embed-model");
const setNumCtx = document.getElementById("set-num-ctx");
const btnRefreshModels = document.getElementById("btn-refresh-models");
const modelsStatus = document.getElementById("models-status");
const notesView = document.getElementById("notes-view");
const notesList = document.getElementById("notes-list");
const notesStatus = document.getElementById("notes-status");
const btnRefreshNotes = document.getElementById("btn-refresh-notes");
const btnNewNote = document.getElementById("btn-new-note");
const btnSaveNote = document.getElementById("btn-save-note");
const noteModal = document.getElementById("note-modal");
const noteArticle = document.getElementById("note-article");
const noteContent = document.getElementById("note-content");
const noteClose = document.getElementById("note-close");
const noteCancel = document.getElementById("note-cancel");
const noteSave = document.getElementById("note-save");
const profileNameLabel = document.getElementById("profile-name-label");
const btnEditProfile = document.getElementById("btn-edit-profile");
const profileMeta = document.getElementById("profile-meta");
const profileModal = document.getElementById("profile-modal");
const profileName = document.getElementById("profile-name");
const profileBirthYear = document.getElementById("profile-birth-year");
const profileHeight = document.getElementById("profile-height");
const profileWeight = document.getElementById("profile-weight");
const profileBloodType = document.getElementById("profile-blood-type");
const profileClose = document.getElementById("profile-close");
const profileCancel = document.getElementById("profile-cancel");
const profileSave = document.getElementById("profile-save");
const remindersEl = document.getElementById("reminders");
const reminderModal = document.getElementById("reminder-modal");
const reminderMarker = document.getElementById("reminder-marker");
const reminderInterval = document.getElementById("reminder-interval");
const reminderMarkerList = document.getElementById("reminder-marker-list");
const reminderClose = document.getElementById("reminder-close");
const reminderCancel = document.getElementById("reminder-cancel");
const reminderSave = document.getElementById("reminder-save");
const btnExportNotes = document.getElementById("btn-export-notes");

let currentArticleId = null;
let currentProfileId = null;

const CHAT_STORAGE_KEY = "zelvera.chat.history";

function loadHistory() {
  try {
    const raw = localStorage.getItem(CHAT_STORAGE_KEY);
    const arr = raw ? JSON.parse(raw) : [];
    return Array.isArray(arr) ? arr.filter((m) => m && m.role && typeof m.content === "string") : [];
  } catch {
    return [];
  }
}

function saveHistory() {
  try {
    localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(history));
  } catch { /* нет места в localStorage — не критично */ }
}

function pushHistory(role, content, images) {
  const item = { role, content };
  if (images && images.length) item.images = images;
  history.push(item);
  saveHistory();
}

let history = loadHistory();
let extractData = null;

function profileQuery() {
  return currentProfileId ? `profile_id=${encodeURIComponent(currentProfileId)}` : "";
}

async function loadProfiles() {
  try {
    const res = await fetch("/api/profiles");
    const data = await res.json();
    const profiles = data.profiles || [];
    const current =
      profiles.find((p) => p.id === data.current) || profiles[0] || null;
    currentProfileId = current ? current.id : null;
    if (profileNameLabel) {
      profileNameLabel.textContent = current ? current.name : t("profileLabel");
    }
    renderProfileMeta(current);
  } catch (err) {
    if (profileNameLabel) profileNameLabel.textContent = t("profileLabel");
  }
}

function renderProfileMeta(p) {
  if (!profileMeta) return;
  if (!p) {
    profileMeta.textContent = "";
    return;
  }
  const parts = [];
  if (p.birth_year) parts.push(t("profile.meta.birth", { y: p.birth_year }));
  if (p.height_cm) parts.push(t("profile.meta.height", { h: p.height_cm }));
  if (p.weight_kg) parts.push(t("profile.meta.weight", { w: p.weight_kg }));
  if (p.blood_type) parts.push(t("profile.meta.blood", { b: p.blood_type }));
  profileMeta.textContent = parts.length ? parts.join(" · ") : t("profile.meta.empty");
}

async function openProfileEditModal() {
  try {
    const res = await fetch("/api/profiles/current");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const p = await res.json();
    if (!p || !p.id) throw new Error(t("profile.notFound"));
    profileName.value = p.name || "";
    profileBirthYear.value = p.birth_year || "";
    profileHeight.value = p.height_cm || "";
    profileWeight.value = p.weight_kg || "";
    profileBloodType.value = p.blood_type || "";
    profileModal.classList.remove("hidden");
    profileName.focus();
  } catch (err) {
    showToast(t("profile.errorLoad", { msg: err.message }), "error");
  }
}

function closeProfileModal() {
  profileModal.classList.add("hidden");
}

function profilePayload() {
  const name = profileName.value.trim();
  const birthYear = profileBirthYear.value ? Number(profileBirthYear.value) : null;
  const height = profileHeight.value ? Number(profileHeight.value) : null;
  const weight = profileWeight.value ? Number(profileWeight.value.replace(",", ".")) : null;
  const bloodType = profileBloodType.value.trim() || null;
  const body = { name };
  if (birthYear) body.birth_year = birthYear;
  if (height) body.height_cm = height;
  if (weight) body.weight_kg = weight;
  if (bloodType) body.blood_type = bloodType;
  return { body, name };
}

async function saveProfile() {
  if (!currentProfileId) {
    showToast(t("profile.notCreated"), "warn");
    return;
  }
  const { body, name } = profilePayload();
  if (!name) {
    showToast(t("profile.needName"), "warn");
    return;
  }
  try {
    const res = await fetch(`/api/profiles/${currentProfileId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    closeProfileModal();
    await loadProfiles();
    showToast(t("profile.updated"), "success");
  } catch (err) {
    showToast(t("profile.errorSave", { msg: err.message }), "error");
  }
}

function isNearBottom() {
  return messagesEl.scrollHeight - messagesEl.scrollTop - messagesEl.clientHeight < 80;
}

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function addMessage(role, text, isError = false) {
  const wrap = document.createElement("div");
  wrap.className = `message ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (isError) bubble.classList.add("error");
  bubble.textContent = text;
  wrap.appendChild(bubble);
  const stickToBottom = isNearBottom();
  messagesEl.appendChild(wrap);
  if (stickToBottom) scrollToBottom();
  return bubble;
}

function makeFigure(img) {
  const fig = document.createElement("figure");
  fig.className = "msg-figure";
  const el = document.createElement("img");
  el.src = img.url;
  el.loading = "lazy";
  el.alt = img.caption || "";
  el.title = t("chat.zoomHint") || "Увеличить";
  el.addEventListener("click", () => openLightbox(el));
  fig.appendChild(el);
  if (img.caption) {
    const cap = document.createElement("figcaption");
    cap.textContent = img.caption;
    fig.appendChild(cap);
  }
  if (img.source) {
    const src = document.createElement("div");
    src.className = "msg-figure-source";
    src.textContent = t("chat.imageFrom") + " " + img.source;
    fig.appendChild(src);
  }
  return fig;
}

let lightboxEl = null;

function openLightbox(img) {
  if (!lightboxEl) {
    lightboxEl = document.createElement("div");
    lightboxEl.className = "lightbox";
    const closeBtn = document.createElement("button");
    closeBtn.className = "lightbox-close";
    closeBtn.textContent = "×";
    closeBtn.setAttribute("aria-label", t("chat.zoomClose") || "Закрыть");
    closeBtn.addEventListener("click", closeLightbox);
    lightboxEl.appendChild(closeBtn);
    const inner = document.createElement("div");
    inner.className = "lightbox-inner";
    lightboxEl.appendChild(inner);
    lightboxEl.addEventListener("click", (e) => {
      if (e.target === lightboxEl) closeLightbox();
    });
    document.body.appendChild(lightboxEl);
  }
  const inner = lightboxEl.querySelector(".lightbox-inner");
  inner.innerHTML = "";
  const big = document.createElement("img");
  big.src = img.src;
  big.alt = img.alt || "";
  inner.appendChild(big);
  const fig = img.closest("figure");
  const cap = fig ? fig.querySelector("figcaption") : null;
  if (cap && cap.textContent) {
    const c = document.createElement("div");
    c.className = "lightbox-caption";
    c.textContent = cap.textContent;
    inner.appendChild(c);
  }
  lightboxEl.classList.add("open");
}

function closeLightbox() {
  if (lightboxEl) lightboxEl.classList.remove("open");
}

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeLightbox();
});

function setComposerBusy(busy) {
  sendBtn.disabled = busy;
  inputEl.disabled = busy;
  if (!busy) inputEl.focus();
}

async function init() {
  for (const m of history) {
    const bubble = addMessage(m.role === "assistant" ? "bot" : m.role, m.content);
    if (m.role === "assistant" && Array.isArray(m.images)) {
      for (const img of m.images) {
        if (img && img.url) bubble.appendChild(makeFigure(img));
      }
    }
  }
  if (history.length) {
    messagesEl.scrollTop = messagesEl.scrollHeight;
    hideSuggestChips();
  }
  try {
    const res = await fetch("/api/config");
    const cfg = await res.json();
    modelLabel.textContent = `${cfg.backend} / ${cfg.model}`;
    modelDot.classList.add("ok");
    renderKiwixStatus(cfg.kiwix);
  } catch {
    modelLabel.textContent = t("chat.noServer");
    modelDot.classList.add("err");
    kiwixLabel.textContent = t("status.kiwix") + ": " + t("chat.noServer");
    kiwixDot.classList.add("err");
  }
}

function renderKiwixStatus(k) {
  if (!k) return;
  if (k.ok) {
    kiwixLabel.textContent = t("status.kiwix") + " / " + (k.zim || k.url || "");
    kiwixDot.classList.add("ok");
  } else {
    kiwixLabel.textContent = t("status.kiwix") + ": " + t("status.kiwixNoConn");
    kiwixDot.classList.add("err");
  }
}

async function send() {
  const text = inputEl.value.trim();
  if (!text || sendBtn.disabled) return;

  hideSuggestChips();
  inputEl.value = "";
  autoResize();

  addMessage("user", text);
  pushHistory("user", text);
  await sendWithText(text);
}

function hideSuggestChips() {
  const chips = document.getElementById("suggest-chips");
  if (chips) chips.classList.add("hidden");
}

function showSuggestChips() {
  const chips = document.getElementById("suggest-chips");
  if (chips) chips.classList.remove("hidden");
}

async function sendWithText(text) {
  const botBubble = addMessage("bot", "");
  setComposerBusy(true);

  const { acc, error, images } = await streamIntoBubble(
    "/api/chat",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: history }),
    },
    botBubble
  );

  if (!error) {
    pushHistory("assistant", acc, images);
  }
  setComposerBusy(false);
}

async function streamIntoBubble(url, options, bubble) {
  let acc = "";
  let error = false;
  const images = [];
  const addedUrls = new Set();
  const textEl = document.createElement("div");
  textEl.className = "msg-text";
  bubble.appendChild(textEl);

  try {
    const res = await fetch(url, options);
    if (!res.ok || !res.body) {
      let detail = `HTTP ${res.status}`;
      try {
        const data = await res.json();
        if (data.detail) detail = data.detail;
      } catch { /* не JSON */ }
      throw new Error(detail);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";

      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith("data:")) continue;
        const payload = line.slice(5).trim();
        if (payload === "[DONE]") continue;

        try {
          const msg = JSON.parse(payload);
          if (msg.content) {
            acc += msg.content;
            textEl.textContent = acc;
          }
          if (Array.isArray(msg.images)) {
            for (const img of msg.images) {
              if (!img || !img.url || addedUrls.has(img.url)) continue;
              addedUrls.add(img.url);
              images.push(img);
              bubble.appendChild(makeFigure(img));
            }
          }
          if (isNearBottom()) scrollToBottom();
        } catch {
          /* игнорируем битые чанки */
        }
      }
    }
  } catch (err) {
    error = true;
    bubble.textContent = `${t("error.prefix")} ${err.message}`;
    bubble.classList.add("error");
  }

  return { acc, error, images };
}

async function analyzeNow() {
  const text = t("analysis.now");
  addMessage("user", text);
  pushHistory("user", text);

  const botBubble = addMessage("bot", t("analysis.preparing"));
  setComposerBusy(true);

  const { acc, error } = await streamIntoBubble(
    `/api/analysis?${profileQuery()}`,
    { method: "POST" },
    botBubble
  );

  if (!error) {
    pushHistory("assistant", acc);
    showToast(t("analysis.ready"), "success");
  }
  setComposerBusy(false);
}

function autoResize() {
  inputEl.style.height = "auto";
  inputEl.style.height = Math.min(inputEl.scrollHeight, 160) + "px";
}

function setStatus(text, isError = false) {
  extractStatus.textContent = text;
  extractStatus.classList.toggle("err", isError);
}

function showExtractPanel(title) {
  extractTitle.textContent = title;
  extractPanel.classList.remove("hidden");
  extractResult.innerHTML = "";
}

function hideExtractPanel() {
  extractPanel.classList.add("hidden");
  extractData = null;
}

function statusLabel(status) {
  const map = {
    normal: "status.normal",
    high: "status.high",
    low: "status.low",
    critical: "status.critical",
    suspect: "status.suspect",
    unknown: "status.unknown",
  };
  return map[status] ? t(map[status]) : "—";
}

function statusPhrase(status) {
  const map = {
    normal: "phrase.normal",
    high: "phrase.high",
    elevated: "phrase.elevated",
    low: "phrase.low",
    unknown: "phrase.unknown",
  };
  return map[status] ? t(map[status]) : t("phrase.unknown");
}

function showToast(message, type = "info", timeout = 6000) {
  const container = document.getElementById("toasts");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = message;
  container.appendChild(el);
  const dismiss = () => {
    el.classList.add("leaving");
    setTimeout(() => el.remove(), 250);
  };
  el.addEventListener("click", dismiss);
  setTimeout(dismiss, timeout);
}

function switchView(view) {
  navItems.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.view === view && !btn.disabled);
  });
  chatView.classList.toggle("hidden", view !== "chat");
  cardView.classList.toggle("hidden", view !== "card");
  articlesView.classList.toggle("hidden", view !== "articles");
  notesView.classList.toggle("hidden", view !== "notes");
  if (view === "card") loadRecords();
  if (view === "articles") loadArticles();
  if (view === "notes") loadNotes();
}

async function saveRecord(record) {
  const res = await fetch("/api/records", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(record),
  });
  if (!res.ok) {
    let detail = t("record.saveError");
    try {
      const data = await res.json();
      if (Array.isArray(data.detail)) {
        detail = data.detail
          .map((e) => `${e.loc ? e.loc[e.loc.length - 1] : "?"}: ${e.msg || ""}`)
          .join("; ");
      } else if (data.detail) {
        detail = data.detail;
      }
    } catch { /* не JSON */ }
    throw new Error(detail);
  }
  return res.json();
}

async function loadRecords() {
  recordsEl.innerHTML = `<div class="record-empty">${t("card.loading")}</div>`;
  loadReminders();
  try {
    const res = await fetch(`/api/records?${profileQuery()}`);
    const records = await res.json();
    renderRecords(records);
  } catch (err) {
    recordsEl.innerHTML = `<div class="record-empty">${escapeHtml(t("card.errorLoad", { msg: err.message }))}</div>`;
  }
}

function renderRecords(records) {
  if (!records.length) {
    recordsEl.innerHTML =
      `<div class="record-empty">${t("card.empty")}</div>`;
    return;
  }
  recordsEl.innerHTML = "";
  for (const rec of records) {
    const card = document.createElement("div");
    card.className = "record-card";

    const head = document.createElement("div");
    head.className = "record-head";

    const meta = document.createElement("div");
    meta.className = "record-meta";
    const date = document.createElement("div");
    date.className = "record-date";
    date.textContent = rec.created_at;
    const source = document.createElement("div");
    source.className = "record-source";
    source.textContent = rec.source_name + ` (${t("card.markers", { n: rec.marker_count })})`;
    if (rec.critical_count > 0) {
      const critBadge = document.createElement("span");
      critBadge.className = "critical-badge record-critical";
      critBadge.textContent = t("card.critical", { n: rec.critical_count });
      critBadge.title = t("card.criticalTitle");
      source.appendChild(critBadge);
    }
    meta.append(date, source);

    const actions = document.createElement("div");
    actions.className = "record-actions";
    const del = document.createElement("button");
    del.className = "danger-btn";
    del.textContent = t("card.delete");
    del.addEventListener("click", () => deleteRecord(rec.id));
    const view = document.createElement("button");
    view.className = "action-btn";
    view.textContent = t("card.details");
    view.addEventListener("click", () => toggleRecordDetails(rec.id, card));
    actions.append(del, view);

    head.append(meta, actions);
    card.appendChild(head);

    const summary = document.createElement("div");
    summary.className = "summary";
    summary.textContent = rec.summary || t("card.noSummary");
    card.appendChild(summary);

    const details = document.createElement("div");
    details.className = "record-details";
    details.id = `record-details-${rec.id}`;
    details.style.display = "none";
    details.innerHTML = `<div class="record-empty">${t("card.loading")}</div>`;
    card.appendChild(details);

    recordsEl.appendChild(card);
  }
}

async function toggleRecordDetails(id, card) {
  const details = card.querySelector(`#record-details-${id}`);
  const btn = card.querySelector(".record-actions .action-btn");
  if (details.style.display !== "none") {
    details.style.display = "none";
    btn.textContent = t("card.details");
    return;
  }
  try {
    const res = await fetch(`/api/records/${id}`);
    const rec = await res.json();
    details.innerHTML = buildMarkersTable(rec.markers || []);
    details.style.display = "";
    btn.textContent = t("card.collapse");
  } catch (err) {
    details.innerHTML = `<div class="record-empty">${escapeHtml(t("card.error", { msg: err.message }))}</div>`;
  }
}

function buildMarkersTable(markers) {
  const table = document.createElement("table");
  table.className = "markers-table";
  table.innerHTML =
    "<thead><tr><th>" + t("markers.table.name") + "</th><th>" + t("markers.table.value") + "</th><th>" + t("markers.table.norm") + "</th><th>" + t("markers.table.status") + "</th></tr></thead>";
  const tbody = document.createElement("tbody");
  if (!markers.length) {
    tbody.innerHTML = '<tr><td colspan="4">' + t("markers.table.none") + "</td></tr>";
  } else {
    for (const m of markers) {
      const st = m.status || "unknown";
      const suspect = !!(m.validation_message || m.validation);
      const stClass = m.critical ? "critical" : (suspect ? "suspect" : st);
      const tr = document.createElement("tr");
      if (m.critical) tr.className = "marker-critical-row";
      if (suspect) tr.className = (tr.className ? tr.className + " " : "") + "marker-suspect-row";
      const warning = suspect
        ? `<div class="marker-warning">${escapeHtml(m.validation_message || t("markers.table.suspectDefault"))}</div>`
        : "";
      tr.innerHTML = `
        <td>${escapeHtml(m.name || "")}${m.critical ? ` <span class="critical-badge" title="${t("markers.table.criticalTitle")}">⚠</span>` : ""}${suspect ? ` <span class="suspect-badge" title="${t("markers.table.suspectTitle")}">?</span>` : ""}</td>
        <td>${escapeHtml(m.value_raw ?? "")} ${escapeHtml(m.unit || "")}${warning}</td>
        <td>${escapeHtml(m.reference_range || "—")}</td>
        <td><span class="marker-status ${stClass}">${statusLabel(stClass)}</span></td>`;
      tbody.appendChild(tr);
    }
  }
  table.appendChild(tbody);
  return table;
}

async function deleteRecord(id) {
  if (!confirm(t("card.deleteConfirm"))) return;
  await fetch(`/api/records/${id}`, { method: "DELETE" });
  loadRecords();
}

navItems.forEach((btn) => {
  if (!btn.disabled) {
    btn.addEventListener("click", () => switchView(btn.dataset.view));
  }
});
btnRefresh.addEventListener("click", loadRecords);

const TREND_KEYS = {
  up: "trend.up",
  down: "trend.down",
  stable: "trend.stable",
  single: "trend.single",
};

function sparklineSvg(points, w = 120, h = 40) {
  const vals = points.map((p) => p.value);
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const range = max - min || 1;
  const step = w / Math.max(vals.length - 1, 1);
  const coords = vals.map((v, i) => {
    const x = i * step;
    const y = h - 4 - ((v - min) / range) * (h - 8);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" class="sparkline">
    <polyline points="${coords.join(" ")}" fill="none" stroke="#38bdf8" stroke-width="2"/>
  </svg>`;
}

function renderTrends(trends) {
  if (!trends.length) {
    trendsEl.innerHTML =
      `<div class="record-empty">${t("trend.empty")}</div>`;
    return;
  }
  trendsEl.innerHTML = "";
  for (const t of trends) {
    const card = document.createElement("div");
    card.className = "trend-card";
    const head = document.createElement("div");
    head.className = "trend-head";
    const name = document.createElement("div");
    name.className = "trend-name";
    name.textContent = `${t.name}${t.unit ? ", " + t.unit : ""}`;
    const badge = document.createElement("div");
    badge.className = `trend-badge ${t.trend}`;
    badge.textContent = TREND_KEYS[t.trend] ? t(TREND_KEYS[t.trend]) : t.trend;
    head.append(name, badge);

    const value = document.createElement("div");
    value.className = "trend-value";
    value.textContent = String(t.latest);

    const meta = document.createElement("div");
    meta.className = "trend-meta";
    const firstDate = t.points[0].date;
    const lastDate = t.points[t.points.length - 1].date;
    meta.textContent = t("trend.measurements", { n: t.count, from: firstDate, to: lastDate });

    card.append(head, value, meta);
    card.insertAdjacentHTML("beforeend", sparklineSvg(t.points));
    trendsEl.appendChild(card);
  }
}

let trendsVisible = false;
async function toggleTrends() {
  trendsVisible = !trendsVisible;
  trendsEl.classList.toggle("hidden", !trendsVisible);
  btnTrends.textContent = trendsVisible ? t("card.hideTrends") : t("card.trends");
  if (trendsVisible) {
    try {
      const res = await fetch(`/api/records/trends?${profileQuery()}`);
      const trends = await res.json();
      renderTrends(trends);
    } catch (err) {
      trendsEl.innerHTML = `<div class="record-empty">${escapeHtml(t("card.error", { msg: err.message }))}</div>`;
    }
  }
}
btnTrends.addEventListener("click", toggleTrends);

async function exportPdf() {
  try {
    const res = await fetch(`/api/records/export.pdf?${profileQuery()}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "med-card.pdf";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (err) {
    alert(t("card.pdfError", { msg: err.message }));
  }
}
btnExportPdf.addEventListener("click", exportPdf);

function daysSince(dateStr) {
  if (!dateStr) return null;
  const d = new Date(dateStr.replace(" ", "T"));
  if (isNaN(d.getTime())) return null;
  return Math.floor((Date.now() - d.getTime()) / (1000 * 60 * 60 * 24));
}

async function loadReminders() {
  if (!remindersEl.offsetParent) return;
  remindersEl.innerHTML =
    `<div class="record-empty">${t("reminders.loading")}</div>`;
  try {
    const res = await fetch(`/api/reminders?${profileQuery()}`);
    const reminders = await res.json();
    renderReminders(reminders);
  } catch (err) {
    remindersEl.innerHTML =
      `<div class="record-empty">${escapeHtml(t("reminders.errorLoad", { msg: err.message }))}</div>`;
  }
}

function renderReminders(reminders) {
  if (!reminders.length) {
    remindersEl.innerHTML =
      `<div class="reminders-head"><span class="reminders-title">${t("reminders.title")}</span>
      <button class="action-btn" id="reminder-add-empty">${t("reminders.add")}</button></div>
      <div class="record-empty">${t("reminders.empty")}</div>`;
    const btn = document.getElementById("reminder-add-empty");
    if (btn) btn.addEventListener("click", openReminderModal);
    return;
  }
  remindersEl.innerHTML =
    `<div class="reminders-head"><span class="reminders-title">${t("reminders.title")}</span>
    <button class="action-btn" id="reminder-add-top">${t("reminders.add")}</button></div>
    <div class="reminders-grid"></div>`;
  document.getElementById("reminder-add-top").addEventListener("click", openReminderModal);
  const grid = remindersEl.querySelector(".reminders-grid");
  for (const r of reminders) {
    const row = document.createElement("div");
    row.className = "reminder-row";

    const info = document.createElement("div");
    info.className = "reminder-info";
    const name = document.createElement("div");
    name.className = "reminder-name";
    name.textContent = r.marker_name;
    const meta = document.createElement("div");
    meta.className = "reminder-meta";
    const days = daysSince(r.last_reported);
    if (days === null) {
      meta.textContent = t("reminders.noValue", { n: r.interval_days });
    } else if (days >= r.interval_days) {
      meta.innerHTML =
        `${t("reminders.every", { n: r.interval_days })} · <span class="reminder-due">${t("reminders.due", { n: days })}</span>`;
    } else {
      meta.textContent = t("reminders.left", { n: r.interval_days, m: r.interval_days - days });
    }
    info.append(name, meta);

    const actions = document.createElement("div");
    actions.className = "reminder-actions";
    const del = document.createElement("button");
    del.className = "danger-btn";
    del.textContent = t("card.delete");
    del.addEventListener("click", () => deleteReminder(r.id));
    actions.appendChild(del);

    row.append(info, actions);
    grid.appendChild(row);
  }
}

function openReminderModal() {
  fillReminderMarkerList();
  reminderMarker.value = "";
  reminderInterval.value = "30";
  reminderModal.classList.remove("hidden");
  reminderMarker.focus();
}

function closeReminderModal() {
  reminderModal.classList.add("hidden");
}

async function fillReminderMarkerList() {
  try {
    const res = await fetch(`/api/records/trends?${profileQuery()}`);
    const trends = await res.json();
    reminderMarkerList.innerHTML = (trends || [])
      .map((t) => `<option value="${escapeHtml(t.name)}"></option>`)
      .join("");
  } catch { /* пустой список — ок */ }
}

async function saveReminder() {
  const marker = reminderMarker.value.trim();
  const interval = Math.max(1, Math.min(3650, Number(reminderInterval.value) || 30));
  if (!marker) {
    showToast(t("reminders.needMarker"), "warn");
    return;
  }
  const body = { marker_name: marker, interval_days: interval };
  if (currentProfileId) body.profile_id = currentProfileId;
  try {
    const res = await fetch("/api/reminders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    closeReminderModal();
    loadReminders();
    showToast(t("reminders.added"), "success");
  } catch (err) {
    showToast(t("reminders.errorAdd", { msg: err.message }), "error");
  }
}

async function deleteReminder(id) {
  if (!confirm(t("reminders.deleteConfirm"))) return;
  try {
    const res = await fetch(`/api/reminders/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    loadReminders();
    showToast(t("reminders.deleted"), "success");
  } catch (err) {
    showToast(t("reminders.errorDel", { msg: err.message }), "error");
  }
}

function setArticleStatus(text, isError = false) {
  articleStatus.textContent = text;
  articleStatus.classList.toggle("err", isError);
}

async function loadArticles() {
  articlesList.innerHTML = `<div class="record-empty">${t("card.loading")}</div>`;
  setArticleStatus("");
  try {
    const res = await fetch("/api/articles");
    const articles = await res.json();
    renderArticles(articles);
  } catch (err) {
    articlesList.innerHTML = `<div class="record-empty">${escapeHtml(t("articles.error", { msg: err.message }))}</div>`;
  }
}

function renderArticles(articles) {
  if (!articles.length) {
    articlesList.innerHTML =
      `<div class="record-empty">${t("articles.empty")}</div>`;
    return;
  }
  articlesList.innerHTML = "";
  for (const a of articles) {
    const card = document.createElement("div");
    card.className = "record-card";

    const head = document.createElement("div");
    head.className = "record-head";
    const meta = document.createElement("div");
    meta.className = "record-meta";
    const date = document.createElement("div");
    date.className = "record-date";
    date.textContent = a.filename;
    const info = document.createElement("div");
    info.className = "record-source";
    info.textContent = `${a.uploaded_at} · ${t("articles.chunks", { n: a.chunk_count })}`;
    meta.append(date, info);

    const actions = document.createElement("div");
    actions.className = "article-actions";
    const del = document.createElement("button");
    del.className = "danger-btn";
    del.textContent = t("card.delete");
    del.addEventListener("click", () => deleteArticle(a.id));
    const ask = document.createElement("button");
    ask.className = "action-btn";
    ask.textContent = t("articles.discuss");
    ask.addEventListener("click", () => askAboutArticle(a));
    actions.append(ask, del);

    head.append(meta, actions);
    card.appendChild(head);

    const summary = document.createElement("div");
    summary.className = "summary";
    summary.textContent = a.summary || t("articles.noSummary");
    card.appendChild(summary);

    articlesList.appendChild(card);
  }
}

async function deleteArticle(id) {
  if (!confirm(t("articles.deleteConfirm"))) return;
  await fetch(`/api/articles/${id}`, { method: "DELETE" });
  loadArticles();
}

async function askAboutArticle(article) {
  switchView("chat");
  currentArticleId = article.id;

  let fragmentsText = "";
  try {
    const res = await fetch(`/api/articles/${article.id}/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: t("articles.askQuery"),
        limit: 30,
      }),
    });
    if (res.ok) {
      const chunks = await res.json();
      if (chunks.length) {
        fragmentsText = chunks.map((c) => c.chunk).join("\n\n");
      }
    }
  } catch { /* без фрагментов */ }

  const fragments = fragmentsText
    ? t("articles.askFragments", { fragments: fragmentsText })
    : t("articles.askSummary", { summary: article.summary || "—" });
  const text = t("articles.askAbout", { name: article.filename, fragments });

  addMessage("user", text);
  pushHistory("user", text);
  sendWithText(text);
}

async function uploadArticle(file) {
  setArticleStatus(t("articles.processing", { name: file.name }));
  const fd = new FormData();
  fd.append("file", file);
  try {
    const res = await fetch("/api/articles", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) {
      setArticleStatus(t("articles.error", { msg: data.detail || t("error.unknown") }), true);
      return;
    }
    setArticleStatus(t("articles.added", { name: data.filename, n: data.chunk_count }));
    loadArticles();
  } catch (err) {
    setArticleStatus(t("articles.uploadError", { msg: err.message }), true);
  }
}

async function searchArticles() {
  const q = articleQuery.value.trim();
  if (!q) return;
  setArticleStatus(t("articles.searching"));
  try {
    const res = await fetch("/api/articles/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: q, limit: 5 }),
    });
    const data = await res.json();
    if (!res.ok) {
      setArticleStatus(t("articles.error", { msg: data.detail || t("error.unknown") }), true);
      return;
    }
    renderSearchResults(q, data);
  } catch (err) {
    setArticleStatus(t("articles.searchError", { msg: err.message }), true);
  }
}

function renderSearchResults(query, results) {
  if (!results.length) {
    setArticleStatus(t("articles.noResults", { q: query }));
    articlesList.innerHTML =
      `<div class="record-empty">${t("articles.tryAgain")}</div>`;
    return;
  }
  setArticleStatus(t("articles.results", { q: query }));
  articlesList.innerHTML = "";
  for (const r of results) {
    const card = document.createElement("div");
    card.className = "record-card";

    const meta = document.createElement("div");
    meta.className = "record-meta";
    const title = document.createElement("div");
    title.className = "record-date";
    title.textContent = r.title;
    const badge = document.createElement("div");
    badge.className = "article-meta";
    badge.innerHTML =
      `<span class="article-badge">${t("articles.badge", { id: r.article_id })}</span>` +
      (r.distance != null
        ? `<span class="article-distance">${t("articles.distance", { d: r.distance })}</span>`
        : "");
    meta.append(title, badge);

    const chunk = document.createElement("div");
    chunk.className = "summary";
    chunk.textContent = r.chunk;

    const actions = document.createElement("div");
    actions.className = "article-actions";
    const ask = document.createElement("button");
    ask.className = "primary-btn";
    ask.textContent = t("articles.askFragment");
    ask.addEventListener("click", () => {
      switchView("chat");
      currentArticleId = r.article_id;
      const text = t("articles.askAboutFragment", { title: r.title, chunk: r.chunk });
      addMessage("user", text);
      pushHistory("user", text);
      sendWithText(text);
    });
    actions.appendChild(ask);

    card.append(meta, chunk, actions);
    articlesList.appendChild(card);
  }
}

function setNotesStatus(text, isError = false) {
  notesStatus.textContent = text;
  notesStatus.classList.toggle("err", isError);
}

async function loadNotes() {
  notesList.innerHTML = `<div class="record-empty">${t("card.loading")}</div>`;
  setNotesStatus("");
  try {
    const res = await fetch("/api/notes");
    const notes = await res.json();
    renderNotes(notes);
  } catch (err) {
    notesList.innerHTML = `<div class="record-empty">${escapeHtml(t("notes.error", { msg: err.message }))}</div>`;
  }
}

function renderNotes(notes) {
  if (!notes.length) {
    notesList.innerHTML =
      `<div class="record-empty">${t("notes.empty")}</div>`;
    return;
  }
  notesList.innerHTML = "";
  for (const n of notes) {
    const card = document.createElement("div");
    card.className = "record-card";

    const head = document.createElement("div");
    head.className = "record-head";

    const meta = document.createElement("div");
    meta.className = "record-meta";
    const date = document.createElement("div");
    date.className = "record-date";
    date.textContent = n.created_at;
    const source = document.createElement("div");
    source.className = "record-source";
    source.textContent = n.filename ? t("notes.article", { name: n.filename }) : t("notes.noArticle");
    meta.append(date, source);

    const actions = document.createElement("div");
    actions.className = "record-actions";
    const del = document.createElement("button");
    del.className = "danger-btn";
    del.textContent = t("card.delete");
    del.addEventListener("click", () => deleteNote(n.id));
    actions.appendChild(del);

    head.append(meta, actions);
    card.appendChild(head);

    const body = document.createElement("div");
    body.className = "summary note-content";
    body.textContent = n.content;
    card.appendChild(body);

    notesList.appendChild(card);
  }
}

async function deleteNote(id) {
  if (!confirm(t("notes.deleteConfirm"))) return;
  await fetch(`/api/notes/${id}`, { method: "DELETE" });
  loadNotes();
}

async function fillNoteArticleSelect() {
  const prev = noteArticle.value;
  noteArticle.innerHTML = `<option value="">${t("notes.noArticle")}</option>`;
  try {
    const res = await fetch("/api/articles");
    const articles = await res.json();
    for (const a of articles) {
      const opt = document.createElement("option");
      opt.value = String(a.id);
      opt.textContent = a.filename;
      noteArticle.appendChild(opt);
    }
    if (currentArticleId !== null && articles.some((a) => a.id === currentArticleId)) {
      noteArticle.value = String(currentArticleId);
    } else if (prev) {
      noteArticle.value = prev;
    }
  } catch { /* без списка статей — только без привязки */ }
}

function openNoteModal(text) {
  noteContent.value = text;
  fillNoteArticleSelect();
  noteModal.classList.remove("hidden");
  noteContent.focus();
}

function closeNoteModal() {
  noteModal.classList.add("hidden");
}

async function saveNote() {
  const content = noteContent.value.trim();
  if (!content) {
    setNotesStatus(t("notes.emptyError"), true);
    return;
  }
  const articleId = noteArticle.value ? Number(noteArticle.value) : null;
  try {
    const res = await fetch("/api/notes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ article_id: articleId, content }),
    });
    const data = await res.json();
    if (!res.ok) {
      showToast(t("notes.errorSave", { msg: data.detail || t("error.unknown") }), "error");
      return;
    }
    closeNoteModal();
    showToast(t("notes.saved"), "success");
  } catch (err) {
    showToast(t("notes.errorSave", { msg: err.message }), "error");
  }
}

btnRefreshNotes.addEventListener("click", loadNotes);
btnNewNote.addEventListener("click", () => openNoteModal(""));
btnSaveNote.addEventListener("click", () => {
  const lastAssistant = [...history].reverse().find((m) => m.role === "assistant");
  openNoteModal(lastAssistant ? lastAssistant.content : "");
});
noteClose.addEventListener("click", closeNoteModal);
noteCancel.addEventListener("click", closeNoteModal);
noteSave.addEventListener("click", saveNote);
noteModal.addEventListener("click", (e) => {
  if (e.target === noteModal) closeNoteModal();
});

function setModelsStatus(text, isError = false) {
  modelsStatus.textContent = text;
  modelsStatus.classList.toggle("err", isError);
}

function setKiwixStatus(text, isError = false) {
  if (!kiwixStatus) return;
  kiwixStatus.textContent = text;
  kiwixStatus.classList.toggle("err", isError);
}

let availableModels = [];

function setupModelPicker(inputEl) {
  const wrap = document.createElement("div");
  wrap.className = "model-picker";
  inputEl.parentNode.insertBefore(wrap, inputEl);
  wrap.appendChild(inputEl);

  const list = document.createElement("ul");
  list.className = "model-options";
  wrap.appendChild(list);

  function render(filterText) {
    list.innerHTML = "";
    const q = (filterText ?? "").trim().toLowerCase();
    const filtered = q
      ? availableModels.filter((m) => m.toLowerCase().includes(q))
      : availableModels.slice();
    if (!filtered.length) {
      const li = document.createElement("li");
      li.className = "empty";
      li.textContent = availableModels.length
        ? t("settings.nothingFound")
        : t("settings.notFound");
      list.appendChild(li);
      return;
    }
    for (const m of filtered) {
      const li = document.createElement("li");
      li.textContent = m;
      li.addEventListener("mousedown", (e) => {
        e.preventDefault();
        inputEl.value = m;
        list.classList.remove("open");
      });
      list.appendChild(li);
    }
  }

  inputEl.addEventListener("focus", () => {
    render("");
    list.classList.add("open");
  });
  inputEl.addEventListener("input", () => {
    render(inputEl.value);
    list.classList.add("open");
  });
  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Escape") list.classList.remove("open");
  });
  document.addEventListener("click", (e) => {
    if (!wrap.contains(e.target)) list.classList.remove("open");
  });
}

function setModelsDatalist(models) {
  availableModels = models || [];
}

async function openSettings() {
  try {
    const res = await fetch("/api/settings");
    const data = await res.json();
    setOllamaUrl.value = data.ollama_base_url || "";
    setKiwixUrl.value = data.kiwix_base_url || "";
    setKiwixZim.value = data.kiwix_zim_name || "";
    setChatModel.value = data.chat_model || "";
    setVisionModel.value = data.vision_model || "";
    setEmbedModel.value = data.embed_model || "";
    setNumCtx.value = data.num_ctx || "";
    const dirEl = document.getElementById("data-dir-path");
    if (dirEl) dirEl.textContent = data.data_dir || "—";
    settingsModal.classList.remove("hidden");
    setModelsStatus("");
    refreshOllamaModels();
  } catch (err) {
    setModelsStatus(t("settings.error", { msg: err.message }), true);
  }
}

async function refreshKiwixBooks() {
  const url = setKiwixUrl.value.trim();
  if (!url) {
    setKiwixStatus(t("settings.kiwixUrl") + ": " + t("settings.nothingFound"), true);
    return;
  }
  setKiwixStatus(t("settings.checkingBooks"));
  btnKiwixBooks.disabled = true;
  try {
    const res = await fetch("/api/settings/kiwix-books", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kiwix_base_url: url }),
    });
    const data = await res.json();
    if (!res.ok) {
      setKiwixStatus(t("settings.error", { msg: data.detail || t("error.unknown") }), true);
      return;
    }
    const books = data.books || [];
    if (!setKiwixZim.value && books.length) {
      const wiki = books.find((b) => b.includes("wikipedia") && b.includes("_en_")) || books[0];
      setKiwixZim.value = wiki;
    }
    setKiwixStatus(t("settings.booksFound", { n: books.length }));
  } catch (err) {
    setKiwixStatus(t("settings.error", { msg: err.message }), true);
  } finally {
    btnKiwixBooks.disabled = false;
  }
}

function closeSettings() {
  settingsModal.classList.add("hidden");
}

document.getElementById("btn-copy-dir")?.addEventListener("click", async () => {
  const dirEl = document.getElementById("data-dir-path");
  if (!dirEl || !dirEl.textContent || dirEl.textContent === "—") return;
  try {
    await navigator.clipboard.writeText(dirEl.textContent);
    dirEl.classList.add("copied");
    setTimeout(() => dirEl.classList.remove("copied"), 1200);
  } catch (err) {
    /* clipboard недоступен */
  }
});

const btnBackupExport = document.getElementById("btn-backup-export");
const btnBackupImport = document.getElementById("btn-backup-import");
const backupFileInput = document.getElementById("backup-file-input");
const backupStatus = document.getElementById("backup-status");

function setBackupStatus(text, isError) {
  if (!backupStatus) return;
  backupStatus.textContent = text;
  backupStatus.style.color = isError ? "var(--danger, #e5484d)" : "var(--accent, #3b82f6)";
}

btnBackupExport?.addEventListener("click", async () => {
  try {
    setBackupStatus(t("settings.creatingBackup"));
    btnBackupExport.disabled = true;
    const res = await fetch("/api/backup/export");
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || `HTTP ${res.status}`);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "zelvera-backup.zip";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    setBackupStatus(t("settings.backupSaved"));
  } catch (err) {
    setBackupStatus(t("settings.error", { msg: err.message }), true);
  } finally {
    btnBackupExport.disabled = false;
  }
});

btnBackupImport?.addEventListener("click", () => {
  backupFileInput.value = "";
  backupFileInput.click();
});

backupFileInput?.addEventListener("change", async () => {
  const file = backupFileInput.files && backupFileInput.files[0];
  if (!file) return;
  const confirmed = confirm(t("settings.restoreConfirm"));
  if (!confirmed) {
    backupFileInput.value = "";
    return;
  }
  const form = new FormData();
  form.append("file", file);
  try {
    setBackupStatus(t("settings.restoring"));
    btnBackupImport.disabled = true;
    const res = await fetch("/api/backup/import", { method: "POST", body: form });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    setBackupStatus(t("settings.restored", { names: (data.restored || []).join(", ") }));
    loadProfiles();
    if (!cardView.classList.contains("hidden")) loadRecords();
  } catch (err) {
    setBackupStatus(t("settings.error", { msg: err.message }), true);
  } finally {
    btnBackupImport.disabled = false;
    backupFileInput.value = "";
  }
});

async function refreshOllamaModels() {
  setModelsStatus(t("settings.fetchingModels"));
  try {
    const res = await fetch("/api/settings/ollama-models", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ollama_base_url: setOllamaUrl.value.trim() }),
    });
    const data = await res.json();
    if (!res.ok) {
      setModelsStatus(t("settings.error", { msg: data.detail || t("error.unknown") }), true);
      return;
    }
    setModelsDatalist(data.models || []);
    setModelsStatus(t("settings.foundModels", { n: (data.models || []).length }));
  } catch (err) {
    setModelsStatus(t("settings.error", { msg: err.message }), true);
  }
}

async function saveSettings() {
  const body = {
    ollama_base_url: setOllamaUrl.value.trim(),
    kiwix_base_url: setKiwixUrl.value.trim(),
    kiwix_zim_name: setKiwixZim.value.trim(),
    chat_model: setChatModel.value.trim(),
    vision_model: setVisionModel.value.trim(),
    embed_model: setEmbedModel.value.trim(),
    num_ctx: setNumCtx.value.trim(),
  };
  try {
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) {
      setModelsStatus(t("settings.error", { msg: data.detail || t("error.unknown") }), true);
      return;
    }
    modelLabel.textContent = `${data.backend} / ${data.chat_model}`;
    closeSettings();
  } catch (err) {
    setModelsStatus(t("settings.error", { msg: err.message }), true);
  }
}

btnSettings.addEventListener("click", openSettings);
settingsClose.addEventListener("click", closeSettings);
settingsCancel.addEventListener("click", closeSettings);
settingsSave.addEventListener("click", saveSettings);
btnRefreshModels.addEventListener("click", refreshOllamaModels);
btnKiwixBooks.addEventListener("click", refreshKiwixBooks);
settingsModal.addEventListener("click", (e) => {
  if (e.target === settingsModal) closeSettings();
});

function escapeLogHtml(s) {
  return String(s).replace(/[&<>]/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;",
  }[c]));
}

async function openLogs() {
  logsModal.classList.remove("hidden");
  await refreshLogs();
}

function closeLogs() {
  logsModal.classList.add("hidden");
}

function switchLogsTab(tab) {
  logsTab = tab;
  modalTabs.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  });
  auditFilters.classList.toggle("hidden", tab !== "audit");
  refreshLogs();
}

async function refreshLogs() {
  logsContent.innerHTML = `<div class="record-empty">${t("card.loading")}</div>`;
  if (logsTab === "audit") {
    await refreshAudit();
    return;
  }
  try {
    const res = await fetch("/api/logs");
    const data = await res.json();
    const lines = (data.logs || []).map((line) => {
      let cls = "";
      if (/\bERROR\b/.test(line)) cls = "err";
      else if (/\bWARN|WARNING\b/.test(line)) cls = "warn";
      return `<div class="${cls}">${escapeLogHtml(line)}</div>`;
    });
    logsContent.innerHTML = lines.length
      ? lines.join("")
      : `<div class="record-empty">${t("logs.empty")}</div>`;
  } catch (err) {
    logsContent.innerHTML = `<div class="record-empty">${escapeLogHtml(t("logs.errorLoad", { msg: err.message }))}</div>`;
  }
}

function populateAuditFilter(actions, labels, selected) {
  auditActionFilter.innerHTML =
    `<option value="">${t("logs.allActions")}</option>` +
    actions
      .map(
        (a) =>
          `<option value="${escapeHtml(a.action)}" ${
            selected === a.action ? "selected" : ""
          }>${escapeHtml(labels[a.action] || a.action)} (${a.count})</option>`
      )
      .join("");
}

async function refreshAudit() {
  try {
    const action = auditActionFilter.value || "";
    const res = await fetch(`/api/audit?action=${encodeURIComponent(action)}&limit=500`);
    const data = await res.json();
    const items = data.items || [];
    if (!action) {
      populateAuditFilter(data.actions || [], data.labels || {}, "");
    }
    if (!items.length) {
      logsContent.innerHTML =
        `<div class="record-empty">${t("logs.auditEmpty")}</div>`;
      return;
    }
    const rows = items
      .map((it) => {
        const label = (data.labels && data.labels[it.action]) || it.action;
        const cls = it.action === "error" ? "err" : "";
        return (
          `<div class="audit-row ${cls}">` +
          `<span class="audit-time">${escapeLogHtml(it.created_at)}</span>` +
          `<span class="audit-action">${escapeLogHtml(label)}</span>` +
          `<span class="audit-detail">${escapeLogHtml(it.detail)}</span>` +
          `</div>`
        );
      })
      .join("");
    logsContent.innerHTML = rows;
  } catch (err) {
    logsContent.innerHTML = `<div class="record-empty">${escapeLogHtml(t("logs.errorAudit", { msg: err.message }))}</div>`;
  }
}

async function clearAudit() {
  if (!confirm(t("logs.clearAuditConfirm"))) return;
  try {
    await fetch("/api/audit", { method: "DELETE" });
    auditActionFilter.value = "";
    await refreshAudit();
  } catch (err) {
    showToast(t("logs.errorClearAudit", { msg: err.message }), "error");
  }
}

async function clearJournal() {
  if (!confirm(t("logs.clearJournalConfirm"))) return;
  try {
    const res = await fetch("/api/logs", { method: "DELETE" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    await refreshLogs();
    showToast(t("logs.cleared"), "success");
  } catch (err) {
    showToast(t("logs.errorClear", { msg: err.message }), "error");
  }
}

function downloadLogs() {
  const a = document.createElement("a");
  a.href = "/api/logs/download";
  a.download = "zelvera-app.log";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

btnLogs.addEventListener("click", openLogs);
logsClose.addEventListener("click", closeLogs);
btnLogsRefresh.addEventListener("click", refreshLogs);
btnLogsDownload.addEventListener("click", downloadLogs);
btnLogsClear.addEventListener("click", clearJournal);
logsModal.addEventListener("click", (e) => {
  if (e.target === logsModal) closeLogs();
});
modalTabs.forEach((btn) => {
  btn.addEventListener("click", () => switchLogsTab(btn.dataset.tab));
});
auditActionFilter.addEventListener("change", refreshAudit);
btnAuditClear.addEventListener("click", clearAudit);

setupModelPicker(setChatModel);
setupModelPicker(setVisionModel);
setupModelPicker(setEmbedModel);

btnUploadArticle.addEventListener("click", () => fileArticle.click());
fileArticle.addEventListener("change", () => {
  if (fileArticle.files[0]) uploadArticle(fileArticle.files[0]);
  fileArticle.value = "";
});
btnRefreshArticles.addEventListener("click", loadArticles);
btnArticleSearch.addEventListener("click", searchArticles);
articleQuery.addEventListener("keydown", (e) => {
  if (e.key === "Enter") searchArticles();
});

function renderExtractResult(data) {
  extractData = data;

  const summary = document.createElement("div");
  summary.className = "summary";
  summary.textContent = data.summary || t("extract.noSummary");

  const table = document.createElement("table");
  table.className = "markers-table";
  const thead = document.createElement("thead");
  thead.innerHTML = `<tr><th>${t("markers.table.name")}</th><th>${t("markers.table.value")}</th><th>${t("markers.table.norm")}</th><th>${t("markers.table.status")}</th></tr>`;
  const tbody = document.createElement("tbody");

  const markers = data.markers || [];
  if (markers.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4">${t("extract.noMarkers")}</td></tr>`;
  } else {
    for (const m of markers) {
      const tr = document.createElement("tr");
      const st = m.status || "unknown";
      const suspect = !!m.validation;
      const stClass = suspect ? "suspect" : st;
      if (suspect) tr.className = "marker-suspect-row";
      const warning = suspect
        ? `<div class="marker-warning">${escapeHtml(t("markers.table.suspectDefault"))}</div>`
        : "";
      tr.innerHTML = `
        <td>${escapeHtml(m.name || "")}${suspect ? ` <span class="suspect-badge" title="${t("markers.table.suspectTitle")}">?</span>` : ""}</td>
        <td>${escapeHtml(String(m.value ?? ""))} ${escapeHtml(m.unit || "")}${warning}</td>
        <td>${escapeHtml(m.reference_range || "—")}</td>
        <td><span class="marker-status ${stClass}">${statusLabel(stClass)}</span></td>`;
      tbody.appendChild(tr);
    }
  }

  const raw = document.createElement("div");
  raw.className = "raw-text";
  raw.textContent = t("extract.raw") + "\n" + (data.text || "");

  const actions = document.createElement("div");
  actions.className = "extract-actions";
  const addBtn = document.createElement("button");
  addBtn.className = "primary-btn";
  addBtn.textContent = markers.length ? t("extract.addAsk") : t("extract.ask");
  addBtn.addEventListener("click", askAboutExtract);
  const closeBtn = document.createElement("button");
  closeBtn.className = "action-btn";
  closeBtn.textContent = t("extract.close");
  closeBtn.addEventListener("click", hideExtractPanel);
  actions.append(addBtn, closeBtn);

  extractResult.append(summary, table, raw, actions);
  setStatus(t("extract.found", { n: markers.length }));
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function resizeImage(file, maxSide = 2000, quality = 0.85) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      const scale = Math.min(1, maxSide / Math.max(img.width, img.height));
      const w = Math.round(img.width * scale);
      const h = Math.round(img.height * scale);
      const canvas = document.createElement("canvas");
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(img, 0, 0, w, h);
      URL.revokeObjectURL(url);
      canvas.toBlob(
        (blob) => (blob ? resolve(blob) : reject(new Error(t("extract.imgCompressFail")))),
        "image/jpeg",
        quality
      );
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error(t("extract.imgReadFail")));
    };
    img.src = url;
  });
}

async function prepareUploadFile(file) {
  if (!file.type.startsWith("image/")) return file;
  try {
    const compressed = await resizeImage(file);
    if (compressed.size < file.size) {
      const renamed = new File([compressed], file.name.replace(/\.\w+$/, ".jpg"), {
        type: "image/jpeg",
      });
      return renamed;
    }
  } catch { /* если сжать не вышло — отправим оригинал */ }
  return file;
}

async function uploadDocument(file) {
  const MAX = 50 * 1024 * 1024;

  showExtractPanel(t("extract.processing", { name: file.name }));
  setStatus(t("extract.prepare"));

  let uploadFile = file;
  if (file.type.startsWith("image/")) {
    try {
      uploadFile = await prepareUploadFile(file);
    } catch { /* используем оригинал */ }
  }

  if (uploadFile.size > MAX) {
    hideExtractPanel();
    showToast(
      t("extract.tooLarge", { size: (uploadFile.size / 1024 / 1024).toFixed(1) }),
      "error"
    );
    return;
  }

  const fd = new FormData();
  fd.append("file", uploadFile);

  try {
    const res = await fetch("/api/documents/extract", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) {
      setStatus(t("error.msg", { msg: data.detail || t("error.unknown") }), true);
      return;
    }
    renderExtractResult(data);
    if ((data.markers || []).length) {
      askAboutExtract();
    } else {
      showToast(t("extract.noMarkersFound"), "warn");
    }
  } catch (err) {
    setStatus(t("extract.uploadError", { msg: err.message }), true);
  }
}

async function askAboutExtract() {
  if (!extractData) return;
  const markers = extractData.markers || [];

  const record = {
    source_name: extractData.filename || t("extract.source"),
    summary: extractData.summary || "",
    date: extractData.date || null,
    markers,
    profile_id: currentProfileId,
  };

  if (markers.length) {
    try {
      await saveRecord(record);
    } catch (err) {
      addMessage("bot", t("extract.errorSaveMsg", { msg: err.message }), true);
      showToast(t("extract.errorSave", { msg: err.message }), "error");
      return;
    }

    showToast(t("extract.saved"), "success");
    const deviations = markers.filter(
      (m) => m.status === "elevated" || m.status === "high" || m.status === "low"
    );
    for (const m of deviations.slice(0, 3)) {
      showToast(
        t("extract.deviation", {
          name: m.name,
          phrase: statusPhrase(m.status),
          value: m.value ?? "?",
          unit: m.unit || "",
          ref: m.reference_range || "—",
        }),
        "warn"
      );
    }
    if (deviations.length > 3) {
      showToast(t("extract.moreDeviations", { n: deviations.length - 3 }), "warn");
    }
  }

  const markersText = markers.map((m) =>
    t("extract.markerItem", {
      name: m.name,
      value: m.value ?? "",
      unit: m.unit || "",
      ref: m.reference_range || "—",
      phrase: statusPhrase(m.status),
    })
  ).join("; ");
  const text = markers.length
    ? t("extract.askIntro", { markers: markersText })
    : t("extract.askIntroNoMarkers");

  hideExtractPanel();
  inputEl.value = text;
  autoResize();
  send();
}

btnPhoto.addEventListener("click", () => filePhoto.click());
btnDoc.addEventListener("click", () => fileDoc.click());
btnAnalysis.addEventListener("click", analyzeNow);
filePhoto.addEventListener("change", () => {
  if (filePhoto.files[0]) uploadDocument(filePhoto.files[0]);
  filePhoto.value = "";
});
fileDoc.addEventListener("change", () => {
  if (fileDoc.files[0]) uploadDocument(fileDoc.files[0]);
  fileDoc.value = "";
});
extractClose.addEventListener("click", hideExtractPanel);

inputEl.addEventListener("input", autoResize);
inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    send();
  }
});
sendBtn.addEventListener("click", send);

newChatBtn.addEventListener("click", () => {
  history = [];
  saveHistory();
  messagesEl.innerHTML = "";
  addMessage("bot", t("chat.newDialog"));
  showSuggestChips();
  inputEl.focus();
});

document.querySelectorAll("#suggest-chips .chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    inputEl.value = chip.textContent;
    autoResize();
    send();
  });
});

const btnVoice = document.getElementById("btn-voice");
let recognition = null;
let voiceActive = false;

function setupVoiceInput() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    btnVoice.style.display = "none";
    return;
  }
  recognition = new SR();
  recognition.lang = LANG === "en" ? "en-US" : "ru-RU";
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  recognition.onresult = (e) => {
    const text = e.results[0][0].transcript;
    inputEl.value = (inputEl.value ? inputEl.value + " " : "") + text;
    autoResize();
    inputEl.focus();
    stopVoice();
  };

  recognition.onerror = () => {
    stopVoice();
    showToast(t("voice.error"), "warn");
  };

  recognition.onend = () => stopVoice();

  btnVoice.addEventListener("click", () => {
    if (voiceActive) {
      stopVoice();
    } else {
      startVoice();
    }
  });
}

function startVoice() {
  if (!recognition) return;
  try {
    recognition.start();
    voiceActive = true;
    btnVoice.classList.add("listening");
    btnVoice.title = t("chat.voiceStopTitle");
  } catch { /* повторный запуск — игнорируем */ }
}

function stopVoice() {
  voiceActive = false;
  if (btnVoice) {
    btnVoice.classList.remove("listening");
    btnVoice.title = t("chat.voiceTitle");
  }
  if (recognition) {
    try {
      recognition.stop();
    } catch { /* уже остановлен */ }
  }
}

btnEditProfile.addEventListener("click", openProfileEditModal);
profileClose.addEventListener("click", closeProfileModal);
profileCancel.addEventListener("click", closeProfileModal);
profileSave.addEventListener("click", saveProfile);
profileModal.addEventListener("click", (e) => {
  if (e.target === profileModal) closeProfileModal();
});

reminderClose.addEventListener("click", closeReminderModal);
reminderCancel.addEventListener("click", closeReminderModal);
reminderSave.addEventListener("click", saveReminder);
reminderModal.addEventListener("click", (e) => {
  if (e.target === reminderModal) closeReminderModal();
});

btnExportNotes.addEventListener("click", async () => {
  try {
    const res = await fetch("/api/notes/export.pdf");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "notes.pdf";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (err) {
    alert(t("notes.pdfError", { msg: err.message }));
  }
});

init();
loadProfiles();
setupVoiceInput();

const langToggle = document.getElementById("lang-toggle");
if (langToggle) {
  langToggle.addEventListener("click", () => {
    setLang(LANG === "ru" ? "en" : "ru");
  });
}
applyI18n();
