from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/api/setlists", tags=["setlists"])


def _to_setlist_song_out(ss: models.SetlistSong) -> schemas.SetlistSongOut:
    song = ss.song
    song_deleted = song is None
    title = song.title if song else ss.song_title_snapshot
    artist = song.artist if song else ss.song_artist_snapshot
    original_key = song.original_key if song else None
    effective_key = ss.key_override or original_key
    effective_bpm = ss.bpm_override or (song.bpm if song else None)

    return schemas.SetlistSongOut(
        id=ss.id,
        setlist_id=ss.setlist_id,
        song_id=ss.song_id,
        song_order=ss.song_order,
        title=title,
        artist=artist,
        key=effective_key,
        original_key=original_key,
        bpm=effective_bpm,
        key_override=ss.key_override,
        bpm_override=ss.bpm_override,
        notes=ss.notes,
        has_custom_arrangement=ss.has_custom_arrangement,
        song_deleted=song_deleted,
    )


@router.get("", response_model=list[schemas.SetlistListItem])
def list_setlists(search: str | None = Query(default=None), db: Session = Depends(get_db)):
    stmt = select(
        models.Setlist,
        func.count(models.SetlistSong.id).label("song_count"),
    ).outerjoin(models.SetlistSong).group_by(models.Setlist.id).order_by(models.Setlist.date.desc())

    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(or_(models.Setlist.name.ilike(like), models.Setlist.description.ilike(like)))

    rows = db.execute(stmt).all()
    results = []
    for setlist, song_count in rows:
        item = schemas.SetlistListItem.model_validate(setlist)
        item.song_count = song_count
        results.append(item)
    return results


@router.post("", response_model=schemas.SetlistOut, status_code=201)
def create_setlist(payload: schemas.SetlistCreate, db: Session = Depends(get_db)):
    setlist = models.Setlist(
        name=payload.name.strip(),
        date=payload.date,
        description=(payload.description or "").strip() or None,
    )
    db.add(setlist)
    db.commit()
    db.refresh(setlist)
    return schemas.SetlistOut(
        id=setlist.id,
        name=setlist.name,
        date=setlist.date,
        description=setlist.description,
        created_at=setlist.created_at,
        updated_at=setlist.updated_at,
        songs=[],
    )


def _get_setlist_or_404(db: Session, setlist_id: int) -> models.Setlist:
    setlist = db.get(
        models.Setlist,
        setlist_id,
        options=[selectinload(models.Setlist.setlist_songs).selectinload(models.SetlistSong.song)],
    )
    if not setlist:
        raise HTTPException(status_code=404, detail="Setlist not found")
    return setlist


@router.get("/{setlist_id}", response_model=schemas.SetlistOut)
def get_setlist(setlist_id: int, db: Session = Depends(get_db)):
    setlist = _get_setlist_or_404(db, setlist_id)
    songs = sorted(setlist.setlist_songs, key=lambda s: s.song_order)
    return schemas.SetlistOut(
        id=setlist.id,
        name=setlist.name,
        date=setlist.date,
        description=setlist.description,
        created_at=setlist.created_at,
        updated_at=setlist.updated_at,
        songs=[_to_setlist_song_out(s) for s in songs],
    )


@router.put("/{setlist_id}", response_model=schemas.SetlistOut)
def update_setlist(setlist_id: int, payload: schemas.SetlistUpdate, db: Session = Depends(get_db)):
    setlist = _get_setlist_or_404(db, setlist_id)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        if isinstance(value, str):
            value = value.strip() or None
        setattr(setlist, field, value)
    if not setlist.name:
        raise HTTPException(status_code=422, detail="Name cannot be empty")
    db.commit()
    db.refresh(setlist)
    songs = sorted(setlist.setlist_songs, key=lambda s: s.song_order)
    return schemas.SetlistOut(
        id=setlist.id,
        name=setlist.name,
        date=setlist.date,
        description=setlist.description,
        created_at=setlist.created_at,
        updated_at=setlist.updated_at,
        songs=[_to_setlist_song_out(s) for s in songs],
    )


@router.delete("/{setlist_id}", status_code=204)
def delete_setlist(setlist_id: int, db: Session = Depends(get_db)):
    setlist = db.get(models.Setlist, setlist_id)
    if not setlist:
        raise HTTPException(status_code=404, detail="Setlist not found")
    db.delete(setlist)
    db.commit()
    return None
