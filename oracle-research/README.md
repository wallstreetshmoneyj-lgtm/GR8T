# Oracle (ORCL) — independent equity research

Self-directed fundamental analysis of Oracle Corporation, built from primary filings.
**Not investment advice.**

| | |
|---|---|
| Model date | 28 August 2026 |
| Market data | 27 August 2026 close · ORCL $151.94 |
| Primary source | FY2026 Form 10-K — SEC EDGAR CIK 0001341439, accession `0001193125-26-277521`, filed 22 June 2026 (FYE 31 May 2026) |
| Secondary primary | Q4/FY26 press release — Exhibit 99.1 to Form 8-K filed 10 June 2026, accession `0001193125-26-265848` |
| Comps source | stockanalysis.com — single source, pulled 27–28 August 2026 |
| Risk-free rate | 10-year UST (^TNX) 4.672%, 27 August 2026 |

## Conclusion

**HOLD**, negative skew. Target **$125** (−18%). **Low confidence.**

At $151.94, roughly **68% of the share price is paying for business Oracle has not yet signed**.
The disclosed backlog plus the legacy software annuity support **$45–76 per share** depending on
how the annuity is valued. The probability-weighted DCF lands at **$116–128**.

The central question — whether the AI buildout clears its cost of capital — is answered as a
**breakeven, not a point estimate**, because the two variables that decide it (OCI utilisation
and asset turn) are not disclosed anywhere.

## Deliverables

| File | What it is |
|---|---|
| `ORCL_memo.md` | The research memo: thesis, corrections to the working data pack, forecast, valuation, scenarios, risks, recommendation, and the case against it |
| `ORCL_model.xlsx` | 16-tab model with live Google-Sheets-compatible formulas and a formula audit tab |
| `ORCL_comps.md` | Two calendarised comp sets, source and date stamped, every cell tagged consensus vs. estimate |
| `ORCL_open_questions.md` | What could not be resolved from public information, ranked by how much the answer would move the valuation |

**Not included:** the line-by-line variance bridge against the analyst's own model
(brief §2.2) — that file had not been supplied when this was built. It runs as a standalone pass.

## Workbook

Set `Inputs!B4` to `Base`, `Bull` or `Bear`; everything downstream re-solves.
Blue cells are editable inputs, black are formulas, green are cross-sheet links, yellow fill
marks the assumptions the answer is most sensitive to. Column J of the `Inputs` tab carries a
source note for every driver, tagged **D** (disclosed by Oracle) or **E** (analyst estimate).

Tabs: `README` · `Inputs` · `Historicals` · `RPO_Schedule` · `Capex_Depreciation` ·
`Income_Statement` · `NonGAAP_Recon` · `Cash_Flow` · `Debt_Shares` · `Valuation_RPO_NPV` ·
`Valuation_DCF` · `Sensitivity` · `ROIC_Breakeven` · `Comps_Software` · `Comps_AI` ·
`Formula_Audit`

The workbook contains **no circular references** and needs no iterative calculation, so it
imports cleanly into Google Sheets. The two circularity breaks and their measured cost are
documented on `Formula_Audit`.

### Verification

LibreOffice is non-functional in the build environment (it cannot load any `.xlsx`, including a
two-cell test file), so the usual recalculate-and-check step could not run. Instead every
formula was parsed and evaluated with the Python `formulas` library: **3,566 cells evaluated,
zero formula errors**, and the outputs tied line by line to the independent Python engine in
`model/`. Revenue, gross margin, operating income, capex, depreciation and share count tie
exactly; EPS and the DCF differ by 2–4% because of the documented interest-expense
simplification, in the conservative direction. Two real defects were caught this way and fixed:
an invalid double-sheet-prefixed range, and a base-year reference that had the SaaS line
starting from R&D expense.

## Reproducing

```
model/model.py       # 3-statement forecast engine, FY2027–FY2031, three scenarios
model/valuation.py   # RPO contract NPV (primary), DCF and FCFE cross-checks, sensitivities, ROIC breakeven
model/comps.py       # comp-set assembly and calendarisation
model/pull_comps.py  # fetches the comp source pages
model/rp.py          # parses EDGAR XBRL "Financial Report" R-files
model/build_xlsx_*.py # constructs the workbook
data/                # cached source data and workbook row maps
```

`model.py` is the authority on the forecast; the workbook reproduces it within the tolerances
recorded on `Formula_Audit`.
