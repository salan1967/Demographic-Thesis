"""
data_engine.py — shared data layer for the demographic dividend thesis.

Stance: aging economies (US, Japan, South Korea) face real labor scarcity.
Automation is the investment response, but it's early innings and not yet
priced in, since the generative-AI wave (2023+) differs from the older
robotics-era automation cycle.

Data sources:
    World Bank API -> dependency ratio, working-age %, immigration
    FRED            -> US labor force participation, wage growth
    yfinance        -> automation vs labor-intensive ETF baskets

Install: pip install requests pandas numpy yfinance
"""

import pandas as pd
import numpy as np
import requests
from io import StringIO
import warnings
warnings.filterwarnings("ignore")


# ── CONFIGURATION ────────────────────────────────────────────────────────────
COUNTRIES = {
    "US": "United States",
    "JP": "Japan",
    "KR": "Korea, Rep.",
}

DEFAULT_START = "2005-01-01"
DEFAULT_END   = "2024-12-31"
AI_WAVE_SPLIT = "2023-01-01"   # ChatGPT release, Nov 2022 -> "AI wave" starts 2023

# Automation basket vs labor-intensive basket
AUTOMATION_TICKERS = ["ROBO", "BOTZ"]
LABOR_INTENSIVE_TICKERS = ["XRT", "ITB"]

# World Bank indicator codes
WB_DEPENDENCY_RATIO = "SP.POP.DPND"        # age dependency ratio (%)
WB_WORKING_AGE_PCT  = "SP.POP.1564.TO.ZS"  # population 15-64 (%)

# Immigration indicators. Net migration is 5-year UN estimates, not annual.
# Migrant stock is labeled annual but the UN source data is itself only
# revised every ~5 years, so values repeat between real updates.
WB_NET_MIGRATION = "SM.POP.NETM"
WB_MIGRANT_STOCK_PCT = "SM.POP.TOTL.ZS"

# Dependency ratio threshold for "aged" society classification
DEFAULT_DEPENDENCY_THRESHOLD = 55.0

# Lower threshold just for clock alignment, since the US and Korea don't
# clearly cross 55 in this data window but all three cross 50
CLOCK_ALIGNMENT_THRESHOLD = 50.0


# ── WORLD BANK: DEMOGRAPHIC DATA ─────────────────────────────────────────────
def load_demographics(countries: dict = COUNTRIES,
                       start_year: int = 2005, end_year: int = 2024) -> pd.DataFrame:
    """Pull annual dependency ratio + working-age % per country from World Bank."""
    records = []
    for code, name in countries.items():
        for indicator, col in [(WB_DEPENDENCY_RATIO, "Dependency_Ratio"),
                                (WB_WORKING_AGE_PCT, "Working_Age_Pct")]:
            url = (f"https://api.worldbank.org/v2/country/{code}/indicator/{indicator}"
                   f"?format=json&date={start_year}:{end_year}&per_page=100")
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if len(data) < 2 or data[1] is None:
                continue
            for row in data[1]:
                if row["value"] is not None:
                    records.append({
                        "Country": code,
                        "Country_Name": name,
                        "Year": int(row["date"]),
                        col: row["value"],
                    })

    df = pd.DataFrame(records)
    if df.empty:
        raise RuntimeError("World Bank API returned no data — check network access.")

    # pivot so each indicator is its own column
    df = df.groupby(["Country", "Country_Name", "Year"]).first().reset_index()
    df = df.sort_values(["Country", "Year"]).reset_index(drop=True)
    return df


def load_immigration(countries: dict = COUNTRIES,
                      start_year: int = 2005, end_year: int = 2024) -> pd.DataFrame:
    """
    Pull net migration and migrant stock share per country from World Bank.
    Both series are low-frequency (~5-year updates), checked explicitly in
    immigration_data_quality_summary() rather than assumed annual.
    """
    records = []
    for code, name in countries.items():
        for indicator, col in [(WB_NET_MIGRATION, "Net_Migration"),
                                (WB_MIGRANT_STOCK_PCT, "Migrant_Stock_Pct")]:
            url = (f"https://api.worldbank.org/v2/country/{code}/indicator/{indicator}"
                   f"?format=json&date={start_year}:{end_year}&per_page=100")
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if len(data) < 2 or data[1] is None:
                continue
            for row in data[1]:
                if row["value"] is not None:
                    records.append({
                        "Country": code,
                        "Country_Name": name,
                        "Year": int(row["date"]),
                        col: row["value"],
                    })

    df = pd.DataFrame(records)
    if df.empty:
        raise RuntimeError("World Bank API returned no immigration data — check network access.")

    df = df.groupby(["Country", "Country_Name", "Year"]).first().reset_index()
    df = df.sort_values(["Country", "Year"]).reset_index(drop=True)
    return df


