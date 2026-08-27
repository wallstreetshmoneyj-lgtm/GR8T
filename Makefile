# Company Research Terminal — common commands (see CLAUDE.md)

.PHONY: run seed refresh refresh-universe seed-peers coverage test lint

# The one run command: creates tables, seeds the universe if needed, starts
# the scheduler, and kicks off the initial data load in the background.
run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000

seed:
	python -m pipelines.run seed

# Full manual data refresh (filings + statements + ratios + coverage report)
refresh:
	python -m pipelines.run refresh

# Regenerate a candidate sp500.csv and print a diff for manual review.
# Never auto-overwrites the live seed file.
refresh-universe:
	python -m scripts.refresh_universe

# Generate peers.json (writes peers.candidate.json if one already exists)
seed-peers:
	python -m pipelines.run peers

coverage:
	python -m pipelines.run coverage

test:
	python -m pytest -q

lint:
	ruff check . && ruff format --check .
