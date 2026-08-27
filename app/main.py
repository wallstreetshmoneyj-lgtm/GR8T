"""FastAPI app: HTML routes (server-rendered Jinja2) + startup wiring.

JSON twins for every page live in app/api/routes.py under /api/... .
Startup: create tables, seed the universe if the DB is empty, kick the first
data load in the background if there are no facts yet, start the scheduler.
"""
from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app import views
from app.api.routes import router as api_router
from core.db import create_all, get_session_factory
from pipelines import scheduler as sched

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

APP_DIR = Path(__file__).resolve().parent

VALID_TABS = ("financials", "ratios", "news", "filings", "notes")


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_all()
    sched.bootstrap_if_needed()
    scheduler = sched.create_scheduler()
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="Company Research Terminal", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
app.include_router(api_router)

templates = Jinja2Templates(directory=APP_DIR / "templates")


def get_db() -> Iterator[Session]:
    with get_session_factory()() as session:
        yield session


@app.get("/", response_class=HTMLResponse)
def home(request: Request, session: Session = Depends(get_db)) -> HTMLResponse:
    return templates.TemplateResponse(request, "home.html", {
        "sectors": views.sectors(session),
    })


@app.get("/sector/{sector_name}", response_class=HTMLResponse)
def sector_page(request: Request, sector_name: str,
                session: Session = Depends(get_db)) -> HTMLResponse:
    return templates.TemplateResponse(request, "sector.html", {
        "sector": sector_name,
        "companies": views.sector_companies(session, sector_name),
    })


@app.get("/company/{ticker}", response_class=HTMLResponse)
def company_page(request: Request, ticker: str, tab: str = "financials",
                 category: str | None = None, form: str | None = None,
                 session: Session = Depends(get_db)) -> HTMLResponse:
    company = views.get_company(session, ticker)
    if company is None:
        return templates.TemplateResponse(request, "not_found.html",
                                          {"ticker": ticker}, status_code=404)
    if tab not in VALID_TABS:
        tab = "financials"
    context: dict = {
        "header": views.company_header(session, company),
        "tab": tab,
    }
    if tab == "financials":
        context["financials"] = views.financials_data(session, company.cik)
    elif tab == "ratios":
        context["ratios"] = views.ratios_data(session, company.cik, category=category)
    elif tab == "filings":
        context["filings"] = views.filings_data(session, company.cik, form=form or None)
    elif tab == "notes":
        context["notes"] = views.notes_data(session, company.cik)
    return templates.TemplateResponse(request, "company.html", context)


@app.get("/company/{ticker}/ratio/{ratio_key}", response_class=HTMLResponse)
def ratio_comps_page(request: Request, ticker: str, ratio_key: str,
                     session: Session = Depends(get_db)) -> HTMLResponse:
    company = views.get_company(session, ticker)
    if company is None:
        return templates.TemplateResponse(request, "not_found.html",
                                          {"ticker": ticker}, status_code=404)
    comps = views.ratio_comps(session, company, ratio_key)
    if comps is None:
        return templates.TemplateResponse(request, "not_found.html",
                                          {"ticker": f"ratio {ratio_key}"}, status_code=404)
    return templates.TemplateResponse(request, "ratio_comps.html", {
        "header": views.company_header(session, company),
        "comps": comps,
    })


@app.get("/status", response_class=HTMLResponse)
def status_page(request: Request, session: Session = Depends(get_db)) -> HTMLResponse:
    return templates.TemplateResponse(request, "status.html", {
        "status": views.status_data(session),
    })
