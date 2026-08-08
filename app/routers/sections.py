from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas

router = APIRouter(tags=["song sections"])


@router.get("/api/songs/{song_id}/sections", response_model=list[schemas.SongSectionOut])
def list_sections(song_id: int, db: Session = Depends(get_db)):
    song = db.get(models.Song, song_id)
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    return sorted(song.sections, key=lambda s: s.section_order)


@router.post("/api/songs/{song_id}/sections", response_model=schemas.SongSectionOut, status_code=201)
def create_section(song_id: int, payload: schemas.SongSectionCreate, db: Session = Depends(get_db)):
    song = db.get(models.Song, song_id)
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")

    if payload.section_order is None:
        max_order = max([s.section_order for s in song.sections], default=-1)
        order = max_order + 1
    else:
        order = payload.section_order

    section = models.SongSection(
        song_id=song_id,
        section_name=payload.section_name,
        section_order=order,
        content=payload.content,
    )
    db.add(section)
    db.commit()
    db.refresh(section)
    return section


@router.put("/api/sections/{section_id}", response_model=schemas.SongSectionOut)
def update_section(section_id: int, payload: schemas.SongSectionUpdate, db: Session = Depends(get_db)):
    section = db.get(models.SongSection, section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(section, field, value)
    db.commit()
    db.refresh(section)
    return section


@router.delete("/api/sections/{section_id}", status_code=204)
def delete_section(section_id: int, db: Session = Depends(get_db)):
    section = db.get(models.SongSection, section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    db.delete(section)
    db.commit()
    return None


@router.put("/api/songs/{song_id}/sections/reorder", response_model=list[schemas.SongSectionOut])
def reorder_sections(song_id: int, payload: schemas.SectionReorderRequest, db: Session = Depends(get_db)):
    song = db.get(models.Song, song_id)
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")

    section_map = {s.id: s for s in song.sections}
    for item in payload.order:
        section = section_map.get(item.id)
        if not section:
            raise HTTPException(status_code=400, detail=f"Section {item.id} does not belong to this song")
        section.section_order = item.section_order

    db.commit()
    return sorted(song.sections, key=lambda s: s.section_order)
