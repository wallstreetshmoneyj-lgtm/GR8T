# Oracle Corporation (ORCL) — Independent Forecast and Valuation

**Analyst:** independent build for Joshua Lacroix
**Model date:** 28 August 2026 · **Market data:** 27 August 2026 close, ORCL $151.94
**Primary source:** FY2026 Form 10-K, SEC EDGAR CIK 0001341439, accession `0001193125-26-277521`, filed 22 June 2026 (FYE 31 May 2026)
**Secondary primary source:** Q4/FY26 press release, Exhibit 99.1 to the Form 8-K filed 10 June 2026, accession `0001193125-26-265848`

---

## 0. Recommendation up front

| | |
|---|---|
| **Rating** | **HOLD**, with a negative skew. A source of funds, not a purchase. |
| **12-month target** | **$125** (−18% from $151.94) |
| **Confidence** | **Low.** The largest single driver of my answer is the discount rate, not anything about Oracle. |
| **Reasonable range** | $49 (contracted value only) to $210 (bull, on multiples) |

The reason this is a hold rather than a sell: my central estimate sits inside my own model's error bar, and Oracle's disclosed backlog puts a genuine floor under FY2027–28 revenue. The reason it is not a buy: at $151.94 roughly **68% of the share price is paying for business Oracle has not yet signed**, and I cannot underwrite that from public information.

**Deliverable 2.2 (the variance bridge against your model) is not in this memo** — the XLSX had not been supplied when this was built. Everything else in your brief is complete. The bridge will run as a standalone pass.

---

## 1. Your data pack — what I verified, and what is wrong

I pulled Oracle's XBRL company facts and the 10-K itself rather than trusting the transcription. **Your citation was exact** and almost everything ties to the dollar.

### Verified to the dollar (10-K R4 / R8 / R91)

Revenue $67,357m · GAAP operating income $20,606m · net income $17,087m (to common $16,984m) · GAAP EPS $5.83 · diluted WASO 2,914m · OCF $31,977m · capex $55,663m · FCF −$23,686m · RPO $638.0bn vs $137.8bn · price $151.94 · 52-week high $345.72 · headcount 141,000 (49,000 US / 92,000 international) · every segment line in your §3.2.

### The six corrections you accepted, restated with sources

**A. §3.4 mixes GAAP and non-GAAP inside one column.** FY27E operating income of $35.90bn on $89.34bn of revenue is a 40.2% operating margin, but the same column shows a 59.98% gross margin — implying opex of $17.7bn against FY26 actual GAAP opex of $23.7bn. Opex falling 25% while revenue grows 33% is not credible. I identified the source: it is stockanalysis.com's forecast tab, whose "Operating Income" for FY2026A reads **$22.39bn** — which is neither GAAP ($20,606m) nor Oracle non-GAAP ($28,926m). It appears to exclude restructuring. Three different definitions in one table. Rebuilt and labelled on the `NonGAAP_Recon` tab.

**B. The three PEGs were internally inconsistent.** All three divided an *NTM* P/E (a blend of FY27E and FY28E) by *FY26→FY27* growth, double-counting the FY28 acceleration. On a consistent FY27E P/E of $151.94 / $8.05 = **18.9x**:

