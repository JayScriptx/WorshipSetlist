from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app import models, schemas
from app.chord_transpose import render_section_content, transpose_key
from app.routers.setlists import _to_setlist_song_out

router = APIRouter(tags=["setlist songs"])


@router.post("/api/setlists/{setlist_id}/songs", response_model=schemas.SetlistSongOut, status_code=201)
def add_song_to_setlist(setlist_id: int, payload: schemas.SetlistSongAdd, db: Session = Depends(get_db)):
    setlist = db.get(models.Setlist, setlist_id, options=[selectinload(models.Setlist.setlist_songs)])
    if not setlist:
        raise HTTPException(status_code=404, detail="Setlist not found")

    song = db.get(models.Song, payload.song_id)
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")

    already_present = any(s.song_id == song.id for s in setlist.setlist_songs)
    if already_present and not payload.allow_duplicate:
        raise HTTPException(
            status_code=409,
            detail=f"'{song.title}' is already in this setlist. Pass allow_duplicate=true to add it again anyway.",
        )

    max_order = max([s.song_order for s in setlist.setlist_songs], default=-1)

    setlist_song = models.SetlistSong(
        setlist_id=setlist_id,
        song_id=song.id,
        song_order=max_order + 1,
        key_override=None,
        bpm_override=None,
        notes=payload.notes,
        song_title_snapshot=song.title,
        song_artist_snapshot=song.artist,
    )
    db.add(setlist_song)
    db.commit()
    db.refresh(setlist_song)
    setlist_song.song = song
    return _to_setlist_song_out(setlist_song)


@router.delete("/api/setlists/{setlist_id}/songs/{setlist_song_id}", status_code=204)
def remove_song_from_setlist(setlist_id: int, setlist_song_id: int, db: Session = Depends(get_db)):
    setlist_song = db.get(models.SetlistSong, setlist_song_id)
    if not setlist_song or setlist_song.setlist_id != setlist_id:
        raise HTTPException(status_code=404, detail="Song not found in this setlist")
    db.delete(setlist_song)
    db.commit()
    return None


@router.put("/api/setlists/{setlist_id}/songs/reorder", response_model=list[schemas.SetlistSongOut])
def reorder_setlist_songs(setlist_id: int, payload: schemas.ReorderRequest, db: Session = Depends(get_db)):
    setlist = db.get(
        models.Setlist,
        setlist_id,
        options=[selectinload(models.Setlist.setlist_songs).selectinload(models.SetlistSong.song)],
    )
    if not setlist:
        raise HTTPException(status_code=404, detail="Setlist not found")

    song_map = {s.id: s for s in setlist.setlist_songs}
    for item in payload.order:
        setlist_song = song_map.get(item.id)
        if not setlist_song:
            raise HTTPException(status_code=400, detail=f"Setlist song {item.id} not found in this setlist")
        setlist_song.song_order = item.song_order

    db.commit()
    ordered = sorted(setlist.setlist_songs, key=lambda s: s.song_order)
    return [_to_setlist_song_out(s) for s in ordered]


def _get_setlist_song_or_404(db: Session, setlist_song_id: int) -> models.SetlistSong:
    setlist_song = db.get(
        models.SetlistSong,
        setlist_song_id,
        options=[
            selectinload(models.SetlistSong.song).selectinload(models.Song.sections),
            selectinload(models.SetlistSong.override_sections),
            selectinload(models.SetlistSong.setlist),
        ],
    )
    if not setlist_song:
        raise HTTPException(status_code=404, detail="Setlist song not found")
    return setlist_song


@router.put("/api/setlist-songs/{setlist_song_id}", response_model=schemas.SetlistSongOut)
def update_setlist_song(setlist_song_id: int, payload: schemas.SetlistSongUpdate, db: Session = Depends(get_db)):
    setlist_song = _get_setlist_song_or_404(db, setlist_song_id)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        if isinstance(value, str):
            value = value.strip() or None
        setattr(setlist_song, field, value)
    db.commit()
    db.refresh(setlist_song)
    return _to_setlist_song_out(setlist_song)


