/* Minimal vanilla JS: search typeahead (keyboard navigable) + notes CRUD
   with debounced autosave. No frameworks, no build step. */
"use strict";

/* ---------- search (home page) ---------- */
(function () {
  const box = document.getElementById("search-box");
  const list = document.getElementById("search-results");
  if (!box || !list) return;
  let items = [];
  let selected = -1;
  let timer = null;

  function render() {
    list.innerHTML = "";
    items.forEach((item, i) => {
      const li = document.createElement("li");
      li.className = i === selected ? "selected" : "";
      const t = document.createElement("span");
      t.className = "t";
      t.textContent = item.ticker;
      li.appendChild(t);
      li.appendChild(document.createTextNode(item.name + " "));
      const s = document.createElement("small");
      s.className = "dim";
      s.textContent = item.sector;
      li.appendChild(s);
      li.addEventListener("mousedown", () => go(item));
      list.appendChild(li);
    });
    list.hidden = items.length === 0;
  }

  function go(item) {
    window.location.href = "/company/" + encodeURIComponent(item.ticker);
  }

  box.addEventListener("input", () => {
    clearTimeout(timer);
    const q = box.value.trim();
    if (!q) { items = []; selected = -1; render(); return; }
    timer = setTimeout(async () => {
      const resp = await fetch("/api/search?q=" + encodeURIComponent(q));
      items = resp.ok ? await resp.json() : [];
      selected = items.length ? 0 : -1;
      render();
    }, 120);
  });

  box.addEventListener("keydown", (ev) => {
    if (ev.key === "ArrowDown") { selected = Math.min(selected + 1, items.length - 1); render(); ev.preventDefault(); }
    else if (ev.key === "ArrowUp") { selected = Math.max(selected - 1, 0); render(); ev.preventDefault(); }
    else if (ev.key === "Enter" && selected >= 0 && items[selected]) { go(items[selected]); }
    else if (ev.key === "Escape") { items = []; render(); }
  });
  box.addEventListener("blur", () => setTimeout(() => { list.hidden = true; }, 150));
})();

/* ---------- notes (company page) ---------- */
(function () {
  const container = document.querySelector(".notes");
  if (!container) return;
  const ticker = container.dataset.ticker;
  const AUTOSAVE_MS = 2000; // "autosave on pause (debounced ~2s)" — SPEC 9.9

  function wireNote(article) {
    const id = article.dataset.noteId;
    const editor = article.querySelector(".note-editor");
    const rendered = article.querySelector(".note-rendered");
    const status = article.querySelector(".note-status");
    const updatedEl = article.querySelector(".note-updated");
    const editBtn = article.querySelector(".note-edit");
    const saveBtn = article.querySelector(".note-save");
    const deleteBtn = article.querySelector(".note-delete");
    let timer = null;

    async function save() {
      clearTimeout(timer);
      status.textContent = "saving…";
      const resp = await fetch("/api/notes/" + id, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: editor.value }),
      });
      if (resp.ok) {
        const note = await resp.json();
        rendered.innerHTML = note.html;
        if (updatedEl) updatedEl.textContent = note.updated_at;
        status.textContent = "saved";
      } else {
        status.textContent = "save failed — copy your text somewhere safe";
      }
    }

    editBtn.addEventListener("click", () => {
      const editing = editor.hidden;
      editor.hidden = !editing;
      rendered.hidden = editing;
      saveBtn.hidden = !editing;
      editBtn.textContent = editing ? "preview" : "edit";
      if (editing) editor.focus();
    });
    saveBtn.addEventListener("click", save);
    editor.addEventListener("input", () => {
      status.textContent = "typing…";
      clearTimeout(timer);
      timer = setTimeout(save, AUTOSAVE_MS);
    });
    deleteBtn.addEventListener("click", async () => {
      // Explicit confirm step; this UI action is the ONLY deletion path.
      if (!window.confirm("Delete this note permanently? There is no undo.")) return;
      const resp = await fetch("/api/notes/" + id, { method: "DELETE" });
      if (resp.ok) article.remove();
      else status.textContent = "delete failed";
    });
  }

  document.querySelectorAll(".note").forEach(wireNote);

  const newBtn = document.getElementById("new-note-btn");
  newBtn.addEventListener("click", async () => {
    const resp = await fetch("/api/company/" + encodeURIComponent(ticker) + "/notes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: "" }),
    });
    if (!resp.ok) return;
    // Simplest correct thing: reload so the server renders the new note row.
    window.location.reload();
  });
})();
