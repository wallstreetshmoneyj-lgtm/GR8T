"""Route smoke tests, including graceful degradation: a company with no
data yet must render "-"/"n/a", never a 500 (SPEC 15)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from core.db import Company


@pytest.fixture
def client(db, orcl_company, monkeypatch):
    """App wired to the temp DB, with the scheduler and initial refresh
    stubbed out so tests never touch the network."""
    from pipelines import scheduler

    monkeypatch.setattr(scheduler, "bootstrap_if_needed", lambda: None)
    monkeypatch.setattr(scheduler, "create_scheduler", lambda: _NullScheduler())

    with db() as session:
        session.add(Company(cik="0000789019", ticker="MSFT", name="Microsoft",
                            gics_sector="Information Technology",
                            gics_sub_industry="Systems Software", active=True))
        session.commit()

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


class _NullScheduler:
    def start(self) -> None: ...
    def shutdown(self, wait: bool = False) -> None: ...


class TestPagesRenderWithoutData:
    """Every Phase 1 page against a company with zero facts/ratios/filings."""

    @pytest.mark.parametrize("path", [
        "/",
        "/status",
        "/sector/Information%20Technology",
        "/company/ORCL",
        "/company/ORCL?tab=financials",
        "/company/ORCL?tab=ratios",
        "/company/ORCL?tab=ratios&category=Profitability",
        "/company/ORCL?tab=news",
        "/company/ORCL?tab=filings",
        "/company/ORCL?tab=filings&form=10-K",
        "/company/ORCL?tab=notes",
        "/company/ORCL/ratio/roe",
    ])
    def test_page_renders(self, client, path):
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} -> {resp.status_code}"

    def test_unknown_ticker_is_404_not_500(self, client):
        assert client.get("/company/NOPE").status_code == 404

    def test_unknown_ratio_is_404_not_500(self, client):
        assert client.get("/company/ORCL/ratio/not_a_ratio").status_code == 404

    def test_unknown_tab_falls_back_to_financials(self, client):
        resp = client.get("/company/ORCL?tab=../../etc/passwd")
        assert resp.status_code == 200
        assert "INCOME STATEMENT" in resp.text or "No statement data yet" in resp.text


class TestApiTwins:
    """Every page's data is also available as JSON (SPEC 3)."""

    @pytest.mark.parametrize("path", [
        "/api/search?q=ora",
        "/api/sectors",
        "/api/sector/Information%20Technology",
        "/api/company/ORCL",
        "/api/company/ORCL/financials",
        "/api/company/ORCL/ratios",
        "/api/company/ORCL/filings",
        "/api/company/ORCL/ratios/roe/comps",
        "/api/company/ORCL/notes",
        "/api/status",
    ])
    def test_endpoint_returns_json(self, client, path):
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} -> {resp.status_code}"
        resp.json()

    def test_search_matches_ticker_prefix_and_name_substring(self, client):
        assert any(r["ticker"] == "ORCL" for r in client.get("/api/search?q=orc").json())
        assert any(r["ticker"] == "ORCL" for r in client.get("/api/search?q=oracle").json())
        # case-insensitive on both sides
        assert any(r["ticker"] == "ORCL" for r in client.get("/api/search?q=ORACLE").json())
        assert client.get("/api/search?q=").json() == []

    def test_unknown_ticker_api_is_404(self, client):
        assert client.get("/api/company/NOPE/financials").status_code == 404


class TestNotesApi:
    def test_create_edit_delete_roundtrip(self, client):
        created = client.post("/api/company/ORCL/notes",
                              json={"content": "# thesis\n\n- **RPO** growth"})
        assert created.status_code == 201
        note = created.json()
        assert "<strong>RPO</strong>" in note["html"]  # markdown rendered

        updated = client.put(f"/api/notes/{note['id']}", json={"content": "revised"})
        assert updated.status_code == 200
        assert updated.json()["content"] == "revised"
        assert updated.json()["updated_at"] >= note["created_at"]

        assert client.get("/api/company/ORCL/notes").json()[0]["content"] == "revised"

        assert client.delete(f"/api/notes/{note['id']}").status_code == 200
        assert client.get("/api/company/ORCL/notes").json() == []

    def test_notes_count_badge_reflects_reality(self, client):
        assert client.get("/api/company/ORCL").json()["notes_count"] == 0
        client.post("/api/company/ORCL/notes", json={"content": "note"})
        assert client.get("/api/company/ORCL").json()["notes_count"] == 1

    def test_export_groups_notes_by_company(self, client):
        client.post("/api/company/ORCL/notes", json={"content": "oracle note"})
        client.post("/api/company/MSFT/notes", json={"content": "microsoft note"})
        body = client.get("/api/notes/export").text
        assert "ORCL — Oracle Corporation" in body
        assert "MSFT — Microsoft" in body
        assert "oracle note" in body and "microsoft note" in body

    def test_editing_a_missing_note_is_404(self, client):
        assert client.put("/api/notes/9999", json={"content": "x"}).status_code == 404
        assert client.delete("/api/notes/9999").status_code == 404


class TestPagesWithData:
    @pytest.fixture
    def loaded(self, client, db, orcl_company, orcl_facts, orcl_submissions):
        from pipelines import filings, statements

        with db() as session:
            filings.refresh_company(session, orcl_company, subs_json=orcl_submissions)
            statements.refresh_company(session, orcl_company, facts_json=orcl_facts)
        return client

    def test_financials_shows_five_years_and_pct_changes(self, loaded):
        html = loaded.get("/company/ORCL?tab=financials").text
        for fy in range(2022, 2027):
            assert f"FY{fy}" in html
        assert "67,357" in html  # FY2026 revenue, $M
        assert "+17.3%" in html  # revenue YoY vs FY2025's 57,399

    def test_financials_cells_carry_the_xbrl_tag_tooltip(self, loaded):
        html = loaded.get("/company/ORCL?tab=financials").text
        assert "RevenueFromContractWithCustomerExcludingAssessedTax" in html

    def test_ratios_show_na_reason_for_negative_equity(self, loaded):
        html = loaded.get("/company/ORCL?tab=ratios&category=Profitability").text
        assert "non-positive average equity" in html

    def test_comps_table_includes_the_peer_set(self, loaded):
        # peers.json seeds ORCL as [MSFT, IBM, CRM, SAP] (SPEC 17.3)
        html = loaded.get("/company/ORCL/ratio/roe").text
        for peer in ("MSFT", "IBM", "CRM", "SAP"):
            assert peer in html

    def test_filings_tab_links_out_to_edgar(self, loaded):
        html = loaded.get("/company/ORCL?tab=filings&form=10-K").text
        assert "sec.gov/Archives/edgar/data/1341439" in html

    def test_latest_and_prior_10k_links_are_distinct(self, loaded):
        header = loaded.get("/api/company/ORCL").json()
        assert header["latest_10k"]["url"] != header["prior_10k"]["url"]
        assert header["latest_10k"]["filed_date"] > header["prior_10k"]["filed_date"]

    def test_financials_json_matches_the_page(self, loaded):
        data = loaded.get("/api/company/ORCL/financials").json()
        assert data["years"][0] == 2026
        assert data["period_ends"]["2026"] == "2026-05-31"
        income = next(s for s in data["statements"] if s["code"] == "IS")
        revenue = next(r for r in income["rows"] if r["item"] == "revenue")
        assert revenue["cells"][0]["value"] == 67_357_000_000
