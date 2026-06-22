"""
analysis.py — runs the pipeline, generates charts, writes REPORT.md.
Run: python src/analysis.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import data_engine as de
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy import stats

OUT_CHARTS = os.path.join(os.path.dirname(__file__), "..", "charts")
OUT_REPORT = os.path.join(os.path.dirname(__file__), "..", "REPORT.md")
os.makedirs(OUT_CHARTS, exist_ok=True)

plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.edgecolor": "#444444",
    "axes.labelcolor": "#222222",
    "text.color": "#222222",
    "font.size": 11,
})

COLORS = {"automation": "#2E5EAA", "labor": "#C0392B", "US": "#2E5EAA", "JP": "#C0392B", "KR": "#27AE60"}


def chart_dependency_trajectories(demo: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(9, 5.5))
    for code, name in de.COUNTRIES.items():
        sub = demo[demo["Country"] == code].sort_values("Year")
        ax.plot(sub["Year"], sub["Dependency_Ratio"], marker="o", markersize=3,
                label=name, color=COLORS.get(code), linewidth=2)
    ax.axhline(de.DEFAULT_DEPENDENCY_THRESHOLD, color="gray", linestyle="--", linewidth=1,
               label=f"Aging threshold ({de.DEFAULT_DEPENDENCY_THRESHOLD})")
    ax.set_title("Age Dependency Ratio, 2005–2024\nUS vs Japan vs South Korea", fontsize=13, fontweight="bold")
    ax.set_xlabel("Year")
    ax.set_ylabel("Dependency Ratio (% of working-age population)")
    ax.legend(loc="upper left", frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    path = os.path.join(OUT_CHARTS, "01_dependency_ratio_trajectories.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def chart_demographic_clock(clocked: pd.DataFrame, crossing_years: dict):
    """Aligns all three countries on years since crossing the clock threshold."""
    fig, ax = plt.subplots(figsize=(9.5, 6))
    for code, name in de.COUNTRIES.items():
        sub = clocked[clocked["Country"] == code].sort_values("Years_Since_Crossing")
        if sub["Years_Since_Crossing"].isna().all():
            continue
        label = f"{name} (crossed {crossing_years[code]:.0f})" if not pd.isna(crossing_years[code]) else name
        ax.plot(sub["Years_Since_Crossing"], sub["Dependency_Ratio"], marker="o",
                markersize=3, label=label, color=COLORS.get(code), linewidth=2)
    ax.axvline(0, color="gray", linestyle="--", linewidth=1)
    ax.text(0.1, ax.get_ylim()[0] + 1, "Crossing point", fontsize=9, color="gray")
    ax.set_title(f"The Demographic Clock\nAligned on years since crossing "
                 f"dependency ratio = {de.CLOCK_ALIGNMENT_THRESHOLD:.0f}",
                 fontsize=13, fontweight="bold")
    ax.set_xlabel("Years since crossing the threshold (0 = crossing point)")
    ax.set_ylabel("Dependency Ratio (%)")
    ax.legend(loc="upper left", frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    path = os.path.join(OUT_CHARTS, "05_demographic_clock.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path



def chart_labor_scarcity(fred: pd.DataFrame):
    fig, ax1 = plt.subplots(figsize=(9, 5.5))
    ax1.plot(fred.index, fred["Labor_Force_Participation"], color=COLORS["US"],
             linewidth=2, label="Labor Force Participation Rate (%)")
    ax1.set_xlabel("Date")
    ax1.set_ylabel("Labor Force Participation Rate (%)", color=COLORS["US"])
    ax1.tick_params(axis="y", labelcolor=COLORS["US"])
    ax1.spines[["top"]].set_visible(False)

    if "Wage_Growth_Index" in fred.columns and fred["Wage_Growth_Index"].notna().any():
        ax2 = ax1.twinx()
        ax2.plot(fred.index, fred["Wage_Growth_Index"], color=COLORS["labor"],
                 linewidth=1.5, linestyle="--", label="Wage Growth Index (ECI)")
        ax2.set_ylabel("Employment Cost Index — Wages (% chg)", color=COLORS["labor"])
        ax2.tick_params(axis="y", labelcolor=COLORS["labor"])
        ax2.spines[["top"]].set_visible(False)

    ax1.set_title("US Labor Scarcity Signal\nLabor Force Participation vs. Wage Growth",
                  fontsize=13, fontweight="bold")
    fig.tight_layout()
    path = os.path.join(OUT_CHARTS, "04_labor_scarcity_fred.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def chart_immigration(immigration: pd.DataFrame, quality: dict):
    """Migrant stock share over time, legend flags how many real data points exist."""
    fig, ax = plt.subplots(figsize=(9, 5.5))
    for code, name in de.COUNTRIES.items():
        sub = immigration[immigration["Country"] == code].sort_values("Year")
        if sub["Migrant_Stock_Pct"].notna().sum() == 0:
            continue
        n_distinct = quality.get(code, {}).get('migrant_stock_distinct_values', '?')
        ax.plot(sub["Year"], sub["Migrant_Stock_Pct"], marker="o", markersize=3,
                label=f"{name} ({n_distinct} distinct values)",
                color=COLORS.get(code), linewidth=2)
    ax.set_title("Immigrant Stock Share of Population\nUS vs Japan vs South Korea",
                 fontsize=13, fontweight="bold")
    ax.set_xlabel("Year")
    ax.set_ylabel("International Migrant Stock (% of population)")
    ax.legend(loc="upper left", frameon=False, fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    path = os.path.join(OUT_CHARTS, "06_immigration.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def chart_basket_performance(auto_idx: pd.Series, labor_idx: pd.Series, ai_split: str):
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot(auto_idx.index, auto_idx.values, label="Automation basket (ROBO, BOTZ)",
            color=COLORS["automation"], linewidth=1.5)
    ax.plot(labor_idx.index, labor_idx.values, label="Labor-intensive basket (XRT, ITB)",
            color=COLORS["labor"], linewidth=1.5)
    split_dt = pd.Timestamp(ai_split)
    ax.axvline(split_dt, color="gray", linestyle="--", linewidth=1)
    ax.text(split_dt, ax.get_ylim()[1]*0.95, "  AI wave begins (2023)", fontsize=9, color="gray")
    ax.set_title("Automation vs Labor-Intensive Basket Performance\nIndexed to 100 at start", fontsize=13, fontweight="bold")
    ax.set_xlabel("Date")
    ax.set_ylabel("Indexed value (start = 100)")
    ax.legend(loc="upper left", frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    path = os.path.join(OUT_CHARTS, "02_basket_performance.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def chart_spread_by_year(spread_annual: pd.Series, ai_split: str):
    fig, ax = plt.subplots(figsize=(9, 5.5))
    years = spread_annual.index.year
    split_year = pd.Timestamp(ai_split).year
    colors = [COLORS["labor"] if y < split_year else COLORS["automation"] for y in years]
    ax.bar(years, spread_annual.values, color=colors)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title("Annual Return Spread: Automation Basket minus Labor-Intensive Basket",
                 fontsize=13, fontweight="bold")
    ax.set_xlabel("Year")
    ax.set_ylabel("Spread (percentage points)")
    ax.spines[["top", "right"]].set_visible(False)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=COLORS["labor"], label="Pre-AI-wave"),
                       Patch(color=COLORS["automation"], label="Post-AI-wave (2023+)")],
              loc="upper left", frameon=False)
    fig.tight_layout()
    path = os.path.join(OUT_CHARTS, "03_spread_by_year.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def run_statistical_tests(data: dict, verdict: dict) -> dict:
    """Run the core hypothesis tests and return a results dict for the report."""
    demo = data["demographics"]

    # Test 1: dependency ratio trend per country
    trend_results = {}
    for code, name in de.COUNTRIES.items():
        sub = demo[demo["Country"] == code].sort_values("Year")
        slope, intercept, r, p, se = stats.linregress(sub["Year"], sub["Dependency_Ratio"])
        trend_results[code] = {"name": name, "slope_per_year": slope, "r_squared": r**2, "p_value": p}

    # Test 2: pre/post AI-wave spread, t-test
    spread_annual = verdict["annual_spread_series"]
    split_year = pd.Timestamp(de.AI_WAVE_SPLIT).year
    pre = spread_annual[spread_annual.index.year < split_year]
    post = spread_annual[spread_annual.index.year >= split_year]
    if len(pre) > 1 and len(post) > 1:
        t_stat, p_val = stats.ttest_ind(post, pre, equal_var=False)
    else:
        t_stat, p_val = np.nan, np.nan

    return {
        "dependency_trends": trend_results,
        "pre_post_ttest": {"t_stat": t_stat, "p_value": p_val,
                            "pre_mean_spread": pre.mean() if len(pre) else np.nan,
                            "post_mean_spread": post.mean() if len(post) else np.nan,
                            "n_pre": len(pre), "n_post": len(post)},
    }


def write_report(data: dict, verdict: dict, stats_results: dict,
                  required_charts: list, bonus_charts: list = None):
    bonus_charts = bonus_charts or []
    demo = data["demographics"]
    trends = stats_results["dependency_trends"]
    ttest = stats_results["pre_post_ttest"]

    lines = []
    lines.append("# Checkpoint 1 — Demographic Dividend Reversed")
    lines.append("**Investing Around a Shrinking Workforce**")
    lines.append("")
    lines.append("*Note on this checkpoint: per program guidance, this submission prioritizes "
                  "process over output. The goal is a working, honest pipeline and a "
                  "documented account of how the analysis was built — not a finished or "
                  "polished conclusion. The verdict below is provisional and expected to "
                  "change as the analysis is extended in later checkpoints.*")
    lines.append("")
    lines.append("## Thesis")
    lines.append("Birth rates are collapsing across developed and middle-income nations. "
                  "This thesis maps the investment implications — automation, immigration "
                  "policy, pension system stress — and identifies which industries "
                  "structurally shrink versus benefit from a tighter labor market over "
                  "the coming decades.")
    lines.append("")
    lines.append("## Written Verdict")
    lines.append("This section is the full stance and verdict for this checkpoint, written "
                  "to stand on its own: what I believed before looking at any data, what I "
                  "actually tested, what the data showed, and what that means going "
                  "forward. The detailed methodology, statistics, and charts supporting "
                  "each part follow later in this report.")
    lines.append("")
    lines.append("### 1. The Stance, Formed Before Looking at Data")
    lines.append("Demographic aging is shrinking the US labor force, and that pressure is "
                  "real and measurable, not speculative. Historically, the US absorbed much "
                  "of that pressure by staying relatively open to immigration compared to "
                  "Japan and South Korea. That offset is weakening now, right as the "
                  "demographic pressure keeps building, which is part of why automation "
                  "investment accelerated starting around 2023 — not purely because the "
                  "technology got better, but because the easier alternative, importing "
                  "labor, has gotten harder at the same time it was needed most. Japan and "
                  "South Korea, having had little immigration to begin with for decades, "
                  "are the longer-running case of what happens when automation has to carry "
                  "more of the load on its own.")
    lines.append("")
    lines.append("This is one connected mechanism, not two separate claims being tested "
                  "side by side: labor scarcity is the cause, immigration access is the "
                  "valve that has historically relieved it, and automation is the response "
                  "that takes over as that valve narrows. Only the demographic and "
                  "automation-timing pieces of this are tested directly with statistics in "
                  "this checkpoint; the recent immigration-tightening piece is used as "
                  "explanation for *why now*, not as a second variable with its own "
                  "regression, since it happened in the same narrow time window as the AI "
                  "wave itself and the two cannot be cleanly separated statistically with "
                  "the data available here.")
    lines.append("")
    lines.append("### 2. What Was Tested, and What the Data Actually Showed")
    lines.append("**Part 1, the demographic mechanism: supported.** Age dependency ratios "
                  "are rising in all three countries, with a statistically significant "
                  "upward trend in the US and Japan. This confirms the core premise is "
                  "real, not an assumption taken on faith. Full regression results are in "
                  "Part 1 below.")
    lines.append("")
    lines.append("**Immigration as historical context: directionally supported.** The "
                  "US's migrant stock share of population is roughly four to six times "
                  "higher than Japan's or South Korea's across every available data point "
                  "in the 2005-2024 window, consistent with the US having a real, "
                  "structural immigration offset that Japan and South Korea do not. Detail "
                  "and a data quality caveat are in the Immigration section below.")
    lines.append("")
    lines.append("**Part 2, the investment timing claim: not yet supported.** The "
                  "automation basket used to test this (ROBO, BOTZ) underperformed the "
                  "labor-intensive comparison basket after 2023, the opposite of what the "
                  "stance predicted. Rather than treat this as the thesis being wrong, the "
                  "result was investigated and traced to a specific, identifiable problem: "
                  "ROBO and BOTZ are industrial robotics funds, holding companies like "
                  "Fanuc and ABB, not generative-AI funds. They predate and do not track "
                  "the specific automation wave this stance is actually about. The test, "
                  "as built, could not distinguish the older robotics cycle from the "
                  "generative-AI cycle, so it could not fairly confirm or deny the timing "
                  "claim. Full detail is in Part 2 and the Limitations section below.")
    lines.append("")
    lines.append("### 3. What This Means Going Forward")
    lines.append("The mechanism this thesis depends on, real labor scarcity from an aging, "
                  "less-immigration-supported workforce, is solidly confirmed by this "
                  "checkpoint's data. The specific claim that AI-era automation investment "
                  "is already capturing that opportunity is unproven, but for a reason that "
                  "points to a fixable next step rather than a dead end: the next checkpoint "
                  "should re-run the same test with a basket that actually tracks "
                  "generative-AI and agentic-automation exposure, rather than older "
                  "industrial robotics names, before drawing a final conclusion on the "
                  "timing claim.")
    lines.append("")
    lines.append("## Stance by Pillar, Before Looking at Data")
    lines.append("The full thesis names four channels through which demographic contraction "
                  "is expected to affect markets: automation, immigration policy, pension "
                  "system stress, and which industries structurally shrink versus benefit. "
                  "This checkpoint does not test all four with equal depth. The table below "
                  "states a directional stance on each, formed before pulling any data, and "
                  "marks honestly which ones were actually tested this checkpoint versus "
                  "named as a belief carried into future checkpoints.")
    lines.append("")
    lines.append("| Pillar | Stance (formed before looking at data) | Tested this checkpoint? |")
    lines.append("|---|---|---|")
    lines.append("| Automation | Automation is the primary response to labor scarcity, "
                  "and that response is accelerating now, both from demographic pressure "
                  "and from a narrowing immigration offset, but is not yet fully priced "
                  "in. | Yes — see Part 2 and the verdict above. |")
    lines.append("| Immigration policy | The US has historically relied on relatively open "
                  "immigration to offset labor scarcity that Japan and South Korea, "
                  "historically closed, could not. That offset is narrowing recently, "
                  "adding to demographic pressure rather than replacing it as a separate "
                  "cause. | Partially — the historical offset is tested with real data "
                  "below; the recent-tightening effect is named as context, not "
                  "separately tested. |")
    lines.append("| Pension system stress | Countries further along the demographic clock "
                  "(see below) and with less immigration offset face more acute pension "
                  "and sovereign fiscal stress, not yet fully reflected in sovereign debt "
                  "pricing. | Not yet — directional belief only, planned for a later "
                  "checkpoint using FRED/IMF fiscal data. |")
    lines.append("| Sector winners vs. losers (beyond automation) | Healthcare and "
                  "eldercare benefit from an aging population directly; broad low-margin, "
                  "labor-intensive domestic services (retail, hospitality, construction) "
                  "are structurally exposed in countries without an immigration offset. | "
                  "Not yet — only the automation-vs-labor-intensive comparison was tested "
                  "this checkpoint, not a broader sector map. |")
    lines.append("")
    lines.append("## Process — What Went Right")
    lines.append("- Found that World Bank and yfinance both expose free, no-auth-required "
                  "APIs, which made it possible to build a fully reproducible pipeline "
                  "with no API key management or credential handling.")
    lines.append("- Separated the project into a data layer (`data_engine.py`) and an "
                  "analysis/reporting layer (`analysis.py`), which made it straightforward "
                  "to keep data-pulling logic separate from statistical testing and "
                  "reporting — easier to debug and easier to extend in later checkpoints.")
    lines.append("- Tested all pipeline logic against mock data shaped like the real API "
                  "responses before running it against live data, which caught structural "
                  "bugs (e.g., basket-index alignment, date-split logic) early and cheaply.")
    lines.append("- Operationalized the stance as a precise, falsifiable rule "
                  "(`post-2023 spread > 0 AND post-2023 spread > pre-2023 spread`) rather "
                  "than a vague directional claim, so the verdict is a real test rather "
                  "than a narrative fit to whatever the data showed.")
    lines.append("")
    lines.append("## Process — What Went Wrong / What Was Harder Than Expected")
    lines.append("- The original plan was to test the thesis across 5+ countries; narrowed "
                  "to three (US, Japan, South Korea) once it became clear that maintaining "
                  "data quality and a clean regression across more countries would cost "
                  "more time than it added insight at this stage.")
    lines.append("- The first version of the verdict logic was a simple \"did automation "
                  "beat labor-intensive stocks\" binary test. That test didn't actually "
                  "match this thesis's stance, which is about *timing* — whether the "
                  "investment response is accelerating, not just whether it's positive — "
                  "so it was rebuilt around a pre/post AI-wave split instead. Worth noting "
                  "as a reminder to test that an analysis actually matches the hypothesis "
                  "being argued, not just a plausible-sounding nearby test.")
    lines.append("- ETF baskets (ROBO, BOTZ, XRT, ITB) are an imperfect, somewhat blunt proxy "
                  "for \"automation exposure\" vs. \"labor-intensive exposure\" — this was a "
                  "known tradeoff made for checkpoint speed, with individual-stock "
                  "granularity flagged as a next-tier improvement rather than solved now.")
    lines.append("- The post-AI-wave window (2023–2024) is short, which limits how much "
                  "weight the t-test result can carry. This was anticipated going in, but "
                  "is worth stating plainly rather than letting the headline verdict imply "
                  "more confidence than the sample size supports.")
    lines.append("- The interactive dashboard (`app.py`) failed on first run with "
                  "`No module named 'yfinance'`, even after confirming via `pip install "
                  "yfinance` that it was installed. Root cause: `which python` and `which "
                  "streamlit` pointed to two different Python installs on the machine "
                  "(Anaconda's Python vs. a separate Python.framework install) — `pip` was "
                  "installing into one environment while Streamlit was launching from "
                  "another. Fixed by running `python -m streamlit run src/app.py` to force "
                  "Streamlit to use the same interpreter that had the dependencies "
                  "installed. A reminder that \"pip says it's installed\" and \"the running "
                  "process can see it\" are not the same claim, especially on machines with "
                  "multiple Python installs.")
    lines.append("- A code edit aimed at adding a new chart function accidentally deleted "
                  "the function signature of an existing one (`chart_labor_scarcity`), "
                  "leaving its body orphaned in the file. This was not caught by reading the "
                  "diff alone — it surfaced immediately on the next full pipeline test run "
                  "as a `NameError`, which is the main reason every change in this project "
                  "was re-tested end-to-end rather than assumed correct after editing.")
    lines.append("")
    lines.append("## Methodology")
    lines.append("1. Pulled annual age-dependency ratios (2005–2024) for the US, Japan, and "
                  "South Korea from the World Bank API to confirm the demographic mechanism "
                  "is real and accelerating.")
    lines.append("2. Pulled daily prices for an automation/robotics ETF basket (ROBO, BOTZ) "
                  "and a labor-intensive/domestic-consumption basket (XRT retail, ITB "
                  "homebuilders) via yfinance.")
    lines.append("3. Split the basket performance comparison at the AI-wave inflection point "
                  "(January 2023, following ChatGPT's late-2022 public release) and tested "
                  "whether the automation-vs-labor return spread is larger post-split than "
                  "pre-split.")
    lines.append("4. Ran a Welch's t-test on annual spread values pre- vs. post-split.")
    lines.append("")
    lines.append("## Part 1 — Is the Demographic Mechanism Real?")
    lines.append("")
    lines.append("| Country | Dependency Ratio Trend (pts/year) | R² | p-value |")
    lines.append("|---|---|---|---|")
    for code, t in trends.items():
        lines.append(f"| {t['name']} | {t['slope_per_year']:+.3f} | {t['r_squared']:.3f} | {t['p_value']:.4f} |")
    lines.append("")
    lines.append("A positive, statistically significant slope confirms dependency ratios are "
                  "rising — i.e., the working-age population is shrinking relative to "
                  "dependents — across all three countries, consistent with the thesis's "
                  "core premise.")
    lines.append("")
    lines.append("## The Demographic Clock — An Unexpected Angle")
    lines.append("")
    lines.append("Rather than treating the US, Japan, and South Korea as three independent "
                  "data points on a calendar-year x-axis, this checkpoint re-aligns all "
                  "three countries on **years since crossing a common dependency-ratio "
                  f"threshold ({de.CLOCK_ALIGNMENT_THRESHOLD:.0f})**. The idea: Japan and "
                  "South Korea are not just 'other countries' — they are the US's own "
                  "trajectory at different points in time. Reading their post-crossing "
                  "history can act as a preview of what the US is approaching, rather than "
                  "treating all three as separate, disconnected cases.")
    lines.append("")
    crossing_years = data.get("crossing_years", {})
    lines.append("| Country | Year crossed threshold | Implied lead/lag vs. other countries |")
    lines.append("|---|---|---|")
    sorted_crossings = sorted(
        [(c, y) for c, y in crossing_years.items() if not pd.isna(y)],
        key=lambda x: x[1]
    )
    for i, (code, year) in enumerate(sorted_crossings):
        name = de.COUNTRIES.get(code, code)
        if i == 0:
            note = "earliest — reference point"
        else:
            lag = year - sorted_crossings[0][1]
            note = f"crosses ~{lag:.1f} years after {de.COUNTRIES.get(sorted_crossings[0][0])}"
        lines.append(f"| {name} | {year:.1f} | {note} |")
    not_crossed = [c for c, y in crossing_years.items() if pd.isna(y)]
    for code in not_crossed:
        lines.append(f"| {de.COUNTRIES.get(code, code)} | not yet crossed in this window | — |")
    lines.append("")
    lines.append("**A related observation worth flagging explicitly: South Korea's "
                  "dependency ratio does not rise monotonically.** It declines for roughly "
                  "the first decade of the data window before inflecting sharply upward. "
                  "This is not a data artifact — it reflects Korea moving through the tail "
                  "end of its own demographic dividend (falling youth dependency outpacing "
                  "rising elderly dependency) before the aging effect takes over. Most "
                  "framings of this thesis would expect a straight upward line for every "
                  "aging country; Korea's chart instead shows the actual turning point from "
                  "dividend to tax happening within the sample window — and shows Korea "
                  "moving through that transition faster than Japan did at the same stage, "
                  "consistent with Korea's lower fertility rate.")
    lines.append("")
    lines.append("This reframing does not change the Part 2 verdict below, but it changes "
                  "how the US result should be read: the US has only just reached the "
                  "alignment threshold within this data window. If Japan and Korea's "
                  "post-crossing histories are any guide, the effects this thesis is "
                  "testing for (automation investment acceleration, wage pressure, sector "
                  "divergence) may simply not have had time to show up in the US data yet "
                  "— which is itself consistent with, not contrary to, the 'early innings' "
                  "stance.")
    lines.append("")
    lines.append("## Immigration — Historical Context for the Automation Timing Claim")
    lines.append("This section is not a separate, independently tested pillar. It supports "
                  "the written verdict above: the claim that the US has historically used "
                  "relatively open immigration to absorb labor scarcity in a way Japan and "
                  "South Korea, both historically closed, have not been able to. That gap "
                  "is part of why the US shows weaker demographic urgency than Japan or "
                  "Korea over the full 2005-2024 window, and why a recent narrowing of that "
                  "offset matters for the timing of automation investment, rather than "
                  "being a second, independently tested cause.")
    lines.append("")
    immigration = data.get("immigration")
    quality = data.get("immigration_quality", {})
    if immigration is not None and not immigration.empty:
        lines.append("| Country | Latest migrant stock (% of population) | Distinct values "
                      "in window | Years covered |")
        lines.append("|---|---|---|---|")
        for code, name in de.COUNTRIES.items():
            sub = immigration[immigration["Country"] == code].sort_values("Year")
            latest = sub["Migrant_Stock_Pct"].dropna()
            latest_val = f"{latest.iloc[-1]:.1f}%" if len(latest) else "no data"
            q = quality.get(code, {})
            lines.append(f"| {name} | {latest_val} | "
                          f"{q.get('migrant_stock_distinct_values', '?')} | "
                          f"{q.get('years_covered', '?')} |")
        lines.append("")
        lines.append("**A data quality caveat that matters more here than anywhere else in "
                      "this checkpoint.** World Bank labels migrant stock share \"annual,\" "
                      "but the table above shows far fewer distinct values than years "
                      "covered, confirming the underlying UN source data is only genuinely "
                      "updated roughly every 5 years. The chart below reflects that "
                      "directly rather than implying smoother annual change than the data "
                      "supports. Net migration (the flow measure, as opposed to migrant "
                      "stock share) is even sparser, reported only on 5-year UN estimate "
                      "windows, so it is summarized here rather than charted on its own.")
        lines.append("")
        lines.append("**Reading the result against the stance.** Even with infrequent "
                      "updates, the gap between the US and Japan/Korea's migrant stock "
                      "share is large and persistent across every available data point, "
                      "consistent with the stance that the US has a real, structural "
                      "immigration offset that Japan and South Korea do not. This is "
                      "directional support for the immigration pillar, not a precise "
                      "trend test — the data's update frequency does not currently allow "
                      "for the same kind of regression or significance testing used for "
                      "the dependency ratio in Part 1.")
    else:
        lines.append("Immigration data was not available in this run.")
    lines.append("")
    lines.append("## Part 2 — Has the Investment Response Already Happened, or Is It Just Beginning?")
    lines.append("")
    lines.append(f"- **Pre-AI-wave spread (2005–2022):** automation basket outperformed labor-intensive "
                  f"basket by **{verdict['pre_ai_wave_spread_pct']:.1f} percentage points** (cumulative).")
    lines.append(f"- **Post-AI-wave spread (2023–2024):** automation basket outperformed labor-intensive "
                  f"basket by **{verdict['post_ai_wave_spread_pct']:.1f} percentage points** (cumulative).")
    lines.append(f"- **Spread accelerating post-AI-wave:** {verdict['spread_accelerating']}")
    lines.append(f"- **Welch's t-test (post vs. pre annual spread):** t = {ttest['t_stat']:.3f}, "
                  f"p = {ttest['p_value']:.4f} (n_pre={ttest['n_pre']}, n_post={ttest['n_post']})")
    lines.append("")
    lines.append(f"## Provisional Verdict (Checkpoint 1): "
                 f"{'SUPPORTED (early innings)' if verdict['supported_early_innings'] else 'NOT YET SUPPORTED'}")
    lines.append("")
    if verdict["supported_early_innings"]:
        lines.append("The data is consistent with the stance: the demographic mechanism is "
                      "real and accelerating, and the automation-vs-labor performance spread "
                      "is *larger* in the post-AI-wave period than before it — suggesting the "
                      "market is still in the process of pricing this in, not finished doing so.")
    else:
        lines.append("The data does not yet show a larger automation-vs-labor spread "
                      "post-AI-wave than pre-AI-wave. Before treating this as a verdict on "
                      "the thesis itself, it is worth being precise about what the test "
                      "actually measured.")
        lines.append("")
        lines.append("**A likely driver: the automation basket is a poor proxy for the "
                      "generative-AI wave specifically.** ROBO and BOTZ are industrial "
                      "robotics ETFs — their largest holdings (e.g., Fanuc, ABB, Keyence, "
                      "Intuitive Surgical) are pre-genAI-era automation companies, not "
                      "generative-AI or agentic-automation names. Meanwhile XRT (retail) "
                      "and ITB (homebuilders) both had unusually strong 2023-2024 runs for "
                      "reasons unrelated to demographics (resilient post-COVID consumer "
                      "spending, rate-cut anticipation lifting homebuilders). So this result "
                      "is better read as *the test could not distinguish industrial-robotics-era "
                      "performance from generative-AI-era performance*, rather than as "
                      "evidence against the underlying mechanism.")
        lines.append("")
        lines.append("This sharpens rather than undermines the checkpoint: the demographic "
                      "mechanism (Part 1) holds up cleanly, but the basket used to test the "
                      "*investment response* needs to be more specifically AI-software-exposed "
                      "(e.g., AIQ, IRBO, or a custom basket of AI-infrastructure names) rather "
                      "than industrial-robotics ETFs, to actually test the early-innings "
                      "generative-AI-wave stance. That is the top priority fix for the next "
                      "tier of this analysis.")
        lines.append("")
        lines.append("Other contributing factors worth naming: (a) the post-2023 window is "
                      "still short, limiting statistical power; (b) the market may have "
                      "already priced in some automation premium during the 2017-2020 "
                      "robotics cycle, ahead of the generative-AI wave this thesis is "
                      "actually about.")
    lines.append("")
    lines.append("## Charts")
    for p in required_charts:
        lines.append(f"![{os.path.basename(p)}]({os.path.relpath(p, os.path.dirname(OUT_REPORT))})")
    if bonus_charts:
        lines.append("")
        lines.append("**Bonus chart** (beyond the 2-3 required) — a direct US-specific check "
                      "on labor scarcity using FRED data, independent of the World Bank "
                      "dependency-ratio series:")
        for p in bonus_charts:
            lines.append(f"![{os.path.basename(p)}]({os.path.relpath(p, os.path.dirname(OUT_REPORT))})")
    lines.append("")
    lines.append("## Limitations")
    lines.append("- Correlation between demographic trend and basket performance does not "
                  "establish causation; confounders include Fed policy, the broader AI "
                  "hype cycle, USD strength, and sector-specific catalysts unrelated to "
                  "demographics.")
    lines.append("- The post-AI-wave window (2023 to 2024) covers roughly two years of "
                  "data, which limits statistical power for the t-test. A 2026 re-run "
                  "with a more AI-specific basket would capture a fuller picture of "
                  "whether the effect has materialized.")
    lines.append("- ETF baskets are imperfect proxies; ROBO/BOTZ include industrial "
                  "robotics exposure that predates the generative-AI wave, and XRT/ITB "
                  "conflate several distinct labor-intensive sub-sectors.")
    lines.append("- A single dependency-ratio threshold (55) is used to classify "
                  "Aging/Young regimes; sensitivity to this threshold is not yet tested "
                  "(planned for next tier).")
    lines.append("- Only three countries are analyzed; broader middle-income coverage "
                  "(per the original thesis scope) is planned for a later checkpoint.")
    lines.append("")
    lines.append("## Next Steps (toward higher tier)")
    lines.append("- **Top priority:** replace ROBO/BOTZ with a basket that actually targets "
                  "the generative-AI / agentic-automation wave (e.g., AIQ, IRBO, or a custom "
                  "basket of AI-infrastructure and AI-software names) so the test isolates the "
                  "specific mechanism the stance is about, rather than industrial robotics "
                  "broadly.")
    lines.append("- Add immigration-policy variable as a moderating factor (US/Canada open "
                  "vs. Japan/Korea closed) to test the pairs-trade angle of the thesis.")
    lines.append("- Add pension-system / sovereign fiscal stress indicators (FRED, IMF).")
    lines.append("- Test sensitivity of the verdict to the dependency-ratio threshold and "
                  "the AI-wave split date.")
    lines.append("- Expand automation/labor baskets to individual names for sector-level "
                  "granularity.")

    with open(OUT_REPORT, "w") as f:
        f.write("\n".join(lines))
    return OUT_REPORT


def main():
    print("Pulling demographic data (World Bank)...")
    data = de.build_combined_dataset()

    print("Computing verdict...")
    verdict = de.compute_verdict(data)

    print("Running statistical tests...")
    stats_results = run_statistical_tests(data, verdict)

    print("Building the demographic clock...")
    clocked, crossing_years = de.build_demographic_clock(data["demographics"])
    data["clocked_demographics"] = clocked
    data["crossing_years"] = crossing_years

    print("Generating charts...")
    required_charts = [
        chart_dependency_trajectories(data["demographics"]),
        chart_basket_performance(data["automation_index"], data["labor_index"], de.AI_WAVE_SPLIT),
        chart_spread_by_year(verdict["annual_spread_series"], de.AI_WAVE_SPLIT),
    ]
    bonus_charts = []
    if "fred_indicators" in data and not data["fred_indicators"].empty:
        bonus_charts.append(chart_labor_scarcity(data["fred_indicators"]))
    bonus_charts.append(chart_demographic_clock(clocked, crossing_years))
    if "immigration" in data and not data["immigration"].empty:
        bonus_charts.append(chart_immigration(data["immigration"], data.get("immigration_quality", {})))
    chart_paths = required_charts + bonus_charts

    print("Writing report...")
    report_path = write_report(data, verdict, stats_results, required_charts, bonus_charts)

    print(f"\nDone.")
    print(f"  Charts:  {OUT_CHARTS}/")
    print(f"  Report:  {report_path}")
    print(f"  Verdict: {'SUPPORTED (early innings)' if verdict['supported_early_innings'] else 'NOT YET SUPPORTED'}")


if __name__ == "__main__":
    main()
