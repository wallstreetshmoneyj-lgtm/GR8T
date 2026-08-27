"""Universe + peers seed-file loading (and peer auto-seeding).

The seed files are manually maintained (SPEC Section 5): this module only
READS them at startup, and the generators never overwrite an existing file —
they write *.candidate.* siblings for manual review instead.
"""
from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import settings
from core.db import Company, StatementFact

log = logging.getLogger(__name__)

SP500_CSV = settings.seed_dir / "sp500.csv"
PEERS_JSON = settings.seed_dir / "peers.json"

# Owner's hand-tuned peer sets (SPEC 17.3). Applied on top of the GICS
# auto-seed; the owner extends this by editing peers.json directly.
OWNER_PEER_OVERRIDES: dict[str, list[str]] = {
    "ORCL": ["MSFT", "IBM", "CRM", "SAP"],
}


def load_universe(session: Session, csv_path: Path = SP500_CSV) -> dict:
    """Sync the companies table from the seed CSV. Companies that vanish from
    the CSV are marked inactive, never deleted — their facts and notes stay
    readable at their URLs (SPEC 9.9)."""
    if not csv_path.exists():
        raise FileNotFoundError(
            f"{csv_path} not found. Run `make refresh-universe` (see CLAUDE.md) to generate it."
        )
    seen_ciks: set[str] = set()
    added = updated = 0
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            cik = row["cik"].strip().zfill(10)
            seen_ciks.add(cik)
            company = session.get(Company, cik)
            values = {
                "ticker": row["ticker"].strip().upper(),
                "name": row["company_name"].strip(),
                "gics_sector": row["gics_sector"].strip(),
                "gics_sub_industry": row["gics_sub_industry"].strip(),
                "ir_url": row.get("ir_url", "").strip() or None,
                "active": row.get("active", "true").strip().lower() in ("true", "1", "yes"),
            }
            if company is None:
                session.add(Company(cik=cik, **values))
                added += 1
            else:
                for key, val in values.items():
                    setattr(company, key, val)
                updated += 1
    deactivated = 0
    for company in session.execute(select(Company)).scalars():
        if company.cik not in seen_ciks and company.active:
            company.active = False
            deactivated += 1
    session.commit()
    log.info("universe: %d added, %d updated, %d deactivated", added, updated, deactivated)
    return {"added": added, "updated": updated, "deactivated": deactivated}


def load_peers() -> dict[str, list[str]]:
    if not PEERS_JSON.exists():
        return {}
    try:
        return json.loads(PEERS_JSON.read_text())
    except json.JSONDecodeError:
        log.warning("peers.json is not valid JSON; rendering pages without peers")
        return {}


def generate_peers(session: Session) -> dict[str, list[str]]:
    """Auto-seed peers: each company's 4 largest GICS sub-industry siblings
    by latest-FY revenue (SPEC 12). Falls back to alphabetical siblings when
    revenue isn't loaded yet. Owner overrides (SPEC 17.3) are applied last."""
    companies = list(session.execute(select(Company).where(Company.active)).scalars())

    newest_revenue: dict[str, tuple[int, float]] = {}
    for fact in session.execute(
        select(StatementFact).where(StatementFact.canonical_item == "revenue")
    ).scalars():
        current = newest_revenue.get(fact.cik)
        # keep the newest FY's revenue per company
        if current is None or fact.fiscal_year > current[0]:
            newest_revenue[fact.cik] = (fact.fiscal_year, fact.value or 0.0)
    latest_revenue = {cik: v for cik, (_, v) in newest_revenue.items()}

    by_sub_industry: dict[str, list[Company]] = {}
    for company in companies:
        by_sub_industry.setdefault(company.gics_sub_industry, []).append(company)

    peers: dict[str, list[str]] = {}
    for company in companies:
        siblings = [c for c in by_sub_industry[company.gics_sub_industry]
                    if c.cik != company.cik]
        siblings.sort(key=lambda c: (-latest_revenue.get(c.cik, 0.0), c.ticker))
        peers[company.ticker] = [c.ticker for c in siblings[:4]]
    peers.update(OWNER_PEER_OVERRIDES)
    return dict(sorted(peers.items()))


def write_peers_seed(session: Session) -> Path:
    """Write peers.json if absent; otherwise write peers.candidate.json for
    manual review (hand-tuned peer sets must never be clobbered)."""
    peers = generate_peers(session)
    target = PEERS_JSON if not PEERS_JSON.exists() else settings.seed_dir / "peers.candidate.json"
    settings.seed_dir.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(peers, indent=2) + "\n")
    log.info("wrote %s (%d companies)", target, len(peers))
    return target
