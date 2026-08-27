"""JSON API: every page's data as JSON (SPEC 3), plus notes CRUD + export.

Notes endpoints are the ONLY code path that creates, edits, or deletes note
rows (SPEC 9.9) — pipelines never touch the notes table.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import views
from core.db import Company, Note, get_session_factory

router = APIRouter(prefix="/api")


def get_db() -> Iterator[Session]:
    with get_session_factory()() as session:
        yield session


def _company_or_404(session: Session, ticker: str) -> Company:
    company = views.get_company(session, ticker)
    if company is None:
        raise HTTPException(status_code=404, detail=f"unknown ticker {ticker}")
    return company


@router.get("/search")
def search(q: str = "", session: Session = Depends(get_db)) -> list[dict]:
    return views.search_companies(session, q)


@router.get("/sectors")
def sectors(session: Session = Depends(get_db)) -> list[dict]:
    return views.sectors(session)


@router.get("/sector/{sector_name}")
def sector(sector_name: str, session: Session = Depends(get_db)) -> dict:
    return {"sector": sector_name, "companies": views.sector_companies(session, sector_name)}


@router.get("/company/{ticker}")
def company(ticker: str, session: Session = Depends(get_db)) -> dict:
    return views.company_header(session, _company_or_404(session, ticker))


@router.get("/company/{ticker}/financials")
def financials(ticker: str, session: Session = Depends(get_db)) -> dict:
    return views.financials_data(session, _company_or_404(session, ticker).cik)


@router.get("/company/{ticker}/ratios")
def ratios(ticker: str, category: str | None = None,
           session: Session = Depends(get_db)) -> dict:
    return views.ratios_data(session, _company_or_404(session, ticker).cik, category=category)


@router.get("/company/{ticker}/ratios/{ratio_key}/comps")
def ratio_comps(ticker: str, ratio_key: str, session: Session = Depends(get_db)) -> dict:
    comps = views.ratio_comps(session, _company_or_404(session, ticker), ratio_key)
    if comps is None:
        raise HTTPException(status_code=404, detail=f"unknown ratio {ratio_key}")
    return comps


@router.get("/company/{ticker}/filings")
def filings(ticker: str, form: str | None = None,
            session: Session = Depends(get_db)) -> dict:
    return views.filings_data(session, _company_or_404(session, ticker).cik, form=form or None)


@router.get("/status")
def status(session: Session = Depends(get_db)) -> dict:
    return views.status_data(session)


# ---------- notes (SPEC 9.9) ----------

class NoteBody(BaseModel):
    content: str = ""


@router.get("/company/{ticker}/notes")
def list_notes(ticker: str, session: Session = Depends(get_db)) -> list[dict]:
    return views.notes_data(session, _company_or_404(session, ticker).cik)


@router.post("/company/{ticker}/notes", status_code=201)
def create_note(ticker: str, body: NoteBody, session: Session = Depends(get_db)) -> dict:
    company = _company_or_404(session, ticker)
    now = _now()
    note = Note(cik=company.cik, content=body.content, created_at=now, updated_at=now)
    session.add(note)
    session.commit()
    return views.note_dict(note)


@router.put("/notes/{note_id}")
def update_note(note_id: int, body: NoteBody, session: Session = Depends(get_db)) -> dict:
    note = session.get(Note, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="note not found")
    note.content = body.content
    note.updated_at = _now()
    session.commit()
    return views.note_dict(note)


@router.delete("/notes/{note_id}")
def delete_note(note_id: int, session: Session = Depends(get_db)) -> dict:
    """The one and only deletion path for a note — reached exclusively from
    the confirmed delete action in the notes UI."""
    note = session.get(Note, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="note not found")
    session.delete(note)
    session.commit()
    return {"deleted": note_id}


@router.get("/notes/export")
def export_notes(session: Session = Depends(get_db)) -> PlainTextResponse:
    """All notes as one markdown file, grouped by company — the one-click
    backup of the owner's own writing (SPEC 9.9)."""
    notes = list(session.execute(select(Note).order_by(Note.cik, Note.created_at)).scalars())
    companies = {c.cik: c for c in session.execute(select(Company)).scalars()}
    lines = [f"# Research notes export ({dt.date.today().isoformat()})", ""]
    current_cik = None
    for note in notes:
        if note.cik != current_cik:
            current_cik = note.cik
            company = companies.get(note.cik)
            title = f"{company.ticker} — {company.name}" if company else f"CIK {note.cik}"
            lines += [f"## {title}", ""]
        lines += [f"### Note {note.id} (created {note.created_at}, updated {note.updated_at})",
                  "", note.content, ""]
    return PlainTextResponse(
        "\n".join(lines),
        media_type="text/markdown",
        headers={"Content-Disposition": 'attachment; filename="notes_export.md"'},
    )


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC).replace(tzinfo=None)
