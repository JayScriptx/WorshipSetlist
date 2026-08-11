// Worship Setlist app - vanilla JS single-page app.
// Hash-based routing, fetch-based API calls (see api.js), no build step -
// this file is served directly by the FastAPI backend.

// ---------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function formatDateDisplay(dateStr) {
  if (!dateStr) return "";
  const [y, m, d] = dateStr.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  return dt.toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
}

function formatDateShort(dateStr) {
  if (!dateStr) return "";
  const [y, m, d] = dateStr.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  return dt.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function todayIso() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function debounce(fn, wait) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), wait);
  };
}

function navigate(path) {
  window.location.hash = "#" + path;
}

// ---------------------------------------------------------------------
// "Paste Whole Song" parser
// ---------------------------------------------------------------------
// Converts a pasted chord chart written the traditional way (a line of
// chords, directly above the lyric line it belongs to, with sections
// marked by a standalone [Bracketed Label] line) into this app's inline
// [G]word format, split into separate sections automatically.

const CHORD_TOKEN_RE =
  /^[A-G][#b]?(?:maj7|maj9|maj13|maj|m7b5|m7|m9|m6|m11|m13|min7|min9|min|sus2|sus4|add9|add11|add2|dim7|dim|aug|2|4|5|6|7|9|11|13)*(?:\/[A-G][#b]?)?$/;

function isChordLine(line) {
  const trimmed = line.trim();
  if (!trimmed) return false;
  const tokens = trimmed.split(/\s+/);
  return tokens.every((t) => CHORD_TOKEN_RE.test(t));
}

function isSectionHeaderLine(line) {
  const m = line.trim().match(/^\[([^\]]+)\]$/);
  return m ? m[1].trim() : null;
}

function buildInlineChordLine(chordLine, lyricLine) {
  const tokens = [];
  const re = /\S+/g;
  let match;
  while ((match = re.exec(chordLine)) !== null) tokens.push({ pos: match.index, chord: match[0] });
  let result = lyricLine;
  const maxPos = tokens.length ? Math.max(...tokens.map((t) => t.pos)) : 0;
  if (result.length < maxPos) result = result.padEnd(maxPos, " ");
  for (let i = tokens.length - 1; i >= 0; i--) {
    const { pos, chord } = tokens[i];
    const insertPos = Math.min(pos, result.length);
    result = result.slice(0, insertPos) + `[${chord}]` + result.slice(insertPos);
  }
  return result;
}

function parseFullSongText(text) {
  const rawLines = text.replace(/\r\n/g, "\n").split("\n");
  const sections = [];
  let current = { section_name: "Verse 1", lines: [] };

  for (let i = 0; i < rawLines.length; i++) {
    const line = rawLines[i];
    const headerName = isSectionHeaderLine(line);
    if (headerName) {
      if (current.lines.length) sections.push(current);
      current = { section_name: headerName, lines: [] };
      continue;
    }
    if (isChordLine(line)) {
      const nextLine = rawLines[i + 1];
      const nextIsLyric =
        nextLine !== undefined &&
        nextLine.trim() !== "" &&
        !isChordLine(nextLine) &&
        !isSectionHeaderLine(nextLine);
      if (nextIsLyric) {
        current.lines.push(buildInlineChordLine(line, nextLine));
        i++;
        continue;
      }
      current.lines.push(line.trim());
      continue;
    }
    if (line.trim() === "") {
      if (current.lines.length && current.lines[current.lines.length - 1] !== "") current.lines.push("");
      continue;
    }
    current.lines.push(line);
  }
  sections.push(current);

  return sections
    .filter((s) => s.lines.some((l) => l.trim() !== ""))
    .map((s, idx) => ({
      section_name: s.section_name,
      section_order: idx,
      content: s.lines.join("\n").trim(),
      _localId: "parsed" + idx + "_" + Date.now(),
    }));
}

// Reverse of parseFullSongText - reconstructs a single pasteable block of
// text (with [Section] labels) from a saved sections array, so the paste
// box can be pre-filled when editing something that already has content.
function sectionsToPasteText(sections) {
  return sections
    .slice()
    .sort((a, b) => a.section_order - b.section_order)
    .map((s) => `[${s.section_name}]\n${s.content || ""}`)
    .join("\n\n");
}

function toast(message, type = "info") {
  const container = document.getElementById("toast-container");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = message;
  container.appendChild(el);
  setTimeout(() => {
    el.style.transition = "opacity 0.3s";
    el.style.opacity = "0";
    setTimeout(() => el.remove(), 300);
  }, 3200);
}

function errorMessage(err) {
  return err && err.message ? err.message : "Something went wrong.";
}

// ---------------------------------------------------------------------
// Modal helper
// ---------------------------------------------------------------------

function openModal(innerHtml, { onMount, title } = {}) {
  closeModal();
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.id = "active-modal-overlay";
  overlay.innerHTML = `
    <div class="modal">
      ${title ? `<div class="modal-header"><h2>${escapeHtml(title)}</h2><button class="btn btn-ghost btn-icon" data-close-modal>✕</button></div>` : ""}
      ${innerHtml}
    </div>
  `;
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) closeModal();
  });
  overlay.querySelectorAll("[data-close-modal]").forEach((btn) => btn.addEventListener("click", closeModal));
  document.body.appendChild(overlay);
  if (onMount) onMount(overlay);
  return overlay;
}

function closeModal() {
  const existing = document.getElementById("active-modal-overlay");
  if (existing) existing.remove();
}

