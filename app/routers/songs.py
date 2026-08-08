from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/api/songs", tags=["songs"])


@router.get("", response_model=list[schemas.SongListItem])
def list_songs(
    search: str | None = Query(default=None, description="Search by title or artist"),
    db: Session = Depends(get_db),
):
    stmt = select(
        models.Song,
        func.count(models.SongSection.id).label("section_count"),
    ).outerjoin(models.SongSection).group_by(models.Song.id).order_by(models.Song.title.asc())

    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(or_(models.Song.title.ilike(like), models.Song.artist.ilike(like)))

    rows = db.execute(stmt).all()
    results = []
    for song, section_count in rows:
        item = schemas.SongListItem.model_validate(song)
        item.section_count = section_count
        results.append(item)
    return results


@router.post("", response_model=schemas.SongOut, status_code=201)
def create_song(payload: schemas.SongCreate, db: Session = Depends(get_db)):
    song = models.Song(
        title=payload.title.strip(),
        artist=(payload.artist or "").strip() or None,
        original_key=(payload.original_key or "").strip() or None,
        bpm=payload.bpm,
        time_signature=payload.time_signature or "4/4",
    )
    for idx, section in enumerate(payload.sections):
        song.sections.append(
            models.SongSection(
                section_name=section.section_name,
                section_order=section.section_order if section.section_order is not None else idx,
                content=section.content,
            )
        )
    db.add(song)
    db.commit()
    db.refresh(song)
    return song


def _get_song_or_404(db: Session, song_id: int) -> models.Song:
    song = db.get(
        models.Song, song_id, options=[selectinload(models.Song.sections)]
    )
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    return song


@router.get("/{song_id}", response_model=schemas.SongOut)
def get_song(song_id: int, db: Session = Depends(get_db)):
    return _get_song_or_404(db, song_id)


@router.put("/{song_id}", response_model=schemas.SongOut)
def update_song(song_id: int, payload: schemas.SongUpdate, db: Session = Depends(get_db)):
    song = _get_song_or_404(db, song_id)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        if isinstance(value, str):
            value = value.strip() or None
        setattr(song, field, value)
    if not song.title:
        raise HTTPException(status_code=422, detail="Title cannot be empty")
    db.commit()
    db.refresh(song)
    return song


@router.delete("/{song_id}", response_model=schemas.SongDeleteResult)
def delete_song(
    song_id: int,
    force: bool = Query(
        default=False,
        description="If the song is used in setlists, force=true deletes it anyway "
        "and preserves the historical data in those setlists via a snapshot.",
    ),
    db: Session = Depends(get_db),
):
    song = _get_song_or_404(db, song_id)

    usage_count = db.execute(
        select(func.count(models.SetlistSong.id)).where(models.SetlistSong.song_id == song_id)
    ).scalar_one()

    if usage_count and not force:
        raise HTTPException(
            status_code=409,
            detail=(
                f"'{song.title}' is used in {usage_count} setlist(s). "
                "Pass force=true to delete it anyway - the setlists will keep "
                "showing this song using a saved snapshot of its title/artist/key."
            ),
        )

    if usage_count:
        # Snapshot is already kept up to date at add-time, but refresh it
        # here too so the last-known values are preserved.
        setlist_songs = db.execute(
            select(models.SetlistSong).where(models.SetlistSong.song_id == song_id)
        ).scalars().all()
        for ss in setlist_songs:
            ss.song_title_snapshot = song.title
            ss.song_artist_snapshot = song.artist
            if not ss.key_override:
                ss.key_override = song.original_key

    db.delete(song)
    db.commit()
    return schemas.SongDeleteResult(
        deleted=True,
        detail="Song deleted." if not usage_count else "Song deleted; used-in setlists preserved via snapshot.",
    )
