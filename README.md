# Worship Setlist & Song Management

A clean, mobile-friendly web app for a church worship team to manage a
reusable song library, build Sunday setlists, and read lyrics/chords with
live transposition. Built with FastAPI + PostgreSQL on the backend and a
dependency-free HTML/CSS/JS frontend, so there's a single service to run
and deploy.

This is a setlist/songbook tool, **not** a presentation/projector app -
see "Future Features" at the bottom for what's intentionally left out of V1.

---

## 1. Architecture

```
worship-setlist-app/
├── app/
│   ├── main.py            FastAPI app, CORS, error handling, static hosting
│   ├── config.py          Settings from environment variables
│   ├── database.py        SQLAlchemy engine/session
│   ├── models.py          ORM models (see schema below)
│   ├── schemas.py         Pydantic request/response models
│   ├── chord_transpose.py Chord parsing/transposition + ChordPro-style rendering
│   ├── seed.py             Optional sample data for local development
│   └── routers/
│       ├── songs.py           /api/songs
│       ├── sections.py        /api/songs/{id}/sections, /api/sections/{id}
│       ├── setlists.py        /api/setlists
│       └── setlist_songs.py   /api/setlists/{id}/songs, /api/setlist-songs/{id}
├── alembic/                Database migrations
├── static/                 Frontend (plain HTML/CSS/JS, no build step)
│   ├── index.html
│   ├── css/style.css
│   └── js/{api.js,app.js}
├── requirements.txt
├── alembic.ini
├── render.yaml              Optional one-click Render Blueprint
├── .env.example
└── README.md (this file)
```

The frontend is served by the same FastAPI process (`static/` is mounted
directly), so there's only one Render service, no CORS setup needed
between frontend/backend, and no JS build pipeline.

### Data model

- **Song / SongSection** — the reusable master song library. A song's
  lyrics/chords are stored as ordered sections (Intro, Verse 1, Chorus,
  ...), each holding text in an inline **ChordPro-style** format: chords
  are written in square brackets directly before the lyric they sit above,
  e.g. `[E]Take me back to where`. This keeps chords glued to the right
  word through transposition and reflow.

- **Setlist / SetlistSong** — a specific Sunday's lineup. `SetlistSong` is
  the *instance* of a song inside a setlist: it can override key/BPM and
  carries setlist-only notes, without ever touching the master `Song` row.
  It also stores a snapshot of the song's title/artist at add-time, so if
  the master song is later deleted the setlist keeps showing correct
  historical data instead of losing it (see "Data integrity" below).

- **SetlistSongSection** — an optional, setlist-only override of a song's
  arrangement (sections/lyrics/chords), used only when a leader explicitly
  customizes a song "for this setlist" via the reader's **Customize for
  This Setlist** button. Until that happens, the setlist view simply
  displays the master song's sections.

### Chord transposition

`app/chord_transpose.py` is pure Python with no external dependencies -
it parses chord symbols (majors, minors, 7ths, sus, add, dim, aug, slash
chords like `G/B`), shifts the root (and slash bass) by N semitones, and
leaves everything outside `[brackets]` completely untouched - so numbers
or words inside lyrics are never mistaken for chords. The same function
renders a stored line into an aligned `(chord_line, lyric_line)` pair for
monospaced display.

### Data integrity

- Deleting a song that's used in setlists returns `409 Conflict` by
  default so you don't lose data by accident. Passing `?force=true`
  deletes it anyway; the setlist keeps working because it already stored
  a snapshot of the song's title/artist, and its key/BPM overrides remain.
- Adding a song that's already in a setlist returns `409 Conflict` (to
  avoid accidental duplicates); passing `allow_duplicate: true` in the
  request body adds it anyway, since intentional repeats (e.g. reprise) are
  allowed.
- All destructive UI actions ask for confirmation before calling the API.

---

## 2. Local development

### Prerequisites

- Python 3.11+
- A local PostgreSQL server (or a free hosted one, e.g. a Render Postgres
  instance, Supabase, Neon, etc.)

### Create the database

```bash
# using the psql CLI, adjust names/password as you like
createuser worship --pwprompt
createdb worship_setlist --owner worship
```

(Or create the same via any Postgres GUI - just make sure the user/db
names match what you put in `DATABASE_URL`.)

### Set up the project

```bash
python -m venv venv

# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# then edit .env and set DATABASE_URL to your local Postgres connection string
```

### Run migrations

```bash
alembic upgrade head
```

### (Optional) load sample data

```bash
python -m app.seed
```