function confirmDialog(message, { danger = true, confirmLabel = "Delete" } = {}) {
  return new Promise((resolve) => {
    const overlay = openModal(
      `
      <p style="margin-top:0">${escapeHtml(message)}</p>
      <div class="btn-row" style="margin-top:20px; justify-content:flex-end;">
        <button class="btn" data-cancel>Cancel</button>
        <button class="btn ${danger ? "btn-danger" : "btn-primary"}" data-confirm>${escapeHtml(confirmLabel)}</button>
      </div>
    `,
      {}
    );
    overlay.querySelector("[data-cancel]").addEventListener("click", () => {
      closeModal();
      resolve(false);
    });
    overlay.querySelector("[data-confirm]").addEventListener("click", () => {
      closeModal();
      resolve(true);
    });
  });
}

// ---------------------------------------------------------------------
// Router
// ---------------------------------------------------------------------

const routes = [
  { pattern: /^\/?$/, view: viewDashboard },
  { pattern: /^\/setlists$/, view: viewSetlistsList },
  { pattern: /^\/setlists\/new$/, view: viewSetlistCreate },
  { pattern: /^\/setlists\/(\d+)$/, view: viewSetlistDetail },
  { pattern: /^\/songs$/, view: viewSongsList },
  { pattern: /^\/songs\/new$/, view: viewSongForm },
  { pattern: /^\/songs\/(\d+)\/edit$/, view: viewSongForm },
  { pattern: /^\/setlist-song\/(\d+)$/, view: viewSetlistSongReader },
];

async function router() {
  const hash = window.location.hash.replace(/^#/, "") || "/";
  const path = hash.split("?")[0];

  for (const route of routes) {
    const match = path.match(route.pattern);
    if (match) {
      updateNavActive(path);
      const content = document.getElementById("content");
      content.innerHTML = `<div class="loading"><div class="spinner"></div>Loading…</div>`;
      window.scrollTo(0, 0);
      try {
        await route.view(content, ...match.slice(1));
      } catch (err) {
        content.innerHTML = `
          <div class="empty-state">
            <div class="icon">⚠️</div>
            <h2>Couldn't load this page</h2>
            <p>${escapeHtml(errorMessage(err))}</p>
            <button class="btn btn-primary" onclick="navigate('/')">Go to Dashboard</button>
          </div>`;
      }
      return;
    }
  }
  navigate("/");
}

function updateNavActive(path) {
  let section = "dashboard";
  if (path.startsWith("/setlists")) section = "setlists";
  else if (path.startsWith("/songs")) section = "songs";
  document.querySelectorAll("[data-nav]").forEach((el) => {
    el.classList.toggle("active", el.getAttribute("data-nav") === section);
  });
}

window.addEventListener("hashchange", router);
window.addEventListener("DOMContentLoaded", router);

// ---------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------

async function viewDashboard(content) {
  const setlists = await api.listSetlists();
  const recent = setlists.slice(0, 5);

  content.innerHTML = `
    <div class="page-title">
      <div>
        <h1>Dashboard</h1>
        <p class="muted" style="margin:0">Plan your next Sunday lineup.</p>
      </div>
    </div>

    <div class="btn-row" style="margin-bottom:28px;">
      <button class="btn btn-primary" id="btn-create-setlist">+ Create Setlist</button>
      <button class="btn" onclick="navigate('/setlists')">View Setlists</button>
      <button class="btn" onclick="navigate('/songs')">View Songs</button>
    </div>

    <h2>Recent Setlists</h2>
    <div id="recent-list">
      ${recent.length
      ? recent.map(renderSetlistCard).join("")
      : `<div class="empty-state">
               <div class="icon">🎵</div>
               <p>No setlists yet.</p>
               <button class="btn btn-primary" id="btn-create-setlist-empty">+ Create Setlist</button>
             </div>`
    }
    </div>
  `;

  const goCreate = () => navigate("/setlists/new");
  content.querySelector("#btn-create-setlist")?.addEventListener("click", goCreate);
  content.querySelector("#btn-create-setlist-empty")?.addEventListener("click", goCreate);
  bindSetlistCardEvents(content);
}

function renderSetlistCard(s) {
  return `
    <div class="list-card" data-setlist-id="${s.id}">
      <div class="info" data-open-setlist="${s.id}" style="cursor:pointer">
        <h3>${escapeHtml(s.name)}</h3>
        <div class="meta">
          <span>${formatDateDisplay(s.date)}</span>
          <span>•</span>
          <span>${s.song_count} Song${s.song_count === 1 ? "" : "s"}</span>
        </div>
      </div>
      <div class="actions">
        <button class="btn btn-sm" data-open-setlist="${s.id}">Open</button>
      </div>
    </div>
  `;
}

function bindSetlistCardEvents(content) {
  content.querySelectorAll("[data-open-setlist]").forEach((el) => {
    el.addEventListener("click", () => navigate(`/setlists/${el.getAttribute("data-open-setlist")}`));
  });
}

// ---------------------------------------------------------------------
// Setlists list
// ---------------------------------------------------------------------

async function viewSetlistsList(content) {
  content.innerHTML = `
    <div class="page-title">
      <h1>Setlists</h1>
      <button class="btn btn-primary" id="btn-new-setlist">+ Create Setlist</button>
    </div>
    <div class="search-bar">
      <input type="text" id="setlist-search" placeholder="Search setlists…" />
    </div>
    <div id="setlist-results"><div class="loading"><div class="spinner"></div></div></div>
  `;

  content.querySelector("#btn-new-setlist").addEventListener("click", () => navigate("/setlists/new"));

  const resultsEl = content.querySelector("#setlist-results");

  async function load(search) {
    const setlists = await api.listSetlists(search);
    if (!setlists.length) {
      resultsEl.innerHTML = `
        <div class="empty-state">
          <div class="icon">🎵</div>
          <p>${search ? "No setlists match your search." : "No setlists yet."}</p>
          ${search ? "" : `<button class="btn btn-primary" id="btn-empty-create">+ Create Setlist</button>`}
        </div>`;
      resultsEl.querySelector("#btn-empty-create")?.addEventListener("click", () => navigate("/setlists/new"));
      return;
    }
    resultsEl.innerHTML = setlists
      .map(
        (s) => `
      <div class="list-card">
        <div class="info" data-open="${s.id}" style="cursor:pointer">
          <h3>${escapeHtml(s.name)}</h3>
          <div class="meta">
            <span>${formatDateDisplay(s.date)}</span>
            <span>•</span>
            <span>${s.song_count} Song${s.song_count === 1 ? "" : "s"}</span>
            <span>•</span>
            <span>Updated ${formatDateShort(s.updated_at.slice(0, 10))}</span>
          </div>
        </div>
        <div class="actions">
          <button class="btn btn-sm" data-open="${s.id}">Open</button>
          <button class="btn btn-sm btn-icon" data-delete="${s.id}" title="Delete setlist">🗑</button>
        </div>
      </div>
    `
      )
      .join("");

    resultsEl.querySelectorAll("[data-open]").forEach((el) =>
      el.addEventListener("click", () => navigate(`/setlists/${el.getAttribute("data-open")}`))
    );
    resultsEl.querySelectorAll("[data-delete]").forEach((el) =>
      el.addEventListener("click", async (e) => {
        e.stopPropagation();
        const id = el.getAttribute("data-delete");
        const ok = await confirmDialog("Delete this setlist? This cannot be undone.");
        if (!ok) return;
        try {
          await api.deleteSetlist(id);
          toast("Setlist deleted.", "success");
          load(content.querySelector("#setlist-search").value.trim());
        } catch (err) {
          toast(errorMessage(err), "error");
        }
      })
    );
  }

  content.querySelector("#setlist-search").addEventListener(
    "input",
    debounce((e) => load(e.target.value.trim()), 300)
  );

  await load();
}

// ---------------------------------------------------------------------
// Create Setlist
// ---------------------------------------------------------------------

async function viewSetlistCreate(content) {
  content.innerHTML = `
    <div class="page-title"><h1>Create Setlist</h1></div>
    <div class="card" style="max-width:520px;">
      <form id="setlist-form">
        <div class="field">
          <label for="f-name">Setlist Name</label>
          <input type="text" id="f-name" placeholder="Aug 14 Sunday Line Up" required />
        </div>
        <div class="field">
          <label for="f-date">Date</label>
          <input type="date" id="f-date" value="${todayIso()}" required />
        </div>
        <div class="field">
          <label for="f-desc">Description <span class="faint">(optional)</span></label>
          <input type="text" id="f-desc" placeholder="Sunday Worship Service" />
        </div>
        <div class="btn-row" style="justify-content:flex-end;">
          <button type="button" class="btn" id="btn-cancel">Cancel</button>
          <button type="submit" class="btn btn-primary">Create Setlist</button>
        </div>
      </form>
    </div>
  `;

  content.querySelector("#btn-cancel").addEventListener("click", () => navigate("/setlists"));
  content.querySelector("#setlist-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = content.querySelector("#f-name").value.trim();
    const date = content.querySelector("#f-date").value;
    const description = content.querySelector("#f-desc").value.trim();
    if (!name || !date) {
      toast("Please fill in the setlist name and date.", "error");
      return;
    }
    const submitBtn = content.querySelector("button[type=submit]");
    submitBtn.disabled = true;
    try {
      const setlist = await api.createSetlist({ name, date, description: description || null });
      toast("Setlist created.", "success");
      navigate(`/setlists/${setlist.id}`);
    } catch (err) {
      toast(errorMessage(err), "error");
      submitBtn.disabled = false;
    }
  });
}

