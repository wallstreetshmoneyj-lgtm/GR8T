"""
INDEX WEIGHTING ANALYSIS
Rolling excess return, drawdown, and volatility comparison for two index total-return series.

Built for: cap-weighted vs equal-weighted vs modified-cap comparison.
Works with ANY two total-return series, so reuse it for SMH vs SOXX, VOO vs VTI, etc.

-------------------------------------------------------------------------------
HOW TO GET THE DATA
-------------------------------------------------------------------------------
Option A (easiest, ~2 min):
  1. Go to testfol.io
  2. Enter tickers RSP and SPY (or ?L=1 style backtest symbols for longer history)
  3. Export the monthly return series to CSV
  4. Save as data.csv with columns: date, series_a, series_b

Option B (longer history, free):
  1. stooq.com -> search ^SPX and ^SPXEW -> download monthly CSV
  2. Note: these are PRICE return, not total return. Dividends missing.
     Fine for relative comparison, wrong for absolute CAGR.

Option C (cleanest, if you can get it):
  S&P DJI index level files, or your school's Bloomberg / CapIQ terminal.
  GCU almost certainly has CapIQ access through the business school.
  Ask. It is the same data the pros use and it is free to you as a student.

-------------------------------------------------------------------------------
SETUP
-------------------------------------------------------------------------------
  pip install pandas numpy matplotlib
  python index_weighting_analysis.py
-------------------------------------------------------------------------------
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# =============================================================================
# CONFIG
# =============================================================================
CSV_PATH = "data.csv"        # columns: date, series_a, series_b
NAME_A = "Cap Weighted"      # label for series_a
NAME_B = "Equal Weighted"    # label for series_b
INPUT_TYPE = "level"         # "level" for index values/prices, "return" for periodic returns
PERIODS_PER_YEAR = 12        # 12 for monthly data, 252 for daily
ROLL_YEARS = 10              # rolling window length


# =============================================================================
# CORE METRICS
# =============================================================================

def to_returns(df, input_type):
    """Convert index levels to simple periodic returns."""
    if input_type == "level":
        return df.pct_change().dropna()
    return df.dropna()


def cagr(returns):
    """Compound annual growth rate from a return series."""
    n_periods = len(returns)
    total_growth = (1 + returns).prod()
    return total_growth ** (PERIODS_PER_YEAR / n_periods) - 1


def annualized_stdev(returns):
    """
    Annualized standard deviation of returns.

    Sample stdev:  s = sqrt( sum((r_i - r_bar)^2) / (n - 1) )
    Annualized:    s_ann = s * sqrt(periods_per_year)

    The sqrt(t) scaling assumes returns are independent across periods.
    That assumption is imperfect (returns cluster in volatility) but it is
    the market standard.
    """
    return returns.std(ddof=1) * np.sqrt(PERIODS_PER_YEAR)


def max_drawdown(returns):
    """
    Largest peak-to-trough decline.

    DD_t = (V_t / max(V_0..V_t)) - 1
    MaxDD = min(DD_t)

    Returns (max_drawdown, peak_date, trough_date, months_to_recover).
    """
    wealth = (1 + returns).cumprod()
    running_peak = wealth.cummax()
    drawdown = wealth / running_peak - 1

    trough = drawdown.idxmin()
    max_dd = drawdown.min()
    peak = wealth.loc[:trough].idxmax()

    # recovery: first date after trough where wealth regains the prior peak
    peak_value = wealth.loc[peak]
    after = wealth.loc[trough:]
    recovered = after[after >= peak_value]
    recovery_periods = len(after.loc[:recovered.index[0]]) if len(recovered) else None

    return max_dd, peak, trough, recovery_periods


def rolling_annualized(returns, years):
    """Rolling annualized return over a trailing window."""
    window = int(years * PERIODS_PER_YEAR)
    log_r = np.log1p(returns)
    rolled = log_r.rolling(window).sum()
    return np.expm1(rolled * (PERIODS_PER_YEAR / window)).dropna()


def sharpe(returns, rf_annual=0.0):
    """
    Sharpe ratio = (annualized return - risk free) / annualized stdev.

    NOTE: this is the metric you were reaching for with "standard deviation
    over returns." Sharpe is return-per-unit-risk, so higher is better.
    The inverse (stdev / return) is the coefficient of variation, where
    lower is better. Both say the same thing upside down.
    """
    return (cagr(returns) - rf_annual) / annualized_stdev(returns)


# =============================================================================
# RUN
# =============================================================================

def main():
    raw = pd.read_csv(CSV_PATH, parse_dates=["date"], index_col="date").sort_index()
    raw.columns = [NAME_A, NAME_B]

    rets = to_returns(raw, INPUT_TYPE)
    a, b = rets[NAME_A], rets[NAME_B]

    # ---- summary table ----
    rows = []
    for name, r in [(NAME_A, a), (NAME_B, b)]:
        dd, peak, trough, rec = max_drawdown(r)
        rows.append({
            "Index": name,
            "CAGR": f"{cagr(r):.2%}",
            "Ann. StDev": f"{annualized_stdev(r):.2%}",
            "Sharpe (rf=0)": f"{sharpe(r):.2f}",
            "Max Drawdown": f"{dd:.2%}",
            "Peak": peak.date(),
            "Trough": trough.date(),
            "Periods to Recover": rec if rec else "not recovered",
        })

    summary = pd.DataFrame(rows).set_index("Index")
    print("\n" + "=" * 78)
    print("SUMMARY STATISTICS")
    print("=" * 78)
    print(summary.to_string())

    # ---- rolling excess ----
    roll_a = rolling_annualized(a, ROLL_YEARS)
    roll_b = rolling_annualized(b, ROLL_YEARS)
    excess = (roll_b - roll_a).dropna()

    pct_positive = (excess > 0).mean()
    print("\n" + "=" * 78)
    print(f"ROLLING {ROLL_YEARS}-YEAR EXCESS RETURN: {NAME_B} minus {NAME_A}")
    print("=" * 78)
    print(f"Windows observed:        {len(excess)}")
    print(f"% of windows B wins:     {pct_positive:.1%}")
    print(f"Mean excess:             {excess.mean():.2%}")
    print(f"Median excess:           {excess.median():.2%}")
    print(f"Best window:             {excess.max():.2%}  ({excess.idxmax().date()})")
    print(f"Worst window:            {excess.min():.2%}  ({excess.idxmin().date()})")
    print(f"StDev of excess:         {excess.std():.2%}")
    print("\nINTERPRETATION KEY")
    print("  ~50% win rate + wide swings  -> regime bet, no structural edge")
    print("  >70% win rate + narrow band  -> possible structural edge, test net of costs")

    # ---- chart ----
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(2, 1, figsize=(12, 9), sharex=False)

    ax = axes[0]
    ax.plot(excess.index, excess * 100, color="#1f4e79", linewidth=1.6)
    ax.axhline(0, color="#c00000", linewidth=1.2, linestyle="--")
    ax.fill_between(excess.index, excess * 100, 0,
                    where=(excess > 0), color="#1f4e79", alpha=0.18)
    ax.fill_between(excess.index, excess * 100, 0,
                    where=(excess <= 0), color="#c00000", alpha=0.18)
    verdict = "oscillates around zero: regime bet" if 0.35 < pct_positive < 0.65 else "persistent: investigate"
    ax.set_title(f"Rolling {ROLL_YEARS}-Yr Excess Return, {NAME_B} minus {NAME_A} — {verdict}",
                 fontsize=13, fontweight="bold")
    ax.set_ylabel("Annualized excess (%)", fontsize=11)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    ax = axes[1]
    for name, r, color in [(NAME_A, a, "#1f4e79"), (NAME_B, b, "#c00000")]:
        wealth = (1 + r).cumprod()
        dd = (wealth / wealth.cummax() - 1) * 100
        ax.plot(dd.index, dd, label=name, color=color, linewidth=1.4)
    ax.set_title("Drawdown from prior peak", fontsize=13, fontweight="bold")
    ax.set_ylabel("Drawdown (%)", fontsize=11)
    ax.set_xlabel("Date", fontsize=11)
    ax.legend(frameon=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.tight_layout()
    plt.savefig("index_weighting_analysis.png", dpi=150, bbox_inches="tight")
    print("\nChart saved: index_weighting_analysis.png")


if __name__ == "__main__":
    main()