| Growth basis | Growth | Yours | Consistent |
|---|---|---|---|
| off the $7.63 headline (contaminated) | 5.50% | 3.12 | **3.43** |
| off the $6.83 clean base (management's own) | 17.86% | 0.97 | **1.06** |
| FY27E→FY28E | 24.98% (my est.) | 0.49 | **0.76** |

Note the middle one crosses 1.0. **The one I would defend is 1.06**, because $6.83 is the base management itself uses for its "+18%" FY27 growth claim (press release footnote 1), and because the FY28 number is my estimate, not consensus — FY2028 consensus is paywalled at my source.

**C. The tax-rate wedge, which your brief omits entirely.** FY26 GAAP pretax was $19,554m against $2,467m of tax — a **12.6% GAAP effective rate**. Oracle re-taxes non-GAAP at **19.9%** (press release footnote 5). Confirmed against the disclosed bridge: $8,320m of pre-tax add-backs, $3,070m of incremental tax, $5,250m net. The implied 36.9% "rate on adjustments" is not a rate on adjustments at all — it is the whole base being re-taxed 730bp higher. **Two tax rates have to be modelled separately, and the GAAP one is fragile:** the 12.6% includes a **$2,062m stock-compensation windfall benefit** (10-K R80, −10.6pp of the rate). At $151.94 against a $345.72 52-week high, that benefit does not repeat. That alone is ~$0.70 of FY26 GAAP EPS that consensus may be carrying forward.

**D. Buybacks are a dead driver.** FY26 repurchases: **$95m** (0.4m shares), versus $600m in FY25 and $1,202m in FY24. $6.3bn of authorisation sits unused. Your §2.1 share-count driver collapses to stock-comp dilution plus two issuance events.

**E. Consensus FY27 FCF of −$47.73bn is not reconcilable to a cash flow statement.** The same source shows FY26 FCF as −$24.54bn on its forecast tab and −$23.69bn on its statistics tab; Oracle's own published figure is **−$23,686m**. So the consensus FCF series is an aggregation of analysts' own definitions, not a computed figure. **And the number is worth staring at:** −$47.73bn is numerically identical to Oracle's disclosed FY2026 *actual* "Net Cash Outlay for Capital Expenditures" of **$47,726m** (press release Ex-99.1: capex $55,663m less $3,345m short-term capex financing less $4,592m customer prepayments). I am not asserting causation — it may be coincidence — but treat it as a data-quality warning and do not build §4.1 on it.

**F. Minor.** 52-week low is $114.50 intraday, not $118.86 (you likely have the lowest close). Your −$23.69bn is the correct plain definition; the aggregator is the odd one out.

### Four further corrections I found

**G. Book equity is NOT negative. This one is load-bearing and it invalidates an instruction in your §2.3.**
At 31 May 2026 total Oracle stockholders' equity was **$42,508m** (10-K R2), up from $20,451m — paid-in capital $43,243m plus preferred $4,954m against an accumulated deficit of only $(4,309)m. **ROE is 53.4% and P/B is 11.7x, and both are meaningful.** Equity was restored by two years of retained earnings and the near-total halt in buybacks. Your brief tells me to flag ROE and P/B as broken; they were broken around FY2022, and they are not broken now. The metrics the capital structure genuinely does break are **EV/FCF and P/FCF**, which are n/m on negative free cash flow.

**H. The mandatory convertible is not the share-count story — the ATM is.**
The Series D converts on **15 January 2029** (10-K Note 10), at 499.8126–624.7657 shares per preferred share. At $151.94, below the $160.06 lower conversion price, the **maximum ratio applies: 31.2m shares** — about 1.1% of the count. Meanwhile Oracle entered a **$20bn at-the-market equity programme on 2 February 2026 and had drawn ZERO of it at 31 May 2026** (10-K R70). At $151.94 a full draw is ~132m shares, **four times** the convertible. And note what that does to your bear case: your §2.4 asks whether the debt load "forces equity issuance at depressed prices." Oracle has already built the plumbing to do exactly that.

**I. The $43.0bn of senior notes were issued 6 March 2026, not February.** The $5.0bn mandatory convertible priced 2 February 2026; the notes came a month later, in fourteen tranches from 4.45% (Sept 2030) to **6.85% (Feb 2066)**. That coupon stack is the real marginal cost of debt, and it is what I use.

**J. Oracle does not quantify RPO customer concentration, and I cannot either.**
The 10-K says only: "**No single customer accounted for 10% or more of our total revenues in fiscal 2026, 2025 or 2024**," followed by a new paragraph conceding that "the economic returns on these investments are dependent on customer demand and the ability of our key customers to meet their contractual obligations." Your §3.6 asks me to quantify concentration from the 10-K. **It is not there.** That is the single largest unquantifiable risk in this name and I treat it as a scenario lever rather than manufacture a number.

---

## 2. The four structural facts that decide this investment

Everything below flows from disclosure, not from my judgement.

### 2.1 Oracle has disclosed its own five-year revenue schedule

10-K Note 1, verbatim: of the $638bn of RPO at 31 May 2026, Oracle expects to recognise **~12% over the next twelve months, 34% over months 13–36, 34% over months 37–60, and the remainder thereafter.**

That is not a forecast. It is a schedule, and it covers exactly your FY2027–FY2031 window. Two things follow:

- **FY2027 revenue is comparatively low-risk.** 12% of $638bn is ~$76.6bn, roughly 85% of the $90bn guide. The FY27 debate is margin and cash, not the top line.
- **The schedule allocates the SAME 34% to months 13–36 and months 37–60.** Revenue from the current backlog *plateaus* after FY2028. Every dollar of growth beyond FY2028 has to come from contracts not yet signed. My FY2030 and FY2031 numbers are assumption; my FY2027 and FY2028 numbers are largely arithmetic on disclosure.

Two more facts worth knowing. Oracle **stopped XBRL-tagging the 12-month conversion percentage after FY2021**, when it was **60–62%**. Duration has gone from roughly two years to eight-plus. And the backlog step-change happened in **one quarter**: $137.8bn (May-25) → **$455.3bn (Aug-25)** → $523.3bn → $552.6bn → $638.0bn. Roughly two-thirds of the entire book was signed in Q1 FY26. That is what makes counterparty concentration the dominant risk rather than a footnote.

### 2.2 A third of Oracle's plant is not yet depreciating

Gross PP&E at 31 May 2026 was $122,651m, of which **$39,973m — 32.6% — was construction in progress** (10-K R49). Servers and networking equipment carry a **6-year life** (R50). Depreciation was $7,623m in FY26, already double FY25's $3,867m.

In my base case depreciation runs **$15.5bn → $23.1bn → $29.2bn → $32.7bn → $35.6bn** across FY27–31. That step-up, on its own, is most of the guided gross-margin compression. It is also why the buildout hits *non-GAAP* EPS: **Oracle does not exclude depreciation or interest from non-GAAP.** Your §4.2 is right about this and it is the most underappreciated mechanic in the story.

### 2.3 Customers are funding a large slice of the buildout

Press release, 10 June 2026: "*Most of the RPO increase in both Q3 and Q4 were large scale AI contracts where the customer prepaid Oracle for the purchase of the GPUs, or the customer bought and supplied the GPUs to Oracle. The prepaid and customer supplied hardware portions of our large AI contracts now total **$75 billion**.*"

This is visible in the FY26 cash flow statement as a brand-new line: **"Increase in deferred revenues from customer prepayments $4,592m"** (zero in FY25 and FY24). It materially reduces the capital Oracle itself must raise, and it is why my independently derived FY27 capex of **$80bn** lands below the gross number a naive capacity calculation would produce.

### 2.4 The cash gap is real, but smaller than §4.1 assumes

Base case FY2027: OCF $46.1bn, capex $80.0bn, **FCF −$33.9bn** — against consensus of −$47.7bn (a figure I have argued you should not lean on). Net income $19.5bn. The gap is ~$53bn, not $67bn, and it closes in FY2028.

Three capex definitions must be kept apart, and the `Cash_Flow` tab prints all three:

| Definition | FY2026A |
|---|---|
| (1) Capital expenditures, as reported (10-K R8) | $(55,663)m |
| (2) Net cash outlay for capex — **Oracle's own non-GAAP** | $(47,726)m |
| (3) Economic, including the change in unpaid capex ($5,279m / $2,970m) | $(57,972)m |

---

## 3. The forecast

Built from filings, without reference to your model. All figures $ millions except per-share.

### Base case

| | FY2027E | FY2028E | FY2029E | FY2030E | FY2031E |
|---|---:|---:|---:|---:|---:|
| Total revenue | 88,287 | 126,011 | 140,169 | 155,647 | 158,358 |
| growth | +31.1% | +42.7% | +11.2% | +11.0% | +1.7% |
| — from the 5/31/26 backlog | 75,532 | 103,793 | 105,081 | 107,480 | 99,504 |
| — from new bookings *(my estimate)* | 4,000 | 13,200 | 25,800 | 38,600 | 49,000 |
| Cloud infrastructure (IaaS) | 36,894 | 72,430 | 84,428 | 97,791 | 98,410 |
| Gross margin | 57.7% | 54.5% | 52.2% | 52.2% | 51.3% |
| IaaS gross margin | 29.0% | 37.2% | 35.5% | 37.2% | 35.5% |
| Capex | 80,000 | 30,573 | 36,814 | 15,882 | 29,187 |
| Depreciation | 15,456 | 23,079 | 29,151 | 32,698 | 35,561 |
| GAAP operating income | 28,563 | 43,367 | 46,790 | 53,395 | 52,973 |
| **GAAP EPS** | **$6.27** | $10.01 | $11.03 | $12.85 | $13.18 |
| **Non-GAAP EPS** | **$7.75** | $11.48 | $12.53 | $14.44 | $14.77 |
| Operating cash flow | 46,060 | 63,187 | 71,349 | 80,178 | 84,818 |
| **Free cash flow** | **(33,940)** | 32,613 | 34,535 | 64,296 | 55,630 |
| Total debt | 148,715 | 138,570 | 133,070 | 125,820 | 116,070 |
| Net debt / EBITDA | 2.54x | 1.26x | 0.71x | net cash | net cash |
| Incremental ROIC (gross basis) | 7.1% | 15.9% | 13.7% | 15.5% | 12.9% |

**Where I sit against the market on FY2027:** revenue $88.3bn vs **$90bn guidance** and $89.3bn consensus (−1.9%); non-GAAP EPS **$7.75 vs $8.05 guidance** (−3.7%). I am modestly below on both, independently derived.

**On the capex path:** it is lumpy — $80bn, then $31bn, then $37bn, then $16bn. That is not a modelling error, it is what happens when you link capex to the revenue it serves and the disclosed conversion schedule is itself lumpy. Smoothing it would hide the mechanism. The `Capex_Depreciation` tab prints a three-year rolling average alongside.

**A finding worth flagging:** management's own $90bn FY27 revenue guide implies OCI revenue of roughly $38.6bn — an acceleration from a 93% Q4 FY26 exit rate to about **+113% for the full year**. My base case gets +104%. That is a high bar and it is the first thing the 10 September print will test.

### Bull and bear

| | Bull | Base | Bear |
|---|---:|---:|---:|
| FY2031 revenue | 203,239 | 158,358 | 105,124 |
| FY2027 non-GAAP EPS | $8.62 | $7.75 | $6.37 |
| FY2031 non-GAAP EPS | $22.60 | $14.77 | $4.77 |
| FY2031 GAAP EPS | $21.36 | $13.18 | $3.14 |
| Peak net debt / EBITDA | 2.55x | 2.54x | **3.23x** |
| FY2029 incremental ROIC (gross) | +18.3% | +13.7% | **−8.3%** |
| Probability weight | **25%** | **45%** | **30%** |

**Bear case mechanics, since your §2.4 asked for it explicitly.** The bear is not primarily a liquidity event — it is a return-on-capital event, and it has a specific shape:

1. A 20% haircut to the AI backlog (counterparty default or renegotiation) — my proxy for the concentration the 10-K will not quantify.
2. **Capex does not fall with it.** GPU orders and data-centre leases are placed 12–18 months ahead; the model floors FY27 capex at $78bn. You spend the money and *then* discover the revenue is not coming. That asymmetry is the whole bear case, and it is why the RPO NPV sizes capacity off the *contracted* schedule rather than the haircut one — doing otherwise would make counterparty risk look value-*accretive*.
3. Utilisation falls to 60–66%, IaaS gross margin compresses to the teens, and $42bn of impairments run through FY28–30.
4. Equity issuance of $45bn at $95–120 — exactly the "equity at depressed prices" you posited. Share count reaches 3,443m.
5. Net debt/EBITDA peaks at 3.23x. The revolver covenant (consolidated EBITDA / consolidated net interest ≥ 3.0x, 10-K R58) is approached but not breached.

**The bear's most uncomfortable feature — and this is a direct extension of your §4.2:** non-GAAP EPS holds at **$4.77–6.37** while GAAP EPS goes to **−$0.93 in FY2029**. Why? Because the impairments land in *restructuring and other*, which is precisely the line Oracle excludes. **In the bear case the damage is invisible on the metric everyone quotes.** If you take one thing from this memo about non-GAAP, take that.

---

## 4. Valuation

### 4.1 Primary method — contract-level NPV of the backlog

Per your approval: a growth-perpetuity DCF on five years of deeply negative FCF is mostly terminal assumption, so the primary method values the **$638bn backlog as a self-liquidating contract portfolio with no renewal assumed**, plus the legacy software business, less net debt. The residual against the share price is then, by construction, what the market is paying for business Oracle has not yet signed.

| $m, base case | |
|---|---:|
| PV of backlog cash flows (FY27–36, WACC 10.30%) | 53,366 |
| PV of residual asset value | 1,838 |
| **Backlog enterprise value** | **55,203** |
| Legacy business (support, licence, SaaS, services, hardware) | 189,164 |
| **Contracted enterprise value** | **244,367** |
| Less net debt / preferred / NCI | (103,195) |
| **Contracted equity value** | **141,172** |
| **Per share** | **$48.45** |
| **Share of the $151.94 price NOT covered** | **68%** |

**Be careful with the legacy leg — it is the second-largest driver of the whole answer and it is a judgement, not a fact.** Discounting a flat software annuity at the group WACC values it at **8.4x EBITDA**, against SAP at 18.7x, MSFT at 16.3x and IBM at 14.3x on the same calendarised basis. Both readings are defensible and I show both:

| Legacy valued at | Contracted value per share |
|---|---:|
| DCF perpetuity (1.5% growth, 10.3% WACC) = 8.4x | $48.45 |
| 8x EBITDA | $45.14 |
| 10x EBITDA | $60.54 |
| 12x EBITDA | $75.94 |

So the honest statement is: **contracted value is $45–76 per share; the market is $151.94; between 50% and 70% of the price requires business not yet signed.** That is the single most useful sentence in this memo.

### 4.2 Cross-check — DCF

| | Bull | Base | Bear |
|---|---:|---:|---:|
| WACC | 9.50% | 10.30% | 11.09% |
| **Unlevered FCF DCF, per share** | **$239.57** | **$136.15** | **$23.60** |
| terminal value as % of EV | 86% | 82% | **118%** |
| **FCFE, per share** | $178.45 | $126.95 | $48.89 |

The bear's terminal value exceeding 100% of EV is not a bug to be smoothed away — it is the method telling you it has stopped being informative. That is the evidence for making the contract NPV primary.

**WACC build** (all inputs on `Valuation_DCF`): risk-free 4.672% (10-year UST, 27 Aug), ERP 5.0%, beta 1.50 (midpoint of the 5-year 1.72 and a normalised 1.28), cost of equity 12.17%; marginal pre-tax cost of debt 6.75% — anchored to Oracle's own February 2026 30-year at 6.70% and 40-year at 6.85%; E/(D+E) 72.3%. **The beta midpoint is a judgement call and it moves the answer more than anything Oracle does.**

### 4.3 Probability-weighted target

At 25% / 45% / 30%: UFCF DCF **$128.24**, FCFE **$116.41**. Multiples cross-check: base FY2028E non-GAAP EPS of $11.48 at a 15–18x multiple gives $172–207, but two-years-out EPS at a full multiple is exactly the kind of arithmetic that got 44 analysts to a $110–$400 target range.

**Target: $125.** Rounded from the $116–128 band, before the multiples cross-check, which I discount for the reason just given.

**Why 45% base rather than higher:** the FY27–28 revenue is close to arithmetic, but everything that determines value — margin at maturity, asset turn, utilisation — is undisclosed. **Why 30% bear rather than 20%:** the concentration that would trigger it is not quantified anywhere, so I cannot assign it a low probability on evidence. **Why 25% bull:** it needs OCI gross margin above 45%, which is 15 points above my derived FY26 level and unverifiable.

---

## 5. Sensitivity and driver ranking

Ranked by swing in base-case contracted value per share:

| Driver | Low | High | Swing | vs base | Range tested |
|---|---:|---:|---:|---:|---|
| **WACC** | $32.73 | $67.67 | $34.94 | 72% | 12.5% → 8.5% |
| **Legacy business terminal growth** | $34.08 | $61.78 | $27.70 | 57% | −1% → +3% |
| Backlog EBITDA margin | $38.32 | $58.51 | $20.19 | 42% | −8pp → +8pp |
| Legacy business EBITDA margin | $35.81 | $54.10 | $18.29 | 38% | 38% → 50% |
| Effective asset turn | $37.24 | $55.45 | $18.21 | 38% | 0.28 → 0.44 |
| RPO haircut / counterparty risk | $39.34 | $50.07 | $10.73 | 22% | 30% → 0% |

**Your §2.5 guessed the drivers would be RPO conversion × OCI gross margin and WACC × terminal growth. You were half right, and the half you got wrong is instructive.** WACC and terminal growth dominate, as you thought. But **RPO conversion is the *weakest* of the six drivers**, not the strongest — because the disclosed schedule already tells us the timing, and because a haircut that removes revenue also (partly) removes the capex needed to serve it. What actually matters is not *whether* the backlog converts but **at what margin and at what capital intensity** — and neither is disclosed.

Two-way tables (WACC × terminal growth, WACC × backlog margin) are live on the `Sensitivity` tab.

---

## 6. Does the buildout clear its cost of capital? (your §4.5)

**Per your instruction: the breakeven, not a point estimate.**

Oracle does not disclose OCI revenue per dollar of plant, OCI utilisation, or OCI cost of revenue. A point estimate of incremental ROIC is manufacturable but not defensible. The breakeven is.

**Required IaaS gross margin (depreciation inside cost of revenue, as Oracle reports it) to earn exactly a 10.30% WACC:**

| utilisation ↓ / asset turn → | 0.40 | 0.45 | 0.50 | 0.55 | 0.60 |
|---|---:|---:|---:|---:|---:|
| 65% | 39.2% | 36.2% | 33.8% | 31.8% | 30.2% |
| 75% | 35.6% | 33.0% | 30.9% | 29.2% | 27.7% |
| 85% | 32.8% | 30.5% | 28.7% | 27.1% | 25.9% |
| 95% | 30.6% | 28.6% | 26.9% | 25.6% | 24.4% |

*(7-year blended asset life, 12% opex allocation, 20% tax, invested capital 55% of gross PP&E.)*

**The derived FY2026 OCI gross margin is ~30%** — obtained by residual, assuming 93% software-support, 98% licence and 78% SaaS gross margins, since Oracle discloses cost of revenue only in three combined lines. Move any of those three assumptions and the 30% moves one-for-one.

**The answer: Oracle is earning approximately its cost of capital on the infrastructure business, and the sign depends on two variables it does not disclose.** At 85% utilisation and a 0.50 asset turn, required margin is 28.7% and Oracle clears it. At 65% and 0.40, required margin is 39.2% and Oracle destroys value badly. My base case sits at 72–88% utilisation and a 0.50 turn, giving incremental gross-basis ROIC of 13–16% against a 10.3% WACC — value-creating, but not by a margin that survives being wrong about utilisation.

**This is genuinely not knowable from public information at acceptable confidence.** What would settle it: OCI revenue per dollar of in-service plant; OCI utilisation; OCI cost of revenue; contracted price per GPU-hour in the large AI agreements. **None of the four is in the 10-K.** The Investor Day of 28 October 2026 is the first realistic opportunity to obtain any of them, and it is why that date matters more than the 10 September print.

---

## 7. Comparables — summary

Full tables, source and date stamped, in **`ORCL_comps.md`** and on the `Comps_Software` / `Comps_AI` tabs. Method and provenance are stated there in full; the short version:

- **Single source** (stockanalysis.com), single date (27–28 August 2026), all eleven names calendarised to a common NTM window of 28 Aug 2026 – 27 Aug 2027.
- **FY2028 consensus is paywalled at that source for every name.** The FY+2 leg of every calendarised metric is therefore **my own estimate**, produced by a disclosed mechanical rule, and every such cell is tagged `[E]`. Trailing metrics, FY+1 consensus, prices and EV are tagged `[C]`.

Leading with EV/EBITDA and EV/EBIT as instructed:

| | ORCL | Software peer median | AI-infra peer median |
|---|---:|---:|---:|
| NTM EV/EBITDA | **11.6x** | 15.3x | 13.5x |
| NTM EV/EBIT | **15.0x** | 19.1x | 22.4x |
| NTM P/E | 17.8x | 21.7x | 18.7x |
| NTM FCF margin | **−54%** | +28% | −4% |
| Net debt / EBITDA | **5.0x** | 2.4x | 1.4x |
| Capex / revenue | **83%** | 2% | 35% |

**Three facts, and they are the entire debate.** On the metric you asked me to lead with, Oracle at 11.6x is the second-cheapest name in the software set, behind only Salesforce at 11.0x, against a median of 15.3x. It also carries roughly twice the peer leverage (5.0x vs 2.4x) and spends more relative to its own revenue than any established hyperscaler. It is not obviously cheap and it is not obviously expensive; it is a different kind of company than either comp set, which is why your instinct to run two sets was right.

CoreWeave and Nebius screen at ~5x EV/EBITDA. That is not cheap, it is meaningless: EV/EBIT is 54.6x and n/m, NTM FCF margins are −217% and −542%, and capex is 401% and 2,103% of revenue.

---

## 8. Risks

1. **Counterparty concentration — undisclosed and unquantifiable.** Two-thirds of the backlog was signed in one quarter. The 10-K confirms no customer exceeds 10% of *revenue* but says nothing about RPO. This is the top risk and I cannot size it.
2. **The utilisation/asset-turn pair.** Section 6. Everything about whether this creates value hangs on two undisclosed numbers.
3. **Committed capex.** The floor under FY27 spending is what converts a demand miss into a balance-sheet problem.
4. **The tax rate.** FY26's 12.6% included a $2,062m stock-comp windfall that a 56%-off share price does not reproduce.
5. **Equity dilution.** $20bn of ATM capacity sits authorised and undrawn. Bear case: $45bn issued at $95–120.
6. **Credit.** BBB− is one notch above high yield *(unverified — see §9)*. The revolver's 3.0x EBITDA/net-interest covenant is approached in the bear case.
7. **The non-GAAP blind spot.** Impairments are excluded from the headline metric. In the bear case non-GAAP EPS stays near $5 while GAAP EPS goes negative.

---

## 9. What I could not verify at source

`investor.oracle.com` returned HTTP 403 throughout. The Q4 FY26 slide deck and the call transcript were unobtainable. **Everything below is your §3.3 transcription, treated as unverified secondary and used nowhere as a model input:**

- FY2027 net capex of ~$70bn, with reported capex $20–25bn higher
- The CFO's "no additional debt raise in calendar 2026" *(the press release does say "Oracle does not expect to issue additional debt in calendar year 2026" — this one is confirmed at source)*
- S&P's cut from BBB to BBB− on 9 July 2026
- The component cost pass-through characterisation
- FY2028 consensus of $130.64bn revenue and $10.91 EPS — paywalled at my source

What I *did* confirm at source from the press release: **$90bn FY2027 revenue guidance; $8.05 non-GAAP EPS guidance; Q1 FY27 revenue +27–29% and non-GAAP EPS $1.72–1.76; the $75bn of prepaid and customer-supplied hardware; the ~$40bn FY27 raise including the $20bn ATM; the $0.50 flat quarterly dividend; and that the $7.63 headline includes gains on the Ampere sale and Bloom Energy warrants, with $6.83 as the clean base.**

Full list in `ORCL_open_questions.md`.

---

## 10. The recommendation, and the case against it

### The call

**HOLD. Target $125. Low confidence.**

The disclosed backlog and the legacy annuity support $45–76 per share. The market is at $151.94. The difference is a bet on renewal and new bookings that no one — not me, not the 44 analysts spread across $110 to $400 — can underwrite from public filings. My probability-weighted DCF lands at $116–128. That is 15–23% below spot, which is a real gap but not a wide one relative to a model whose top driver is the discount rate.

If forced binary: **source of funds, not a purchase.**

### The strongest argument against my own conclusion

**My legacy-business valuation is probably too harsh, and if I am wrong there I am wrong on the whole call.**

I discount a flat, sticky, ~$19.8bn software-support annuity at a 10.3% WACC that exists because of the AI buildout's risk. That is arguably a category error: the maintenance stream's cash flows are not risky, they are just being *spent* on something risky. Value the legacy business at 12x EBITDA — still a discount to SAP at 18.7x and IBM at 14.3x — and contracted value alone is **$75.94**, half the share price rather than a third of it. Push the base-case DCF's WACC to 9.0% and the per-share number goes from $136 to roughly $170, above spot.

The second-strongest: **I am below management on FY2027 on both revenue and EPS, and management has the actual bookings data.** Being 3.7% below a guide the CFO reaffirmed in June, on a backlog whose conversion schedule the company itself disclosed, is a position that requires me to be right about margin — which is the thing I have just spent Section 6 arguing is not knowable. If OCI margins inflect two years earlier than I model, the bull case is the base case and $210+ is defensible.

### What would change my mind

**To a buy:**
- Investor Day (28 Oct) discloses OCI-level revenue per dollar of in-service plant, or utilisation, at levels implying an asset turn above 0.50 — this single disclosure resolves most of Section 6
- FY2028 gross margin guided above 55% (my base is 54.5%; consensus has no visibility)
- Named counterparties with disclosed credit standing covering the top decile of RPO
- FCF inflecting positive in FY2028 on *reported* capex, not on the net-outlay definition
- The ATM going undrawn through FY2027 — evidence the buildout self-funds

**To a sell:**
- Q1 FY27 (10 Sep) IaaS revenue below ~$8.5bn, implying the full-year $90bn guide needs an implausible back-half
- Any RPO *decline*, or a disclosed contract renegotiation
- ATM drawn below $130, or an equity raise beyond the $20bn authorised
- FY2027 gross margin guided below 57%
- Net debt/EBITDA above 3.0x with capex commitments intact
- The revolver covenant (3.0x EBITDA/net interest) being renegotiated

**The two dates that matter:** 10 September 2026 (Q1 FY27) tests whether the $90bn guide's implied OCI acceleration is real. **28 October 2026 (Investor Day) is the higher-value event** — it is the first realistic chance to obtain the OCI unit economics that Section 6 shows are decisive, and until then the central question in this name is genuinely unanswerable at acceptable confidence.