// ---------------------------------------------------------------------
// Setlist detail
// ---------------------------------------------------------------------

async function viewSetlistDetail(content, setlistId) {
  const setlist = await api.getSetlist(setlistId);
  renderSetlistDetail(content, setlist);
}

function renderSetlistDetail(content, setlist) {
  const songs = [...setlist.songs].sort((a, b) => a.song_order - b.song_order);

  content.innerHTML = `
    <div class="page-title">
      <div>
        <p class="eyebrow" style="cursor:pointer" id="back-to-setlists">← Setlists</p>
        <h1>${escapeHtml(setlist.name)}</h1>
        <p class="muted" style="margin:2px 0 0">${formatDateDisplay(setlist.date)}${setlist.description ? " · " + escapeHtml(setlist.description) : ""}</p>
      </div>
      <div class="btn-row">
        <button class="btn" id="btn-edit-setlist">Edit</button>
        <button class="btn btn-danger" id="btn-delete-setlist">Delete</button>
      </div>
    </div>

    <h2>Songs</h2>
    <div id="song-list">
      ${songs.length
      ? songs.map((s, i) => renderSetlistSongRow(s, i, songs.length)).join("")
      : `<div class="empty-state">
               <div class="icon">🎼</div>
               <p>No songs added yet.</p>
             </div>`
    }
    </div>
    <button class="btn btn-primary btn-block" id="btn-add-song" style="margin-top:10px;">+ Add Song</button>
  `;

  content.querySelector("#back-to-setlists").addEventListener("click", () => navigate("/setlists"));

  content.querySelector("#btn-edit-setlist").addEventListener("click", () => openEditSetlistModal(setlist));

  content.querySelector("#btn-delete-setlist").addEventListener("click", async () => {
    const ok = await confirmDialog(`Delete "${setlist.name}"? This cannot be undone.`);
    if (!ok) return;
    try {
      await api.deleteSetlist(setlist.id);
      toast("Setlist deleted.", "success");
      navigate("/setlists");
    } catch (err) {
      toast(errorMessage(err), "error");
    }
  });

  content.querySelector("#btn-add-song").addEventListener("click", () => openAddSongModal(setlist, content));

  bindSetlistSongRowEvents(content, setlist);
}

