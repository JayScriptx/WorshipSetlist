"""
Populates the database with sample songs and a sample setlist so the app
is immediately usable in development.

All lyrics/chords below are original placeholder text written for this
seed script - NOT the actual lyrics of any copyrighted song - even though
the song titles/artists/keys/BPM mirror the examples from the product
brief, so this is safe to commit and share.

Run with:
    python -m app.seed
"""
import datetime

from app.database import SessionLocal, Base, engine
from app import models


PLACEHOLDER_VERSE_1 = "[E]This is a placeholder line one\n[B]This is a placeholder line two"
PLACEHOLDER_CHORUS = "[C#m]Placeholder chorus line one\n[A]Placeholder chorus line two"
PLACEHOLDER_BRIDGE = "[A]Placeholder bridge line\n[E]Bringing it back home"


SEED_SONGS = [
    {
        "title": "Take Me Back",
        "artist": "Placeholder Worship",
        "original_key": "E",
        "bpm": 120,
        "time_signature": "4/4",
        "sections": [
            ("Intro", "E   B   C#m   A"),
            ("Verse 1", PLACEHOLDER_VERSE_1),
            ("Chorus", PLACEHOLDER_CHORUS),
            ("Verse 2", PLACEHOLDER_VERSE_1),
            ("Chorus", PLACEHOLDER_CHORUS),
            ("Bridge", PLACEHOLDER_BRIDGE),
            ("Chorus", PLACEHOLDER_CHORUS),
            ("Outro", "E   B   C#m   A"),
        ],
    },
    {
        "title": "We Raise",
        "artist": "Placeholder Worship",
        "original_key": "E",
        "bpm": 128,
        "time_signature": "4/4",
        "sections": [
            ("Intro", "E   A   B"),
            ("Verse 1", PLACEHOLDER_VERSE_1),
            ("Pre-Chorus", "[A]Placeholder pre-chorus line"),
            ("Chorus", PLACEHOLDER_CHORUS),
            ("Bridge", PLACEHOLDER_BRIDGE),
        ],
    },
    {
        "title": "Prophecy",
        "artist": "Placeholder Worship",
        "original_key": "G",
        "bpm": 96,
        "time_signature": "4/4",
        "sections": [
            ("Intro", "G   D   Em   C"),
            ("Verse 1", "[G]Placeholder verse line one\n[D]Placeholder verse line two"),
            ("Chorus", "[Em]Placeholder chorus line\n[C]Bringing this line home"),
            ("Instrumental", "G   D   Em   C"),
        ],
    },
    {
        "title": "Praise",
        "artist": "Placeholder Worship",
        "original_key": "A",
        "bpm": 140,
        "time_signature": "4/4",
        "sections": [
            ("Intro", "A   E   F#m   D"),
            ("Verse 1", "[A]Placeholder verse line one\n[E]Placeholder verse line two"),
            ("Chorus", "[F#m]Placeholder chorus line\n[D]Big and celebratory"),
            ("Outro", "A   E   F#m   D"),
        ],
    },
]


def run():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(models.Song).count() > 0:
            print("Songs already exist - skipping seed to avoid duplicates.")
            return

        songs_by_title = {}
        for data in SEED_SONGS:
            song = models.Song(
                title=data["title"],
                artist=data["artist"],
                original_key=data["original_key"],
                bpm=data["bpm"],
                time_signature=data["time_signature"],
            )
            for order, (name, content) in enumerate(data["sections"]):
                song.sections.append(
                    models.SongSection(section_name=name, section_order=order, content=content)
                )
            db.add(song)
            songs_by_title[data["title"]] = song

        db.commit()

        setlist = models.Setlist(
            name="Aug 14 Sunday Line Up",
            date=datetime.date(2026, 8, 14),
            description="Sunday Worship Service",
        )
        db.add(setlist)
        db.commit()

        for order, title in enumerate(["Take Me Back", "We Raise", "Prophecy", "Praise"]):
            song = songs_by_title[title]
            db.add(
                models.SetlistSong(
                    setlist_id=setlist.id,
                    song_id=song.id,
                    song_order=order,
                    song_title_snapshot=song.title,
                    song_artist_snapshot=song.artist,
                )
            )
        db.commit()
        print(f"Seeded {len(SEED_SONGS)} songs and 1 setlist ('{setlist.name}').")
    finally:
        db.close()


if __name__ == "__main__":
    run()