def immigration_data_quality_summary(df: pd.DataFrame) -> dict:
    """Counts distinct values per series so low-frequency data isn't hidden."""
    summary = {}
    for code in df["Country"].unique():
        sub = df[df["Country"] == code]
        summary[code] = {
            "net_migration_distinct_values": sub["Net_Migration"].dropna().nunique() if "Net_Migration" in sub else 0,
            "migrant_stock_distinct_values": sub["Migrant_Stock_Pct"].dropna().nunique() if "Migrant_Stock_Pct" in sub else 0,
            "years_covered": sub["Year"].nunique(),
        }
    return summary


def classify_demographic_regime(df: pd.DataFrame,
                                 threshold: float = DEFAULT_DEPENDENCY_THRESHOLD) -> pd.DataFrame:
    """Classify each country-year as 'Aging' or 'Young' based on dependency ratio."""
    df = df.copy()
    df["Regime"] = np.where(df["Dependency_Ratio"] >= threshold, "Aging", "Young")
    return df


# ── THE DEMOGRAPHIC CLOCK ─────────────────────────────────────────────────────
def find_crossing_year(df: pd.DataFrame, country: str,
                        threshold: float = DEFAULT_DEPENDENCY_THRESHOLD) -> float:
    """Interpolated year a country's dependency ratio first crosses threshold."""
    sub = df[df["Country"] == country].sort_values("Year").reset_index(drop=True)
    above = sub[sub["Dependency_Ratio"] >= threshold]
    if above.empty:
        return np.nan
    first_idx = above.index[0]
    if first_idx == 0:
        return float(sub.loc[0, "Year"])  # already above threshold at start

    y0, r0 = sub.loc[first_idx - 1, ["Year", "Dependency_Ratio"]]
    y1, r1 = sub.loc[first_idx, ["Year", "Dependency_Ratio"]]
    if r1 == r0:
        return float(y1)
    frac = (threshold - r0) / (r1 - r0)
    return float(y0 + frac * (y1 - y0))


def build_demographic_clock(df: pd.DataFrame,
                             threshold: float = CLOCK_ALIGNMENT_THRESHOLD) -> pd.DataFrame:
    """
    Re-index each country by years since crossing CLOCK_ALIGNMENT_THRESHOLD
    instead of calendar year, so Japan/Korea's history previews where the
    US is headed. Uses 50, not the 55 aging threshold, since the US and
    Korea don't clearly cross 55 in this data window.
    """
    df = df.copy()
    crossing_years = {c: find_crossing_year(df, c, threshold) for c in df["Country"].unique()}
    df["Crossing_Year"] = df["Country"].map(crossing_years)
    df["Years_Since_Crossing"] = df["Year"] - df["Crossing_Year"]
    return df, crossing_years


# ── FRED: US LABOR MARKET DATA ───────────────────────────────────────────────
def load_fred_series(series_id: str, start: str = DEFAULT_START,
                      end: str = DEFAULT_END) -> pd.Series:
    """
    Pull a FRED series via the public, no-key CSV endpoint.
    Common series: CIVPART (labor force participation), ECIWAG (wage growth).
    """
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    df = pd.read_csv(StringIO(resp.text), parse_dates=["observation_date"])
    df = df.set_index("observation_date")[series_id]
    df = df.apply(pd.to_numeric, errors="coerce").dropna()
    df = df.loc[start:end]
    return df


def load_us_labor_scarcity_indicators(start: str = DEFAULT_START,
                                       end: str = DEFAULT_END) -> pd.DataFrame:
    """US labor force participation + wage growth, a direct check on labor scarcity."""
    lfpr = load_fred_series("CIVPART", start, end)
    wages = load_fred_series("ECIWAG", start, end)
    df = pd.DataFrame({"Labor_Force_Participation": lfpr}).join(
        pd.DataFrame({"Wage_Growth_Index": wages}), how="outer")
    return df.sort_index()