function renderSetlistSongRow(s, index, total) {
  const keyLabel = s.key_override && s.original_key && s.key_override !== s.original_key
    ? `${escapeHtml(s.key)} <span class="faint">(orig ${escapeHtml(s.original_key)})</span>`
    : escapeHtml(s.key || "—");

  return `
    <div class="song-row" data-row-id="${s.id}">
      <div class="num">${String(index + 1).padStart(2, "0")}</div>
      <div class="info" data-open-song="${s.id}">
        <h4>${escapeHtml(s.title)}${s.song_deleted ? ' <span class="faint">(removed from library)</span>' : ""}</h4>
        <div class="meta">
          ${s.artist ? escapeHtml(s.artist) + " · " : ""}Key: ${keyLabel}${s.bpm ? " · " + s.bpm + " BPM" : ""}
        </div>
      </div>
      <div class="reorder">
        <button class="btn btn-icon btn-sm" data-move-up="${s.id}" ${index === 0 ? "disabled" : ""} title="Move up">▲</button>
        <button class="btn btn-icon btn-sm" data-move-down="${s.id}" ${index === total - 1 ? "disabled" : ""} title="Move down">▼</button>
      </div>
      <div class="actions">
        <button class="btn btn-sm" data-open-song="${s.id}">Open</button>
        <button class="btn btn-sm btn-icon" data-edit-row="${s.id}" title="Edit key/BPM/notes">✎</button>
        <button class="btn btn-sm btn-icon" data-remove-row="${s.id}" title="Remove from setlist">✕</button>
      </div>
    </div>
  `;
}

function bindSetlistSongRowEvents(content, setlist) {
  content.querySelectorAll("[data-open-song]").forEach((el) =>
    el.addEventListener("click", () => navigate(`/setlist-song/${el.getAttribute("data-open-song")}`))
  );

  content.querySelectorAll("[data-edit-row]").forEach((el) =>
    el.addEventListener("click", () => {
      const row = setlist.songs.find((s) => String(s.id) === el.getAttribute("data-edit-row"));
      openEditSetlistSongModal(row, setlist, content);
    })
  );

  content.querySelectorAll("[data-remove-row]").forEach((el) =>
    el.addEventListener("click", async () => {
      const id = el.getAttribute("data-remove-row");
      const row = setlist.songs.find((s) => String(s.id) === id);
      const ok = await confirmDialog(`Remove "${row.title}" from this setlist?`, { confirmLabel: "Remove" });
      if (!ok) return;
      try {
        await api.removeSongFromSetlist(setlist.id, id);
        const fresh = await api.getSetlist(setlist.id);
        renderSetlistDetail(content, fresh);
        toast("Song removed.", "success");
      } catch (err) {
        toast(errorMessage(err), "error");
      }
    })
  );

  content.querySelectorAll("[data-move-up]").forEach((el) =>
    el.addEventListener("click", () => moveSetlistSong(setlist, content, el.getAttribute("data-move-up"), -1))
  );
  content.querySelectorAll("[data-move-down]").forEach((el) =>
    el.addEventListener("click", () => moveSetlistSong(setlist, content, el.getAttribute("data-move-down"), 1))
  );
}

async function moveSetlistSong(setlist, content, songRowId, direction) {
  const songs = [...setlist.songs].sort((a, b) => a.song_order - b.song_order);
  const idx = songs.findIndex((s) => String(s.id) === String(songRowId));
  const swapWith = idx + direction;
  if (swapWith < 0 || swapWith >= songs.length) return;

  [songs[idx], songs[swapWith]] = [songs[swapWith], songs[idx]];
  const order = songs.map((s, i) => ({ id: s.id, song_order: i }));

  try {
    await api.reorderSetlistSongs(setlist.id, order);
    const fresh = await api.getSetlist(setlist.id);
    renderSetlistDetail(content, fresh);
  } catch (err) {
    toast(errorMessage(err), "error");
  }
}

function openEditSetlistModal(setlist) {
  openModal(
    `
    <form id="edit-setlist-form">
      <div class="field">
        <label for="e-name">Setlist Name</label>
        <input type="text" id="e-name" value="${escapeHtml(setlist.name)}" required />
      </div>
      <div class="field">
        <label for="e-date">Date</label>
        <input type="date" id="e-date" value="${setlist.date}" required />
      </div>
      <div class="field">
        <label for="e-desc">Description</label>
        <input type="text" id="e-desc" value="${escapeHtml(setlist.description || "")}" />
      </div>
      <div class="btn-row" style="justify-content:flex-end;">
        <button type="button" class="btn" data-close-modal>Cancel</button>
        <button type="submit" class="btn btn-primary">Save Changes</button>
      </div>
    </form>
  `,
    {
      title: "Edit Setlist",
      onMount: (overlay) => {
        overlay.querySelector("#edit-setlist-form").addEventListener("submit", async (e) => {
          e.preventDefault();
          try {
            await api.updateSetlist(setlist.id, {
              name: overlay.querySelector("#e-name").value.trim(),
              date: overlay.querySelector("#e-date").value,
              description: overlay.querySelector("#e-desc").value.trim() || null,
            });
            closeModal();
            toast("Setlist updated.", "success");
            const fresh = await api.getSetlist(setlist.id);
            renderSetlistDetail(document.getElementById("content"), fresh);
          } catch (err) {
            toast(errorMessage(err), "error");
          }
        });
      },
    }
  );
}