@router.get("/api/setlist-songs/{setlist_song_id}/view", response_model=schemas.SetlistSongView)
def view_setlist_song(
    setlist_song_id: int,
    transpose: int = Query(default=0, ge=-11, le=11, description="Semitones to transpose, relative to the setlist's base key"),
    db: Session = Depends(get_db),
):
    ss = _get_setlist_song_or_404(db, setlist_song_id)
    song = ss.song
    song_deleted = song is None

    title = song.title if song else ss.song_title_snapshot
    artist = song.artist if song else ss.song_artist_snapshot
    original_key = song.original_key if song else None
    base_key = ss.key_override or original_key
    current_key = transpose_key(base_key, transpose) if base_key else None
    effective_bpm = ss.bpm_override or (song.bpm if song else None)
    time_signature = song.time_signature if song else None

    if ss.has_custom_arrangement:
        source_sections = sorted(ss.override_sections, key=lambda s: s.section_order)
    else:
        source_sections = sorted(song.sections, key=lambda s: s.section_order) if song else []

    rendered_sections = []
    for sec in source_sections:
        lines = render_section_content(sec.content, transpose)
        rendered_sections.append(
            schemas.RenderedSection(
                id=sec.id,
                section_name=sec.section_name,
                section_order=sec.section_order,
                lines=[schemas.RenderedLine(**line) for line in lines],
                raw_content=sec.content,
            )
        )

    return schemas.SetlistSongView(
        id=ss.id,
        setlist_id=ss.setlist_id,
        setlist_name=ss.setlist.name,
        song_id=ss.song_id,
        title=title,
        artist=artist,
        original_key=original_key,
        base_key=base_key,
        current_key=current_key,
        semitones=transpose,
        bpm=effective_bpm,
        time_signature=time_signature,
        notes=ss.notes,
        has_custom_arrangement=ss.has_custom_arrangement,
        song_deleted=song_deleted,
        sections=rendered_sections,
    )


@router.put("/api/setlist-songs/{setlist_song_id}/sections", response_model=list[schemas.SetlistSongSectionOut])
def set_custom_arrangement(
    setlist_song_id: int, payload: schemas.SetlistSongSectionsUpdate, db: Session = Depends(get_db)
):
    """Replace this setlist song's arrangement with a custom, setlist-only
    version. This never touches the master song."""
    ss = db.get(
        models.SetlistSong, setlist_song_id, options=[selectinload(models.SetlistSong.override_sections)]
    )
    if not ss:
        raise HTTPException(status_code=404, detail="Setlist song not found")

    # Replace all override sections.
    for existing in list(ss.override_sections):
        db.delete(existing)
    db.flush()

    new_sections = []
    for idx, item in enumerate(payload.sections):
        section = models.SetlistSongSection(
            setlist_song_id=ss.id,
            section_name=item.section_name,
            section_order=item.section_order if item.section_order is not None else idx,
            content=item.content,
        )
        db.add(section)
        new_sections.append(section)

    ss.has_custom_arrangement = True
    db.commit()
    for s in new_sections:
        db.refresh(s)
    return [
        schemas.SetlistSongSectionOut.model_validate(s)
        for s in sorted(new_sections, key=lambda s: s.section_order)
    ]


@router.post("/api/setlist-songs/{setlist_song_id}/reset-arrangement", response_model=schemas.SetlistSongOut)
def reset_custom_arrangement(setlist_song_id: int, db: Session = Depends(get_db)):
    """Discard the setlist-specific arrangement and go back to using the
    master song's sections."""
    ss = _get_setlist_song_or_404(db, setlist_song_id)
    for existing in list(ss.override_sections):
        db.delete(existing)
    ss.has_custom_arrangement = False
    db.commit()
    db.refresh(ss)
    return _to_setlist_song_out(ss)