This creates 4 sample songs and one sample setlist ("Aug 14 Sunday Line
Up") with **placeholder lyrics only** - no copyrighted lyrics are
included. Replace them with your own song content once you're up and
running.

### Run the app

```bash
uvicorn app.main:app --reload
```

Visit `http://localhost:8000` for the app, and
`http://localhost:8000/docs` for interactive API docs (Swagger UI).

---

## 3. Environment variables

| Variable            | Required | Description                                                                 |
|----------------------|----------|-------------------------------------------------------------------------------|
| `DATABASE_URL`       | Yes      | PostgreSQL connection string, e.g. `postgresql+psycopg2://user:pass@host:5432/db` |
| `SECRET_KEY`         | Yes      | Random string, reserved for future auth (session/token signing).            |
| `CORS_ORIGINS`       | No       | Comma-separated allowed origins, or `*` (default).                          |
| `AUTO_CREATE_TABLES` | No       | `true`/`false` (default `false`). Dev convenience only — creates tables from models instead of using Alembic. Never use in production. |
| `ENVIRONMENT`        | No       | Free-form label, defaults to `development`.                                 |

Never commit a real `.env` file - only `.env.example` is checked in.

---

## 4. Running database migrations

Migrations are managed with **Alembic**.

```bash
# apply all pending migrations
alembic upgrade head

# after changing app/models.py, generate a new migration
alembic revision --autogenerate -m "describe your change"

# review the generated file in alembic/versions/ before applying it
alembic upgrade head

# roll back one migration
alembic downgrade -1
```

The initial migration (`alembic/versions/0001_initial_schema.py`) creates
all tables described above.

---

## 5. Deploying to Render

### Option A — Blueprint (one click)

This repo includes `render.yaml`. In the Render dashboard: **New +** →
**Blueprint** → point it at this repo. It provisions:

- A free managed PostgreSQL database
- A web service that runs `pip install -r requirements.txt && alembic
  upgrade head` on build, then starts with
  `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Render automatically injects `DATABASE_URL` from the linked database and
generates a `SECRET_KEY` for you.

### Option B — Manual setup

1. **Create a PostgreSQL database** on Render (New + → PostgreSQL). Copy
   its **Internal Connection String**.
2. **Create a Web Service** from this repo:
   - Runtime: Python 3
   - Build command: `pip install -r requirements.txt && alembic upgrade head`
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. **Environment variables** on the web service:
   - `DATABASE_URL` → the connection string from step 1 (use
     `postgresql+psycopg2://...` - Render gives you a `postgresql://...`
     URL; either works since SQLAlchemy normalizes it, but
     `postgresql+psycopg2://` is the most explicit)
   - `SECRET_KEY` → any long random string
   - `CORS_ORIGINS` → `*` (or your custom domain once you have one)
4. Deploy. Migrations run automatically as part of the build command
   above, so the schema is always in sync with what's deployed.

### Seeding sample data on Render (optional)

Open a shell for the web service (Render dashboard → **Shell**) and run:

```bash
python -m app.seed
```

---

## 6. API overview

All endpoints are under `/api`. Full interactive docs are at `/docs`
(Swagger) and `/redoc` once the app is running.

```
GET    /api/songs                         list/search songs
POST   /api/songs                         create song (with sections)
GET    /api/songs/{id}                    get song + sections
PUT    /api/songs/{id}                    update song fields
DELETE /api/songs/{id}?force=bool         delete (409 if used in setlists, unless force=true)

GET    /api/songs/{id}/sections           list sections
POST   /api/songs/{id}/sections           add section
PUT    /api/sections/{id}                 update section
DELETE /api/sections/{id}                 delete section
PUT    /api/songs/{id}/sections/reorder   persist new section order

GET    /api/setlists                      list/search setlists
POST   /api/setlists                      create setlist
GET    /api/setlists/{id}                 get setlist + songs
PUT    /api/setlists/{id}                 update setlist
DELETE /api/setlists/{id}                 delete setlist

POST   /api/setlists/{id}/songs                     add song to setlist (409 if duplicate, unless allow_duplicate=true)
DELETE /api/setlists/{id}/songs/{setlist_song_id}   remove song from setlist
PUT    /api/setlists/{id}/songs/reorder             persist new song order

PUT    /api/setlist-songs/{id}                      update key/BPM override + notes
GET    /api/setlist-songs/{id}/view?transpose=N     rendered, transposed chord chart for the reader UI
PUT    /api/setlist-songs/{id}/sections             save a setlist-only custom arrangement
POST   /api/setlist-songs/{id}/reset-arrangement    discard custom arrangement, fall back to master song

GET    /api/health                        health check
```

---

## 7. What's intentionally NOT in V1

Per the product brief, this build focuses on reliable setlist/song
management. Not implemented yet (by design), but the schema and API are
structured so they can be added without breaking changes:

- **V2**: user accounts/auth, church/team accounts, permissions, shared
  libraries, favorites, tags, setlist duplication, export/print
- **V3**: metronome, timed cues, master timeline, synchronized team view
- **V4**: presentation/projector mode, backgrounds, multi-display, remote
  control

---

## 8. Troubleshooting

- **"relation does not exist" errors** → migrations haven't been run;
  `alembic upgrade head`.
- **App can't connect to Postgres** → double check `DATABASE_URL`
  (especially that it uses `postgresql+psycopg2://`, not just
  `postgres://`), and that the database accepts connections from your
  network/Render service.
- **Changes to `app/models.py` aren't reflected in the DB** → generate and
  apply a new migration; this app never auto-syncs the schema in
  production (`AUTO_CREATE_TABLES` is a dev-only escape hatch).