function openEditSetlistSongModal(row, setlist, content) {
  openModal(
    `
    <form id="edit-row-form">
      <p class="muted" style="margin-top:0">${escapeHtml(row.title)}</p>
      <div class="field-row">
        <div class="field">
          <label for="r-key">Key ${row.original_key ? `<span class="faint">(orig ${escapeHtml(row.original_key)})</span>` : ""}</label>
          <input type="text" id="r-key" value="${escapeHtml(row.key_override || "")}" placeholder="${escapeHtml(row.original_key || "e.g. D")}" />
          <div class="field-hint">A real note (C, F#, Bb...) so transpose keeps working.</div>
        </div>
        <div class="field">
          <label for="r-bpm">BPM</label>
          <input type="number" id="r-bpm" min="1" max="400" value="${row.bpm_override || ""}" />
        </div>
      </div>
      <div class="field">
        <label for="r-notes">Setlist Notes</label>
        <textarea id="r-notes" rows="4" placeholder="Intro 4 bars, repeat chorus twice…">${escapeHtml(row.notes || "")}</textarea>
      </div>
      <div class="btn-row" style="justify-content:flex-end;">
        <button type="button" class="btn" data-close-modal>Cancel</button>
        <button type="submit" class="btn btn-primary">Save</button>
      </div>
    </form>
  `,
    {
      title: "Setlist-only Overrides",
      onMount: (overlay) => {
        overlay.querySelector("#edit-row-form").addEventListener("submit", async (e) => {
          e.preventDefault();
          try {
            const keyVal = overlay.querySelector("#r-key").value.trim();
            const bpmVal = overlay.querySelector("#r-bpm").value;
            await api.updateSetlistSong(row.id, {
              key_override: keyVal || null,
              bpm_override: bpmVal ? Number(bpmVal) : null,
              notes: overlay.querySelector("#r-notes").value.trim() || null,
            });
            closeModal();
            toast("Saved.", "success");
            const fresh = await api.getSetlist(setlist.id);
            renderSetlistDetail(content, fresh);
          } catch (err) {
            toast(errorMessage(err), "error");
          }
        });
      },
    }
  );
}

function openAddSongModal(setlist, content) {
  openModal(
    `
    <input type="text" id="picker-search" placeholder="Search songs…" style="width:100%; background:var(--bg-card); border:1px solid var(--border); color:var(--text); border-radius:9px; padding:12px 14px; font-size:0.95rem; margin-bottom:14px;" />
    <div id="picker-results"><div class="loading"><div class="spinner"></div></div></div>
  `,
    {
      title: "Add Song",
      onMount: async (overlay) => {
        const resultsEl = overlay.querySelector("#picker-results");

        async function load(search) {
          const songs = await api.listSongs(search);
          if (!songs.length) {
            resultsEl.innerHTML = `<div class="empty-state">
              <p>${search ? "No songs match your search." : "Your song library is empty."}</p>
              ${search ? "" : `<button class="btn btn-primary" id="picker-empty-create">+ Add Song</button>`}
            </div>`;
            resultsEl.querySelector("#picker-empty-create")?.addEventListener("click", () => {
              closeModal();
              navigate("/songs/new");
            });
            return;
          }
          resultsEl.innerHTML = songs
            .map(
              (song) => `
            <div class="picker-item">
              <div class="info">
                <h4>${escapeHtml(song.title)}</h4>
                <div class="meta">${escapeHtml(song.artist || "")}${song.artist ? " · " : ""}Key: ${escapeHtml(song.original_key || "—")}${song.bpm ? " · " + song.bpm + " BPM" : ""}</div>
              </div>
              <button class="btn btn-sm btn-primary" data-add="${song.id}">Add</button>
            </div>
          `
            )
            .join("");

          resultsEl.querySelectorAll("[data-add]").forEach((btn) =>
            btn.addEventListener("click", async () => {
              btn.disabled = true;
              btn.textContent = "Adding…";
              const songId = Number(btn.getAttribute("data-add"));
              try {
                await api.addSongToSetlist(setlist.id, songId);
                toast("Song added.", "success");
                closeModal();
                const fresh = await api.getSetlist(setlist.id);
                renderSetlistDetail(content, fresh);
              } catch (err) {
                if (err.status === 409) {
                  const again = await confirmDialog(errorMessage(err), { confirmLabel: "Add Anyway", danger: false });
                  if (again) {
                    try {
                      await api.addSongToSetlist(setlist.id, songId, null, true);
                      toast("Song added.", "success");
                      closeModal();
                      const fresh = await api.getSetlist(setlist.id);
                      renderSetlistDetail(content, fresh);
                      return;
                    } catch (err2) {
                      toast(errorMessage(err2), "error");
                    }
                  }
                  btn.disabled = false;
                  btn.textContent = "Add";
                } else {
                  toast(errorMessage(err), "error");
                  btn.disabled = false;
                  btn.textContent = "Add";
                }
              }
            })
          );
        }

        overlay.querySelector("#picker-search").addEventListener(
          "input",
          debounce((e) => load(e.target.value.trim()), 300)
        );

        await load();
      },
    }
  );
}

// ---------------------------------------------------------------------
// Songs list (library)
// ---------------------------------------------------------------------

