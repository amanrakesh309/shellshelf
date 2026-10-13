"use strict";
/* ShellShelf frontend: no frameworks, explicit user actions only. */

const state = { items: [], detailId: null, preview: { entries: [], skipped: [] }, editingId: null };

const $ = (id) => document.getElementById(id);

function showError(msg) {
  const el = $("error-banner");
  el.textContent = msg;
  el.hidden = false;
}
function showNotice(msg) {
  const el = $("notice-banner");
  el.textContent = msg;
  el.hidden = false;
  setTimeout(() => { el.hidden = true; }, 4000);
}
function clearBanners() { $("error-banner").hidden = true; $("notice-banner").hidden = true; }

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error((data.errors || ["Request failed"]).join(" "));
  return data;
}

async function load() {
  $("loading").hidden = false;
  clearBanners();
  try {
    const q = encodeURIComponent($("search").value.trim());
    const fav = $("fav-only").checked ? "&favorites=1" : "";
    const data = await api(`/api/shortcuts?q=${q}${fav}`);
    state.items = data.shortcuts || [];
    render();
  } catch (err) {
    showError(`Could not load shortcuts: ${err.message}`);
  } finally {
    $("loading").hidden = true;
  }
}

function render() {
  const list = $("shortcut-list");
  list.innerHTML = "";
  $("empty-state").hidden = state.items.length !== 0;
  for (const item of state.items) {
    const li = document.createElement("li");
    li.className = "card";
    li.tabIndex = 0;
    li.setAttribute("aria-label", `${item.name}: ${item.command}`);
    li.addEventListener("keydown", (e) => {
      if (e.key === "Enter") openDetail(item.id);
    });

    const meta = document.createElement("div");
    meta.className = "meta";
    const name = document.createElement("div");
    name.className = "name";
    name.textContent = `${item.favorite ? "★ " : ""}${item.name}`;
    const cmd = document.createElement("code");
    cmd.textContent = item.command;
    meta.append(name, cmd);

    const actions = document.createElement("div");
    actions.className = "actions";
    const openBtn = document.createElement("button");
    openBtn.textContent = "Open";
    openBtn.setAttribute("aria-label", `Open ${item.name}`);
    openBtn.addEventListener("click", () => openDetail(item.id));
    const favBtn = document.createElement("button");
    favBtn.textContent = item.favorite ? "Unfavorite" : "Favorite";
    favBtn.setAttribute("aria-label", `${item.favorite ? "Unfavorite" : "Favorite"} ${item.name}`);
    favBtn.addEventListener("click", async () => {
      await api(`/api/shortcuts/${item.id}`, {
        method: "PUT", body: JSON.stringify({ favorite: !item.favorite }),
      });
      await load();
    });
    const editBtn = document.createElement("button");
    editBtn.textContent = "Edit";
    editBtn.setAttribute("aria-label", `Edit ${item.name}`);
    editBtn.addEventListener("click", () => openEditor(item));
    const delBtn = document.createElement("button");
    delBtn.textContent = "Delete";
    delBtn.setAttribute("aria-label", `Delete ${item.name}`);
    delBtn.addEventListener("click", async () => {
      if (!confirm(`Delete '${item.name}'?`)) return;
      await api(`/api/shortcuts/${item.id}`, { method: "DELETE" });
      await load();
    });
    actions.append(openBtn, favBtn, editBtn, delBtn);
    li.append(meta, actions);
    list.append(li);
  }
}

function openDetail(id) {
  const item = state.items.find((s) => s.id === id);
  if (!item) return;
  state.detailId = id;
  $("detail-name").textContent = item.name;
  $("detail-desc").textContent = item.description || "";
  $("detail-command").textContent = item.command;
  $("detail-mode").textContent = item.launch_mode === "app" ? "Open application / file" : "Run command";
  $("detail-source").textContent = item.source;
  $("detail-explain").textContent = "Nothing runs until you press “Launch now”. Output and errors appear below.";
  $("shell-ack-row").hidden = true;
  $("shell-ack").checked = false;
  $("launch-output-wrap").hidden = true;
  $("detail-dialog").hidden = false;
  $("btn-launch").focus();
}

async function doLaunch() {
  clearBanners();
  const viaShellAck = $("shell-ack").checked;
  try {
    const data = await api("/api/launch", {
      method: "POST",
      body: JSON.stringify({ id: state.detailId, confirmed: true, via_shell_ack: viaShellAck }),
    });
    if (data.spec) {
      $("detail-explain").textContent = data.spec.explanation || "";
    }
    if (data.returncode !== undefined) {
      $("launch-output-wrap").hidden = false;
      $("launch-status").textContent = `Exit code: ${data.returncode}`;
      $("launch-stdout").textContent = data.stdout || "(no output)";
      $("launch-stderr").textContent = data.stderr || "";
    } else {
      showNotice("Launch requested.");
      $("detail-dialog").hidden = true;
    }
  } catch (err) {
    if (err.message.includes("needs a shell")) {
      $("shell-ack-row").hidden = false;
      $("detail-explain").textContent = err.message + " Tick the acknowledgement to proceed.";
    }
    showError(err.message);
  }
}

