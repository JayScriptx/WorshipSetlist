from datetime import datetime, date as date_
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Song sections
# ---------------------------------------------------------------------------

class SongSectionBase(BaseModel):
    section_name: str = Field(..., max_length=50, examples=["Verse 1"])
    section_order: int = 0
    content: str = ""


class SongSectionCreate(SongSectionBase):
    pass


class SongSectionUpdate(BaseModel):
    section_name: str | None = None
    section_order: int | None = None
    content: str | None = None


class SongSectionOut(SongSectionBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    song_id: int


class SectionReorderItem(BaseModel):
    id: int
    section_order: int


class SectionReorderRequest(BaseModel):
    order: list[SectionReorderItem]


# ---------------------------------------------------------------------------
# Songs
# ---------------------------------------------------------------------------

class SongBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    artist: str | None = Field(default=None, max_length=255)
    original_key: str | None = Field(default=None, max_length=10)
    bpm: int | None = Field(default=None, ge=1, le=400)
    time_signature: str = Field(default="4/4", max_length=10)


class SongCreate(SongBase):
    sections: list[SongSectionCreate] = []


class SongUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    artist: str | None = None
    original_key: str | None = None
    bpm: int | None = Field(default=None, ge=1, le=400)
    time_signature: str | None = None


class SongListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    artist: str | None
    original_key: str | None
    bpm: int | None
    time_signature: str
    section_count: int = 0


class SongOut(SongBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime
    sections: list[SongSectionOut] = []


class SongDeleteResult(BaseModel):
    deleted: bool
    detail: str


# ---------------------------------------------------------------------------
# Setlists
# ---------------------------------------------------------------------------

class SetlistBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    date: date_
    description: str | None = Field(default=None, max_length=500)


class SetlistCreate(SetlistBase):
    pass


class SetlistUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    date: date_ | None = None
    description: str | None = None


class SetlistListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    date: date_
    description: str | None
    song_count: int = 0
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Setlist songs (the "instance" of a song within a setlist)
# ---------------------------------------------------------------------------

class SetlistSongAdd(BaseModel):
    song_id: int
    notes: str | None = None
    allow_duplicate: bool = False


class SetlistSongUpdate(BaseModel):
    key_override: str | None = None
    bpm_override: int | None = Field(default=None, ge=1, le=400)
    notes: str | None = None


class SetlistSongOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    setlist_id: int
    song_id: int | None
    song_order: int
    title: str
    artist: str | None
    key: str | None            # effective key = override or master song's key
    original_key: str | None   # master song's original key, for reference
    bpm: int | None            # effective bpm = override or master song's bpm
    key_override: str | None
    bpm_override: int | None
    notes: str | None
    has_custom_arrangement: bool
    song_deleted: bool         # True if the master song no longer exists


class ReorderItem(BaseModel):
    id: int
    song_order: int


class ReorderRequest(BaseModel):
    order: list[ReorderItem]


class SetlistOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    date: date_
    description: str | None
    created_at: datetime
    updated_at: datetime
    songs: list[SetlistSongOut] = []


# ---------------------------------------------------------------------------
# Setlist song detail / performance view (with rendered + transposed chords)
# ---------------------------------------------------------------------------

class RenderedLine(BaseModel):
    chord_line: str
    lyric_line: str
    has_chords: bool


class RenderedSection(BaseModel):
    id: int | None
    section_name: str
    section_order: int
    lines: list[RenderedLine]
    raw_content: str


class SetlistSongView(BaseModel):
    id: int
    setlist_id: int
    setlist_name: str
    song_id: int | None
    title: str
    artist: str | None
    original_key: str | None
    base_key: str              # key before transpose (override or original)
    current_key: str | None    # base_key transposed by `semitones`
    semitones: int
    bpm: int | None
    time_signature: str | None
    notes: str | None
    has_custom_arrangement: bool
    song_deleted: bool
    sections: list[RenderedSection]


class SetlistSongSectionIn(BaseModel):
    section_name: str = Field(..., max_length=50)
    section_order: int = 0
    content: str = ""


class SetlistSongSectionsUpdate(BaseModel):
    sections: list[SetlistSongSectionIn]


class SetlistSongSectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    setlist_song_id: int
    section_name: str
    section_order: int
    content: str