async function viewSongsList(content) {
  content.innerHTML = `
    <div class="page-title">
      <h1>Song Library</h1>
      <button class="btn btn-primary" id="btn-new-song">+ Add Song</button>
    </div>
    <div class="search-bar">
      <input type="text" id="song-search" placeholder="Search songs…" />
    </div>
    <div id="song-results"><div class="loading"><div class="spinner"></div></div></div>
  `;

  content.querySelector("#btn-new-song").addEventListener("click", () => navigate("/songs/new"));
  const resultsEl = content.querySelector("#song-results");

  async function load(search) {
    const songs = await api.listSongs(search);
    if (!songs.length) {
      resultsEl.innerHTML = `
        <div class="empty-state">
          <div class="icon">🎸</div>
          <p>${search ? "No songs match your search." : "Your song library is empty."}</p>
          ${search ? "" : `<button class="btn btn-primary" id="btn-empty-add">+ Add Your First Worship Song</button>`}
        </div>`;
      resultsEl.querySelector("#btn-empty-add")?.addEventListener("click", () => navigate("/songs/new"));
      return;
    }
    resultsEl.innerHTML = songs
      .map(
        (song) => `
      <div class="list-card">
        <div class="info" data-open="${song.id}" style="cursor:pointer">
          <h3>${escapeHtml(song.title)}</h3>
          <div class="meta">
            <span>${escapeHtml(song.artist || "Unknown Artist")}</span>
            <span>•</span>
            <span>Key: ${escapeHtml(song.original_key || "—")}</span>
            ${song.bpm ? `<span>•</span><span>${song.bpm} BPM</span>` : ""}
            <span>•</span>
            <span>${song.section_count} section${song.section_count === 1 ? "" : "s"}</span>
          </div>
        </div>
        <div class="actions">
          <button class="btn btn-sm" data-open="${song.id}">Edit</button>
          <button class="btn btn-sm btn-icon" data-delete="${song.id}" data-title="${escapeHtml(song.title)}" title="Delete song">🗑</button>
        </div>
      </div>
    `
      )
      .join("");

    resultsEl.querySelectorAll("[data-open]").forEach((el) =>
      el.addEventListener("click", () => navigate(`/songs/${el.getAttribute("data-open")}/edit`))
    );

    resultsEl.querySelectorAll("[data-delete]").forEach((el) =>
      el.addEventListener("click", async (e) => {
        e.stopPropagation();
        const id = el.getAttribute("data-delete");
        const title = el.getAttribute("data-title");
        const ok = await confirmDialog(`Delete "${title}"? This cannot be undone.`);
        if (!ok) return;
        try {
          await api.deleteSong(id);
          toast("Song deleted.", "success");
          load(content.querySelector("#song-search").value.trim());
        } catch (err) {
          if (err.status === 409) {
            const force = await confirmDialog(
              `${errorMessage(err)}\n\nDelete anyway? Setlists using this song will keep showing its title/artist/key.`,
              { confirmLabel: "Delete Anyway" }
            );
            if (force) {
              try {
                await api.deleteSong(id, true);
                toast("Song deleted.", "success");
                load(content.querySelector("#song-search").value.trim());
              } catch (err2) {
                toast(errorMessage(err2), "error");
              }
            }
          } else {
            toast(errorMessage(err), "error");
          }
        }
      })
    );
  }

  content.querySelector("#song-search").addEventListener(
    "input",
    debounce((e) => load(e.target.value.trim()), 300)
  );

  await load();
}

// ---------------------------------------------------------------------
// Song create / edit form (single paste box - sections come from
// [Bracket] labels only, no manual per-section UI)
// ---------------------------------------------------------------------

async function viewSongForm(content, songId) {
  const isEdit = !!songId;
  let song = null;
  if (isEdit) song = await api.getSong(songId);

  const initialPasteText = isEdit ? sectionsToPasteText(song.sections) : "";

  content.innerHTML = `
    <div class="page-title">
      <div>
        <p class="eyebrow" style="cursor:pointer" id="back-link">← Songs</p>
        <h1>${isEdit ? "Edit Song" : "Add Song"}</h1>
      </div>
      ${isEdit ? `<button class="btn btn-danger" id="btn-delete-song">Delete Song</button>` : ""}
    </div>

    <form id="song-form">
      <div class="card" style="margin-bottom:20px;">
        <div class="field">
          <label for="f-title">Title</label>
          <input type="text" id="f-title" value="${isEdit ? escapeHtml(song.title) : ""}" placeholder="Take Me Back" required />
        </div>
        <div class="field-row">
          <div class="field">
            <label for="f-artist">Artist</label>
            <input type="text" id="f-artist" value="${isEdit ? escapeHtml(song.artist || "") : ""}" placeholder="Planetshakers" />
          </div>
          <div class="field">
            <label for="f-key">Original Key</label>
            <input type="text" id="f-key" value="${isEdit ? escapeHtml(song.original_key || "") : ""}" placeholder="E" />
            <div class="field-hint">A real note: C, F#, Bb, etc. - anything else breaks the transpose buttons.</div>          </div>
        </div>
        <div class="field-row">
          <div class="field">
            <label for="f-bpm">BPM</label>
            <input type="number" id="f-bpm" min="1" max="400" value="${isEdit && song.bpm ? song.bpm : ""}" placeholder="120" />
          </div>
          <div class="field">
            <label for="f-ts">Time Signature</label>
            <input type="text" id="f-ts" value="${isEdit ? escapeHtml(song.time_signature) : "4/4"}" placeholder="4/4" />
          </div>
        </div>
      </div>

      <h2 style="margin-bottom:12px;">Lyrics &amp; Chords</h2>
      <div class="chordpro-help">
        Paste the whole song here - chords on their own line, directly above the lyric line, just
        like you'd normally write it. Start each section with a label in brackets on its own line,
        e.g. <code>[Intro]</code>, <code>[Verse 1]</code>, <code>[Chorus]</code>. Sections are
        created automatically from those labels - no need to add them one at a time.
      </div>
      <textarea id="full-song-textarea" rows="20" style="width:100%; font-family:'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace; font-size:0.9rem; margin-top:10px; background:var(--bg-elevated); border:1px solid var(--border); color:var(--text); border-radius:9px; padding:14px;" placeholder="[Intro]
G   D   Em   C

[Verse 1]
     G                   Em7
The splendor of a King, clothed in majesty">${escapeHtml(initialPasteText)}</textarea>

      <div class="btn-row" style="justify-content:flex-end; margin-top:24px;">
        <button type="button" class="btn" id="btn-cancel">Cancel</button>
        <button type="submit" class="btn btn-primary">${isEdit ? "Save Changes" : "Create Song"}</button>
      </div>
    </form>
  `;

  content.querySelector("#back-link").addEventListener("click", () => navigate("/songs"));
  content.querySelector("#btn-cancel").addEventListener("click", () => navigate("/songs"));

  if (isEdit) {
    content.querySelector("#btn-delete-song").addEventListener("click", async () => {
      const ok = await confirmDialog(`Delete "${song.title}"? This cannot be undone.`);
      if (!ok) return;
      try {
        await api.deleteSong(song.id);
        toast("Song deleted.", "success");
        navigate("/songs");
      } catch (err) {
        if (err.status === 409) {
          const force = await confirmDialog(
            `${errorMessage(err)}\n\nDelete anyway? Setlists using this song will keep showing its title/artist/key.`,
            { confirmLabel: "Delete Anyway" }
          );
          if (force) {
            try {
              await api.deleteSong(song.id, true);
              toast("Song deleted.", "success");
              navigate("/songs");
            } catch (err2) {
              toast(errorMessage(err2), "error");
            }
          }
        } else {
          toast(errorMessage(err), "error");
        }
      }
    });
  }

  content.querySelector("#song-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const title = content.querySelector("#f-title").value.trim();
    if (!title) {
      toast("Title is required.", "error");
      return;
    }
    const payload = {
      title,
      artist: content.querySelector("#f-artist").value.trim() || null,
      original_key: content.querySelector("#f-key").value.trim() || null,
      bpm: content.querySelector("#f-bpm").value ? Number(content.querySelector("#f-bpm").value) : null,
      time_signature: content.querySelector("#f-ts").value.trim() || "4/4",
    };

    const rawText = content.querySelector("#full-song-textarea").value;
    const parsedSections = rawText.trim() ? parseFullSongText(rawText) : [];

    const submitBtn = content.querySelector("button[type=submit]");
    submitBtn.disabled = true;

    try {
      let savedSong;
      if (isEdit) {
        savedSong = await api.updateSong(song.id, payload);
        await replaceSongSections(song.id, song.sections, parsedSections);
      } else {
        payload.sections = parsedSections.map((s, i) => ({
          section_name: s.section_name,
          section_order: i,
          content: s.content,
        }));
        savedSong = await api.createSong(payload);
      }
      toast(isEdit ? "Song updated." : "Song created.", "success");
      navigate("/songs");
    } catch (err) {
      toast(errorMessage(err), "error");
      submitBtn.disabled = false;
    }
  });
}