// --- editor ---
function openEditor(item) {
  state.editingId = item ? item.id : null;
  $("editor-title").textContent = item ? "Edit shortcut" : "Add shortcut";
  $("f-name").value = item ? item.name : "";
  $("f-command").value = item ? item.command : "";
  $("f-mode").value = item ? item.launch_mode : "terminal";
  $("f-desc").value = item ? item.description : "";
  $("f-fav").checked = item ? !!item.favorite : false;
  $("form-errors").innerHTML = "";
  $("editor-dialog").hidden = false;
  $("f-name").focus();
}

async function saveEditor(event) {
  event.preventDefault();
  const payload = {
    name: $("f-name").value,
    command: $("f-command").value,
    launch_mode: $("f-mode").value,
    description: $("f-desc").value,
    favorite: $("f-fav").checked,
  };
  try {
    if (state.editingId) {
      await api(`/api/shortcuts/${state.editingId}`, { method: "PUT", body: JSON.stringify(payload) });
    } else {
      await api("/api/shortcuts", { method: "POST", body: JSON.stringify(payload) });
    }
    $("editor-dialog").hidden = true;
    showNotice("Shortcut saved.");
    await load();
  } catch (err) {
    const ul = $("form-errors");
    ul.innerHTML = "";
    for (const part of err.message.split(". ")) {
      const li = document.createElement("li");
      li.textContent = part;
      ul.append(li);
    }
  }
}

// --- import ---
async function loadCandidates() {
  const data = await api("/api/import/candidates");
  const sel = $("import-file");
  sel.innerHTML = "";
  for (const c of data.candidates) {
    const opt = document.createElement("option");
    opt.value = c.path;
    opt.textContent = `${c.label} — ${c.path}${c.exists ? "" : " (missing)"}`;
    sel.append(opt);
  }
}

async function previewImport(text, path) {
  clearBanners();
  const body = text !== undefined ? { text } : { path };
  try {
    const data = await api("/api/import/preview", { method: "POST", body: JSON.stringify(body) });
    state.preview = data;
    $("import-results").hidden = false;
    const entries = $("import-entries");
    entries.innerHTML = "";
    for (const e of data.entries) {
      const li = document.createElement("li");
      const label = document.createElement("label");
      const box = document.createElement("input");
      box.type = "checkbox";
      box.checked = !e.duplicate;
      box.disabled = !!e.duplicate;
      box.dataset.name = e.name;
      box.dataset.command = e.command;
      label.append(box, document.createTextNode(` ${e.name} = ${e.command}${e.duplicate ? " (already saved — skipped)" : ""}`));
      li.append(label);
      entries.append(li);
    }
    if (data.entries.length === 0) {
      const li = document.createElement("li");
      li.textContent = "No importable aliases found.";
      entries.append(li);
    }
  } catch (err) {
    showError(err.message);
  }
}

async function confirmImport() {
  const boxes = document.querySelectorAll("#import-entries input[type=checkbox]:checked:not(:disabled)");
  const entries = Array.from(boxes).map((b) => ({ name: b.dataset.name, command: b.dataset.command, origin: $("import-file").value || "paste" }));
  if (entries.length === 0) {
    showError("Select at least one entry to import.");
    return;
  }
  try {
    const data = await api("/api/import/confirm", { method: "POST", body: JSON.stringify({ entries }) });
    if (data.errors && data.errors.length) showError(data.errors.join(" "));
    showNotice(`Imported ${data.imported.length} shortcut(s).`);
    $("import-dialog").hidden = true;
    await load();
  } catch (err) {
    showError(err.message);
  }
}

function wire() {
  $("search").addEventListener("input", load);
  $("fav-only").addEventListener("change", load);
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && document.activeElement !== $("search")) {
      e.preventDefault();
      $("search").focus();
    }
    if (e.key === "Escape") {
      $("detail-dialog").hidden = true;
      $("editor-dialog").hidden = true;
      $("import-dialog").hidden = true;
    }
  });
  $("btn-add").addEventListener("click", () => openEditor(null));
  $("btn-empty-add").addEventListener("click", () => openEditor(null));
  $("btn-import").addEventListener("click", async () => {
    $("import-dialog").hidden = false;
    $("import-results").hidden = true;
    await loadCandidates().catch((e) => showError(e.message));
  });
  $("btn-empty-import").addEventListener("click", async () => {
    $("import-dialog").hidden = false;
    $("import-results").hidden = true;
    await loadCandidates().catch((e) => showError(e.message));
  });
  $("btn-detail-close").addEventListener("click", () => { $("detail-dialog").hidden = true; });
  $("btn-launch").addEventListener("click", doLaunch);
  $("editor-form").addEventListener("submit", saveEditor);
  $("btn-editor-close").addEventListener("click", () => { $("editor-dialog").hidden = true; });
  $("btn-import-close").addEventListener("click", () => { $("import-dialog").hidden = true; });
  $("btn-preview").addEventListener("click", () => previewImport(undefined, $("import-file").value));
  $("btn-preview-text").addEventListener("click", () => previewImport($("import-text").value, undefined));
  $("btn-do-import").addEventListener("click", confirmImport);
}

wire();
load();

// Optional PWA service worker: app-shell caching only. Registration is
// best-effort — the app works fully without it, and shortcut data, imports,
// and launches always require the local Python backend regardless.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {
      /* unsupported or unavailable (e.g. non-local http): ignore */
    });
  });
}
