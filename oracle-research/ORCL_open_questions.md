# Open questions — what I could not resolve from public information

Ordered by how much the answer would move the valuation.

---

## Tier 1 — these determine whether the investment case works

### 1. What is OCI's revenue per dollar of in-service plant, and at what utilisation?
**Why it matters:** it is the top of the ROIC breakeven grid. At an 0.50 asset turn and 85% utilisation the buildout clears a 10.3% WACC comfortably; at 0.40 and 65% it destroys value badly. This one pair of numbers flips the sign of the entire investment case.
**Where I looked:** 10-K Items 1, 7 and 7A; the PP&E note (R49–R51); the segment note (R85–R87); the Q4 press release.
**Status:** not disclosed, and not derivable. Oracle reports three segments — Cloud & Software, Hardware, Services — so OCI is not even a reporting segment. Gross PP&E is disclosed by asset class but not by business.
**Best realistic source:** Investor Day, 28 October 2026.

### 2. What is OCI's cost of revenue?
**Why it matters:** Oracle discloses cost of revenue in exactly three lines — cloud and software combined, hardware, services. Cloud and software are fused, so OCI's gross margin cannot be read out of the filings. My ~30% figure for FY2026 is a residual built on assumed 93% software-support, 98% licence and 78% SaaS margins. **Move any of those three and the OCI margin moves one-for-one, and every conclusion about OCI profitability moves with it.**
**Status:** not disclosed. This is the largest single source of construct risk in the model.

### 3. How concentrated is the $638bn of RPO by counterparty?
**Why it matters:** roughly two-thirds of the backlog was signed in a single quarter (RPO went $137.8bn → $455.3bn between May and August 2025). If a meaningful share sits with one or two counterparties whose own funding is not secured, the bear case is not a tail.
**What the 10-K actually says:** "No single customer accounted for 10% or more of our total revenues in fiscal 2026, 2025 or 2024" — a *revenue* test, not an RPO test. Oracle then adds, in the same note, that "the economic returns on these investments are dependent on customer demand and the ability of our key customers to meet their contractual obligations."
**Status:** **not quantified anywhere.** Press reporting names OpenAI, Meta and NVIDIA; none of that is a filing and I have not used it. I model this as a scenario lever (0% / 5% / 20% of the AI backlog never recognised) rather than manufacture a number.

### 4. What is the contracted price per GPU-hour, and are the AI contracts fixed-price or cost-plus?
**Why it matters:** it determines whether component cost inflation lands on Oracle or the customer, and therefore whether the ~30% OCI margin is defensible through the ramp.
**Status:** not in any filing. The working brief attributes a "fixed-price where costs are known, pass-through where uncertain" characterisation to the Q4 call — **I could not verify it** (see Tier 3).

---

## Tier 2 — these would materially tighten the forecast

### 5. What is the split of the $638bn backlog between IaaS, SaaS and software support?
Oracle gives one aggregate RPO figure with one conversion schedule. My decomposition into a fast-converting "legacy" book (~$140bn) and a slow-converting "AI" book is an analyst construct calibrated so that the parts sum to the disclosed 12% / 34% / 34% / 20%. A disclosed split would replace a construct with data.

### 6. How much of the $75bn of prepaid and customer-supplied hardware is prepayment versus customer-supplied GPUs?
The distinction matters. Prepayments are Oracle's cash and Oracle's asset; customer-supplied GPUs are neither, and never touch Oracle's capex, depreciation or balance sheet. The press release gives one combined figure. The FY26 cash flow statement isolates $4,592m of prepayments with a significant financing component, which suggests the customer-supplied leg is much the larger of the two — but that is an inference.

### 7. Does Oracle capitalise interest on construction in progress, and how much?
With $39,973m of CIP, capitalised interest could be several hundred million dollars a year, and it flatters reported interest expense during exactly the years the model cares about. I found no disclosure in the debt note or the PP&E note. **My model assumes none, which is conservative.**

### 8. What is the FY2027 guided capex on a *reported* basis?
The brief cites ~$70bn net capex with reported capex $20–25bn higher, from the Q4 call. Oracle's own "net cash outlay for capital expenditures" definition (capex less short-term capex financing less customer prepayments) is disclosed in the press release, but no forward figure on either basis appears in any filing I could reach. My base case derives $80bn of reported capex independently.