// Replaces all of a song's sections with a freshly parsed set (from the
// paste box). Since the box is the single source of truth, this simply
// deletes the old sections and creates the new ones, rather than trying
// to diff them line by line.
async function replaceSongSections(songId, originalSections, parsedSections) {
  await Promise.all(originalSections.map((s) => api.deleteSection(s.id)));

  const createdIds = [];
  for (const sec of parsedSections) {
    const newSec = await api.createSection(songId, {
      section_name: sec.section_name,
      section_order: 0,
      content: sec.content,
    });
    createdIds.push(newSec.id);
  }

  if (createdIds.length) {
    const order = createdIds.map((id, i) => ({ id, section_order: i }));
    await api.reorderSections(songId, order);
  }
}

// ---------------------------------------------------------------------
// Setlist-song reader (the main "songbook" view with transpose)
// ---------------------------------------------------------------------

async function viewSetlistSongReader(content, setlistSongId) {
  const data = await api.viewSetlistSong(setlistSongId, 0);
  let songList = [];
  try {
    const setlist = await api.getSetlist(data.setlist_id);
    songList = [...setlist.songs].sort((a, b) => a.song_order - b.song_order);
  } catch (err) {
    // Prev/Next navigation is a nice-to-have - don't block the reader if this fails.
    songList = [];
  }
  renderReader(content, data, 0, songList);
}

