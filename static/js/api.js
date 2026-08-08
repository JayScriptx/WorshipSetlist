// Thin wrapper around fetch() for talking to the FastAPI backend.
// Every function returns a Promise that resolves to parsed JSON, and
// throws an Error with a user-friendly message on failure.

const API_BASE = "/api";

async function request(method, path, body) {
  let res;
  try {
    res = await fetch(API_BASE + path, {
      method,
      headers: body !== undefined ? { "Content-Type": "application/json" } : {},
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (networkErr) {
    throw new Error("Can't reach the server. Check your connection and try again.");
  }

  if (res.status === 204) return null;

  let data = null;
  try {
    data = await res.json();
  } catch (e) {
    // No JSON body (e.g. some error pages) - fall through with null data.
  }

  if (!res.ok) {
    const detail = (data && (data.detail || data.message)) || `Request failed (${res.status}).`;
    const err = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    err.status = res.status;
    throw err;
  }

  return data;
}

const api = {
  // Songs
  listSongs: (search) => request("GET", `/songs${search ? "?search=" + encodeURIComponent(search) : ""}`),
  getSong: (id) => request("GET", `/songs/${id}`),
  createSong: (payload) => request("POST", "/songs", payload),
  updateSong: (id, payload) => request("PUT", `/songs/${id}`, payload),
  deleteSong: (id, force) => request("DELETE", `/songs/${id}${force ? "?force=true" : ""}`),

  // Sections
  createSection: (songId, payload) => request("POST", `/songs/${songId}/sections`, payload),
  updateSection: (sectionId, payload) => request("PUT", `/sections/${sectionId}`, payload),
  deleteSection: (sectionId) => request("DELETE", `/sections/${sectionId}`),
  reorderSections: (songId, order) => request("PUT", `/songs/${songId}/sections/reorder`, { order }),

  // Setlists
  listSetlists: (search) => request("GET", `/setlists${search ? "?search=" + encodeURIComponent(search) : ""}`),
  getSetlist: (id) => request("GET", `/setlists/${id}`),
  createSetlist: (payload) => request("POST", "/setlists", payload),
  updateSetlist: (id, payload) => request("PUT", `/setlists/${id}`, payload),
  deleteSetlist: (id) => request("DELETE", `/setlists/${id}`),

  // Setlist songs
  addSongToSetlist: (setlistId, songId, notes, allowDuplicate) =>
    request("POST", `/setlists/${setlistId}/songs`, {
      song_id: songId,
      notes: notes || null,
      allow_duplicate: !!allowDuplicate,
    }),
  removeSongFromSetlist: (setlistId, setlistSongId) =>
    request("DELETE", `/setlists/${setlistId}/songs/${setlistSongId}`),
  reorderSetlistSongs: (setlistId, order) =>
    request("PUT", `/setlists/${setlistId}/songs/reorder`, { order }),
  updateSetlistSong: (setlistSongId, payload) => request("PUT", `/setlist-songs/${setlistSongId}`, payload),
  viewSetlistSong: (setlistSongId, transpose) =>
    request("GET", `/setlist-songs/${setlistSongId}/view?transpose=${transpose || 0}`),
  setCustomArrangement: (setlistSongId, sections) =>
    request("PUT", `/setlist-songs/${setlistSongId}/sections`, { sections }),
  resetArrangement: (setlistSongId) => request("POST", `/setlist-songs/${setlistSongId}/reset-arrangement`),
};
