"""
Database models.

Design notes (see README for the full rationale):

- Song / SongSection is the reusable "master" song library. Content is
  stored per-section (Intro, Verse 1, Chorus, ...) rather than as one giant
  text blob, using an inline ChordPro-style syntax where chords are written
  in square brackets directly before the lyric they sit above, e.g.:

      [E]Take me back to where
      [B]I first believed

  This keeps chords glued to the correct word even after transposition or
  reflow, and is a well-understood convention for worship musicians.

- Setlist / SetlistSong represents a specific Sunday's lineup. SetlistSong
  is the "instance" of a song within a setlist: it can override the key
  and BPM without ever touching the master Song row.

- SetlistSongSection holds a *setlist-specific* copy of the arrangement
  (sections/lyrics/chords) for when a worship leader needs to change the
  actual content for one Sunday (e.g. drop a verse, change a chord) without
  affecting the master song. It starts out empty (meaning "use the master
  song as-is") and is only populated when the leader explicitly edits the
  arrangement for that setlist - see the /setlist-songs/{id}/sections
  endpoint.

- SetlistSong also keeps a denormalized snapshot of the song's title/
  artist/key at the time it was added. If the master song is later
  deleted, the setlist keeps working and keeps showing correct historical
  data instead of silently losing it (see the song delete endpoint).
"""
from datetime import datetime, date as date_

from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    Text,
    DateTime,
    Date,
    Boolean,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """Minimal user table. Not used for auth yet (V1 has no login), but
    included now so the schema doesn't need a breaking migration when
    multi-user/multi-team support (V2) is added."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Song(Base):
    __tablename__ = "songs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    artist: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    original_key: Mapped[str | None] = mapped_column(String(10), nullable=True)
    bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time_signature: Mapped[str] = mapped_column(String(10), default="4/4", server_default="4/4")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    sections: Mapped[list["SongSection"]] = relationship(
        back_populates="song", cascade="all, delete-orphan", order_by="SongSection.section_order"
    )
    setlist_songs: Mapped[list["SetlistSong"]] = relationship(back_populates="song")


class SongSection(Base):
    __tablename__ = "song_sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    song_id: Mapped[int] = mapped_column(ForeignKey("songs.id", ondelete="CASCADE"), index=True)
    section_name: Mapped[str] = mapped_column(String(50))  # e.g. "Verse 1", "Chorus"
    section_order: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text, default="")  # ChordPro-style text
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    song: Mapped["Song"] = relationship(back_populates="sections")


class Setlist(Base):
    __tablename__ = "setlists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    date: Mapped[date_] = mapped_column(Date, index=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    setlist_songs: Mapped[list["SetlistSong"]] = relationship(
        back_populates="setlist",
        cascade="all, delete-orphan",
        order_by="SetlistSong.song_order",
    )


class SetlistSong(Base):
    """A single song "slot" inside a setlist - the instance layer between
    the reusable Song library and a specific Sunday's lineup."""

    __tablename__ = "setlist_songs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    setlist_id: Mapped[int] = mapped_column(ForeignKey("setlists.id", ondelete="CASCADE"), index=True)
    # Nullable + SET NULL: if the master song is deleted we keep the
    # historical setlist entry alive via the snapshot fields below instead
    # of destroying the setlist's data.
    song_id: Mapped[int | None] = mapped_column(
        ForeignKey("songs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    song_order: Mapped[int] = mapped_column(Integer, default=0)

    key_override: Mapped[str | None] = mapped_column(String(10), nullable=True)
    bpm_override: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Snapshot of the song's identity at the moment it was added, so the
    # setlist keeps meaning even if the master song is edited/renamed or
    # deleted later.
    song_title_snapshot: Mapped[str] = mapped_column(String(255), default="")
    song_artist_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # True once the worship leader has customized the arrangement
    # (sections/lyrics/chords) specifically for this setlist. While False,
    # the setlist view falls back to the master song's sections.
    has_custom_arrangement: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    setlist: Mapped["Setlist"] = relationship(back_populates="setlist_songs")
    song: Mapped["Song | None"] = relationship(back_populates="setlist_songs")
    override_sections: Mapped[list["SetlistSongSection"]] = relationship(
        back_populates="setlist_song",
        cascade="all, delete-orphan",
        order_by="SetlistSongSection.section_order",
    )


class SetlistSongSection(Base):
    """Setlist-specific override of a song's sections. Only present when
    has_custom_arrangement is True on the parent SetlistSong."""

    __tablename__ = "setlist_song_sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    setlist_song_id: Mapped[int] = mapped_column(
        ForeignKey("setlist_songs.id", ondelete="CASCADE"), index=True
    )
    section_name: Mapped[str] = mapped_column(String(50))
    section_order: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    setlist_song: Mapped["SetlistSong"] = relationship(back_populates="override_sections")