function renderReader(content, data, semitones, songList = []) {
  const idx = songList.findIndex((s) => s.id === data.id);
  const prevSong = idx > 0 ? songList[idx - 1] : null;
  const nextSong = idx >= 0 && idx < songList.length - 1 ? songList[idx + 1] : null;

  content.innerHTML = `
    <div class="reader-header">
      <span class="back" id="back-to-setlist">← ${escapeHtml(data.setlist_name)}</span>
      <h1>${escapeHtml(data.title)}${data.song_deleted ? ' <span class="faint" style="font-size:0.9rem;">(removed from library)</span>' : ""}</h1>
      ${data.artist ? `<div class="artist">${escapeHtml(data.artist)}</div>` : ""}

      <div class="reader-controls">
        <div class="transpose-control">
          <button id="transpose-down" ${!data.base_key ? "disabled" : ""} aria-label="Transpose down">−</button>
          <div class="key-display">
            ${data.current_key ? escapeHtml(data.current_key) : "—"}
            <small>${semitones === 0 ? "Original" : semitones > 0 ? "+" + semitones : semitones}</small>
          </div>
          <button id="transpose-up" ${!data.base_key ? "disabled" : ""} aria-label="Transpose up">+</button>
        </div>
        ${semitones !== 0 ? `<button class="btn btn-sm" id="transpose-reset">Reset</button>` : ""}
        <div class="reader-meta">
          ${data.bpm ? `<span>${data.bpm} BPM</span>` : ""}
          ${data.time_signature ? `<span>${escapeHtml(data.time_signature)}</span>` : ""}
          ${data.has_custom_arrangement ? `<span class="pill">Custom arrangement</span>` : ""}
        </div>
      </div>

      ${
        songList.length > 1
          ? `<div class="btn-row" style="margin-top:14px; justify-content:space-between; align-items:center;">
               <button class="btn btn-sm" id="btn-prev-song" ${prevSong ? "" : "disabled"}>◀ Prev${prevSong ? ": " + escapeHtml(prevSong.title) : ""}</button>
               ${idx >= 0 ? `<span class="faint" style="font-size:0.78rem; white-space:nowrap;">${idx + 1} of ${songList.length}</span>` : ""}
               <button class="btn btn-sm" id="btn-next-song" ${nextSong ? "" : "disabled"}>${nextSong ? escapeHtml(nextSong.title) + ": " : ""}Next ▶</button>
             </div>`
          : ""
      }
    </div>

    <div id="sections-display">
      ${data.sections.length
      ? data.sections.map(renderReaderSection).join("")
      : `<div class="empty-state"><p>No lyrics/chords added for this song yet.</p></div>`
    }
    </div>

    ${data.notes
      ? `<div class="notes-block">
             <div class="section-name">Notes</div>
             <pre>${escapeHtml(data.notes)}</pre>
           </div>`
      : ""
    }

    <div class="btn-row" style="margin-top:30px;">
      <button class="btn" id="btn-edit-arrangement">${data.has_custom_arrangement ? "Edit Custom Arrangement" : "Customize for This Setlist"}</button>
      ${data.has_custom_arrangement ? `<button class="btn btn-ghost" id="btn-reset-arrangement">Reset to Master Song</button>` : ""}
    </div>
  `;

  content.querySelector("#back-to-setlist").addEventListener("click", () => navigate(`/setlists/${data.setlist_id}`));

  content.querySelector("#btn-prev-song")?.addEventListener("click", () => {
    if (prevSong) navigate(`/setlist-song/${prevSong.id}`);
  });
  content.querySelector("#btn-next-song")?.addEventListener("click", () => {
    if (nextSong) navigate(`/setlist-song/${nextSong.id}`);
  });

  content.querySelector("#transpose-up")?.addEventListener("click", async () => {
    const fresh = await api.viewSetlistSong(data.id, Math.min(11, semitones + 1));
    renderReader(content, fresh, fresh.semitones, songList);
  });
  content.querySelector("#transpose-down")?.addEventListener("click", async () => {
    const fresh = await api.viewSetlistSong(data.id, Math.max(-11, semitones - 1));
    renderReader(content, fresh, fresh.semitones, songList);
  });
  content.querySelector("#transpose-reset")?.addEventListener("click", async () => {
    const fresh = await api.viewSetlistSong(data.id, 0);
    renderReader(content, fresh, 0, songList);
  });

  content.querySelector("#btn-edit-arrangement").addEventListener("click", () =>
    openArrangementEditor(data, content, songList)
  );
  content.querySelector("#btn-reset-arrangement")?.addEventListener("click", async () => {
    const ok = await confirmDialog(
      "Reset to the master song's lyrics/chords? Your setlist-only edits for this song will be discarded.",
      { confirmLabel: "Reset" }
    );
    if (!ok) return;
    try {
      await api.resetArrangement(data.id);
      const fresh = await api.viewSetlistSong(data.id, 0);
      renderReader(content, fresh, 0, songList);
      toast("Reverted to master song.", "success");
    } catch (err) {
      toast(errorMessage(err), "error");
    }
  });
}

function renderReaderSection(section) {
  return `
    <div class="section-block">
      <div class="section-name">${escapeHtml(section.section_name)}</div>
      ${section.lines
      .map((line) => {
        if (!line.chord_line && !line.lyric_line) return `<div class="chord-line-pair">&nbsp;</div>`;
        return `
          <div class="chord-line-pair">
            <div class="chords">${line.has_chords ? escapeHtml(line.chord_line) : ""}</div>
            <div class="lyrics">${escapeHtml(line.lyric_line) || "&nbsp;"}</div>
          </div>`;
      })
      .join("")}
    </div>
  `;
}

// --- Arrangement editor: setlist-only lyrics/chords override, same
// single-paste-box approach as the main song form. ---

function openArrangementEditor(data, content, songList) {
  const initialText = data.sections.length
    ? data.sections.map((s) => `[${s.section_name}]\n${s.raw_content || ""}`).join("\n\n")
    : "";

  const overlay = openModal(
    `
    <div class="chordpro-help" style="margin-bottom:14px;">
      Editing here only affects <strong>this setlist</strong> - the master song in your library
      stays unchanged. Paste chords + lyrics like you'd normally write them - chords on their own
      line directly above the lyric line. Start each section with a label in brackets on its own
      line, e.g. <code>[Verse 1]</code>, <code>[Chorus]</code>.
    </div>
    <textarea id="arr-textarea" rows="18" style="width:100%; font-family:'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace; font-size:0.9rem; background:var(--bg-card); border:1px solid var(--border); color:var(--text); border-radius:9px; padding:14px;" placeholder="[Verse 1]
     G                   Em7
The splendor of a King, clothed in majesty">${escapeHtml(initialText)}</textarea>
    <div class="btn-row" style="justify-content:flex-end; margin-top:20px;">
      <button type="button" class="btn" data-close-modal>Cancel</button>
      <button type="button" class="btn btn-primary" id="arr-save">Save for This Setlist</button>
    </div>
  `,
    {
      title: "Customize Arrangement",
      onMount: (modalOverlay) => {
        modalOverlay.querySelector("#arr-save").addEventListener("click", async () => {
          const raw = modalOverlay.querySelector("#arr-textarea").value;
          const parsed = raw.trim() ? parseFullSongText(raw) : [];
          const payload = parsed.map((s, i) => ({
            section_name: s.section_name,
            section_order: i,
            content: s.content,
          }));
          try {
            await api.setCustomArrangement(data.id, payload);
            closeModal();
            const fresh = await api.viewSetlistSong(data.id, data.semitones);
            renderReader(content, fresh, fresh.semitones, songList);
            toast("Arrangement saved for this setlist.", "success");
          } catch (err) {
            toast(errorMessage(err), "error");
          }
        });
      },
    }
  );
  return overlay;
}