def load_sector_returns(tickers: list, start: str = DEFAULT_START,
                         end: str = DEFAULT_END) -> pd.DataFrame:
    """Pull daily adjusted close prices for a list of tickers via yfinance."""
    import yfinance as yf
    data = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)["Close"]
    if isinstance(data, pd.Series):
        data = data.to_frame(name=tickers[0])
    data = data.dropna(how="all")
    return data


def basket_index(prices: pd.DataFrame, tickers: list) -> pd.Series:
    """Equal-weighted basket index, rebased to 100 at the first valid date."""
    available = [t for t in tickers if t in prices.columns]
    if not available:
        raise ValueError(f"None of {tickers} found in price data columns: {list(prices.columns)}")
    normed = prices[available] / prices[available].iloc[0] * 100
    return normed.mean(axis=1)


def annual_returns(series: pd.Series) -> pd.Series:
    """Convert a daily indexed price series into annual % returns."""
    annual = series.resample("YE").last()
    return annual.pct_change().dropna() * 100


# ── COMBINED PIPELINE ─────────────────────────────────────────────────────────
def build_combined_dataset(start: str = DEFAULT_START, end: str = DEFAULT_END,
                            dependency_threshold: float = DEFAULT_DEPENDENCY_THRESHOLD) -> dict:
    """Run the full pipeline: pull all data sources, merge, classify."""
    demo = load_demographics(start_year=int(start[:4]), end_year=int(end[:4]))
    demo = classify_demographic_regime(demo, threshold=dependency_threshold)

    fred = load_us_labor_scarcity_indicators(start, end)

    immigration = load_immigration(start_year=int(start[:4]), end_year=int(end[:4]))
    immigration_quality = immigration_data_quality_summary(immigration)

    auto_prices  = load_sector_returns(AUTOMATION_TICKERS, start, end)
    labor_prices = load_sector_returns(LABOR_INTENSIVE_TICKERS, start, end)

    auto_index  = basket_index(auto_prices, AUTOMATION_TICKERS)
    labor_index = basket_index(labor_prices, LABOR_INTENSIVE_TICKERS)

    return {
        "demographics":      demo,
        "fred_indicators":   fred,
        "immigration":         immigration,
        "immigration_quality": immigration_quality,
        "automation_prices": auto_prices,
        "labor_prices":      labor_prices,
        "automation_index":  auto_index,
        "labor_index":       labor_index,
        "automation_annual": annual_returns(auto_index),
        "labor_annual":      annual_returns(labor_index),
    }


# ── VERDICT LOGIC ──────────────────────────────────────────────────────────────
def compute_verdict(data: dict, ai_wave_split: str = AI_WAVE_SPLIT) -> dict:
    """
    Tests the stance in two parts: is there a real spread between baskets,
    and is that spread bigger post-AI-wave (2023+) than before it. Supported
    only if both are true, since that's what "accelerating, not yet priced
    in" actually requires.
    """
    auto_idx  = data["automation_index"]
    labor_idx = data["labor_index"]

    split_date = pd.Timestamp(ai_wave_split)

    pre_auto   = auto_idx[auto_idx.index < split_date]
    post_auto  = auto_idx[auto_idx.index >= split_date]
    pre_labor  = labor_idx[labor_idx.index < split_date]
    post_labor = labor_idx[labor_idx.index >= split_date]

    def total_return(series):
        return (series.iloc[-1] / series.iloc[0] - 1) * 100 if len(series) > 1 else np.nan

    pre_spread  = total_return(pre_auto)  - total_return(pre_labor)
    post_spread = total_return(post_auto) - total_return(post_labor)

    # spread between baskets by year
    auto_annual  = data["automation_annual"]
    labor_annual = data["labor_annual"]
    spread_annual = (auto_annual - labor_annual).dropna()

    return {
        "pre_ai_wave_spread_pct":  pre_spread,
        "post_ai_wave_spread_pct": post_spread,
        "spread_accelerating":     bool(post_spread > pre_spread),
        "post_wave_positive":      bool(post_spread > 0),
        "supported_early_innings": bool(post_spread > 0 and post_spread > pre_spread),
        "annual_spread_series":    spread_annual,
    }


def sharpe_ratio(returns: pd.Series, risk_free: float = 0.04) -> float:
    """Annualized Sharpe ratio of daily returns."""
    excess = returns - risk_free / 252
    return (excess.mean() / excess.std()) * np.sqrt(252) if excess.std() > 0 else 0.0


def max_drawdown(prices: pd.Series) -> float:
    roll_max = prices.cummax()
    drawdown = (prices - roll_max) / roll_max
    return drawdown.min() * 100