### 9. What FY2027 tax rate is management assuming?
FY2026's 12.6% GAAP effective rate included a **$2,062m stock-compensation windfall benefit** (10-K R80, worth −10.6 percentage points). At $151.94 against a $345.72 52-week high, that benefit does not repeat, and consensus may be carrying it forward. Oracle guides EPS, not tax rate. **This alone could be $0.50–0.70 of GAAP EPS.**

### 10. What is the maturity and coupon profile of the *next* $40bn?
Management said ~$40bn of debt and equity in FY2027 including the $20bn ATM, and no additional debt in calendar 2026. The mix, timing and pricing are undisclosed. I model 6.75% pre-tax on new debt, anchored to Oracle's own February 2026 30-year at 6.70% and 40-year at 6.85% — pre-dating the S&P downgrade, so arguably too low.

---

## Tier 3 — could not be verified at source (access, not disclosure)

`investor.oracle.com` returned **HTTP 403** on every attempt, so the Q4 FY26 slide deck and the earnings call transcript were unobtainable. The following are from the working brief, treated as **unverified secondary** and used nowhere as model inputs:

| Item | Status |
|---|---|
| FY2027 net capex ~$70bn; reported $20–25bn higher | unverified |
| S&P downgrade BBB → BBB− on 9 July 2026 | unverified |
| Component cost pass-through characterisation | unverified |
| FY2027 gross margin guided down on ramp timing and mix | unverified |
| FY2028 consensus: $130.64bn revenue, $10.91 EPS | **paywalled at my source** — my FY2028 figures are my own estimates |
| Recent broker targets (Citi $330, DBS $310, JPM $200, RBC $190) | corroborated on the aggregator's ratings tab, not read at source |

**Confirmed at source from the press release (Ex-99.1 to the 8-K of 10 June 2026):** $90bn FY2027 revenue guidance · $8.05 FY2027 non-GAAP EPS guidance · Q1 FY27 revenue +27–29% and non-GAAP EPS $1.72–1.76 · $75bn of prepaid and customer-supplied hardware · ~$40bn FY2027 raise including the $20bn ATM · "Oracle does not expect to issue additional debt in calendar year 2026" · $0.50 quarterly dividend, flat · the $7.63 headline includes gains on the Ampere sale and Bloom Energy warrants, with **$6.83** as the clean base.

---

## Tier 4 — data-quality flags, not questions

**a. The −$47.73bn coincidence.** Consensus FY2027E free cash flow is quoted as −$47.73bn. Oracle's disclosed FY2026 **actual** "Net Cash Outlay for Capital Expenditures" is **$47,726m**. The same aggregator carries FY2026 FCF as −$24.54bn on its forecast tab and −$23.69bn on its statistics tab, while Oracle's own published figure is −$23,686m. I am not asserting a causal link, but the consensus FCF series is not reconcilable to any cash flow statement and should not carry a thesis.

**b. Three different "operating income" figures for FY2026 are in circulation:** GAAP $20,606m, Oracle non-GAAP $28,926m, and the aggregator's $22,394m (which appears to exclude restructuring). Any table mixing them is not comparable across rows.

**c. CRM is the least stable row in the comp set.** Salesforce moved +22.6% on 27 August 2026 on its Q2 print; its consensus estimates had not been revised as of this pull.

**d. Stale cached prices are common on free sources.** Every price used here was cross-checked against a live quote. ORCL's 52-week low is **$114.50 intraday**; a figure of $118.86 is the lowest *close*, a different basis.

---

## What I would ask Oracle IR

1. What is OCI revenue per dollar of in-service plant, and what utilisation does that reflect?
2. Will you disclose an OCI-level gross margin, or the RPO split between IaaS, SaaS and support?
3. What share of RPO sits with the top three counterparties, and what is their contracted payment profile?
4. Of the $75bn of prepaid and customer-supplied hardware, how much is cash prepayment and how much is customer-supplied equipment?
5. Do you capitalise interest on construction in progress, and how much in FY2026?
6. What GAAP tax rate should we assume for FY2027 absent the stock-compensation windfall?
7. At what point in the data-centre ramp does OCI gross margin inflect, and what utilisation does that assume?

Questions 1, 2 and 7 are the ones that would change the recommendation.
