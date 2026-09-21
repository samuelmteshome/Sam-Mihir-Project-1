"""EDA and figures from the reviewed processing outputs.

    python scripts/04_visualize.py

Reads data/processed/county_analysis.csv and trial_sites_clean.csv, writes
figures/ and reports/eda_findings.md.

Site definition used throughout: the BROADER ACTIVE cohort (site status
RECRUITING, ENROLLING_BY_INVITATION or ACTIVE_NOT_RECRUITING). The strict
recruiting cohort is reported alongside as a sensitivity comparison, because
site status is missing on a large share of location rows.

Burden measure: crude stroke prevalence among adults 18+ (PLACES primary),
with age-adjusted prevalence as the sensitivity measure.

Counties with no PLACES stroke estimate (all of KY and PA in the 2025 release)
are drawn in a distinct "no estimate" grey, never as low-burden areas.
"""
import json
from pathlib import Path

import geopandas as gpd
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
FIGURES = ROOT / "figures"
REPORTS = ROOT / "reports"

TERRITORY_FIPS = {"02", "15", "60", "66", "69", "72", "78"}
EQUAL_AREA_CRS = "EPSG:5070"

mpl.rcParams.update({
    "figure.dpi": 150, "font.size": 10,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25,
})
INK, ACCENT, NO_DATA = "#1b2a41", "#c1440e", "#d9d6d0"

SOURCE_NOTE = ("Sources: CDC PLACES County Data 2025 release (2023 estimates) \u00b7 "
               "ClinicalTrials.gov API v2 snapshot \u00b7 US Census 2023 boundaries")


def snapshot_date() -> str:
    try:
        manifest = json.loads((RAW / "manifest.json").read_text())
        stamps = [s.get("retrieved_at_utc", "") for s in manifest.get("sources", {}).values()]
        return max(s for s in stamps if s)[:10]
    except Exception:
        return "see data/raw/manifest.json"


def load():
    df = pd.read_csv(PROCESSED / "county_analysis.csv", dtype={"countyfips": str})
    df["countyfips"] = df["countyfips"].str.zfill(5)
    for col in ("potential_desert_active", "potential_desert_recruiting",
                "potential_desert_active_ageadj"):
        df[col] = df[col].astype("boolean")

    geo = gpd.read_file(RAW / "cb_2023_us_county_500k.zip")[["GEOID", "STATEFP", "geometry"]]
    geo = geo[~geo["STATEFP"].isin(TERRITORY_FIPS)].rename(columns={"GEOID": "countyfips"})
    geo = geo.to_crs(EQUAL_AREA_CRS).merge(df, on="countyfips", how="left")

    sites = pd.read_csv(PROCESSED / "trial_sites_clean.csv")
    sites = sites[sites["is_active_site"]].dropna(subset=["lat", "lon"])
    sites = gpd.GeoDataFrame(
        sites, geometry=gpd.points_from_xy(sites.lon, sites.lat),
        crs="EPSG:4326").to_crs(EQUAL_AREA_CRS)
    return df, geo, sites


def footer(fig, extra=""):
    """Source line under the whole figure, wrapped so it never stretches the axes."""
    text = f"{SOURCE_NOTE}. Snapshot {snapshot_date()}."
    if extra:
        text += f" {extra}"
    fig.subplots_adjust(bottom=0.24)
    fig.text(0.01, 0.015, text, fontsize=6.5, color="#6a7179", wrap=True, va="bottom")


# ---------------------------------------------------------------------------
def fig_burden_map(geo):
    fig, ax = plt.subplots(figsize=(10, 6.2))
    geo.plot(column="stroke_crudeprev", cmap="YlOrRd", linewidth=0, ax=ax, legend=True,
             missing_kwds={"color": NO_DATA, "label": "No PLACES estimate"},
             legend_kwds={"label": "Crude stroke prevalence, adults 18+ (%)",
                          "shrink": 0.55, "orientation": "horizontal", "pad": 0.01})
    geo.dissolve(by="STATEFP").boundary.plot(ax=ax, color="white", linewidth=0.4)
    ax.set_title("Where stroke burden is concentrated", loc="left",
                 fontsize=14, weight="bold", color=INK)
    ax.set_axis_off()
    footer(fig, "Grey = no PLACES estimate (all KY and PA counties), not low burden.")
    fig.tight_layout()
    fig.savefig(FIGURES / "01_stroke_burden_map.png", bbox_inches="tight")
    plt.close(fig)


def fig_overlay(geo, sites):
    fig, ax = plt.subplots(figsize=(10, 6.2))
    geo.plot(column="stroke_crudeprev", cmap="YlOrRd", linewidth=0, ax=ax, legend=True,
             missing_kwds={"color": NO_DATA},
             legend_kwds={"label": "Crude stroke prevalence, adults 18+ (%)",
                          "shrink": 0.55, "orientation": "horizontal", "pad": 0.01})
    geo.dissolve(by="STATEFP").boundary.plot(ax=ax, color="white", linewidth=0.4)
    sites.drop_duplicates(subset=["facility_key", "city_key", "state"]).plot(
        ax=ax, color=INK, markersize=7, alpha=0.75, marker="o",
        edgecolor="white", linewidth=0.3, label="Active stroke trial site")
    minx, miny, maxx, maxy = geo.total_bounds
    pad = (maxx - minx) * 0.02
    ax.set_xlim(minx - pad, maxx + pad)
    ax.set_ylim(miny - pad, maxy + pad)
    ax.legend(loc="lower left", frameon=False)
    ax.set_title("Stroke burden and active stroke trial sites",
                 loc="left", fontsize=14, weight="bold", color=INK)
    ax.set_axis_off()
    footer(fig, "Active cohort: recruiting, enrolling by invitation, or active/not recruiting.")
    fig.tight_layout()
    fig.savefig(FIGURES / "02_overlay_burden_vs_trials.png", bbox_inches="tight")
    plt.close(fig)


def fig_desert_counties(df):
    d = (df[df["potential_desert_active"].fillna(False)]
         .nlargest(15, "stroke_crudeprev")
         .assign(label=lambda x: x.countyname + ", " + x.stateabbr)
         .sort_values("stroke_crudeprev"))
    fig, ax = plt.subplots(figsize=(7, 5.2))
    bars = ax.barh(d.label, d.stroke_crudeprev, color=ACCENT, height=0.7)
    ax.bar_label(bars, fmt="%.1f%%", padding=3, fontsize=8)
    median = df["stroke_crudeprev"].median()
    ax.axvline(median, color=INK, linestyle="--", linewidth=1)
    ax.text(median, -1.1, " national median", fontsize=8, color=INK, va="top")
    ax.set_xlabel("Crude stroke prevalence, adults 18+ (%)")
    ax.set_xlim(0, d.stroke_crudeprev.max() * 1.18)
    ax.set_title("Highest stroke burden, no active trial site",
                 loc="left", fontsize=13, weight="bold", color=INK)
    ax.grid(axis="y", alpha=0)
    footer(fig)
    fig.savefig(FIGURES / "03_top_desert_counties.png", bbox_inches="tight")
    plt.close(fig)


def fig_stratified(strat):
    x = np.arange(len(strat))
    fig, ax = plt.subplots(figsize=(7, 4.4))
    ax.bar(x - 0.19, strat.pct_with_site_low_burden, 0.38, color=INK, label="Lower-burden half")
    ax.bar(x + 0.19, strat.pct_with_site_high_burden, 0.38, color=ACCENT, label="Higher-burden half")
    ax.set_xticks(x)
    ax.set_xticklabels([f"Q{q}\n~{p:,}" for q, p in
                        zip(strat.population_quintile, strat.median_population)], fontsize=8)
    ax.set_xlabel("County population quintile (median population below)")
    ax.set_ylabel("% of counties with an active site")
    ax.set_ylim(0, max(strat.pct_with_site_low_burden.max(),
                       strat.pct_with_site_high_burden.max()) * 1.35)
    ax.legend(frameon=False, fontsize=9, ncol=2, loc="upper left")
    ax.set_title("Compare counties of similar size, and the gap closes",
                 loc="left", fontsize=13, weight="bold", color=INK)
    footer(fig, "Each stratum split at its own median stroke prevalence.")
    fig.savefig(FIGURES / "04_population_stratified.png", bbox_inches="tight")
    plt.close(fig)


def fig_cohort_sensitivity(df):
    labels = ["Strict recruiting", "Broader active"]
    vals = [100 * df.has_site_recruiting.mean(), 100 * df.has_site_active.mean()]
    deserts = [int(df.potential_desert_recruiting.fillna(False).sum()),
               int(df.potential_desert_active.fillna(False).sum())]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.4, 4))
    for ax, data, title, fmt in (
            (a1, vals, "% of counties with a site", "%.1f%%"),
            (a2, deserts, "Potential desert counties", "%d")):
        bars = ax.bar(labels, data, color=[INK, ACCENT], width=0.55)
        ax.bar_label(bars, fmt=fmt, padding=3, fontsize=9)
        ax.set_title(title, loc="left", fontsize=11, weight="bold", color=INK)
        ax.set_ylim(0, max(data) * 1.28)
    footer(fig, "Site definition changes the headline; status is missing on many rows.")
    fig.savefig(FIGURES / "05_cohort_sensitivity.png", bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
def findings(df, strat) -> str:
    eligible = df[df.stroke_crudeprev.notna()]
    zero = ~eligible.has_site_active
    with_t = eligible.loc[eligible.has_site_active, "stroke_crudeprev"]
    without = eligible.loc[zero, "stroke_crudeprev"]
    t, p = stats.ttest_ind(with_t, without, equal_var=False)

    ranked = df.sort_values("trial_site_pairs_active", ascending=False)
    total = ranked.trial_site_pairs_active.sum()
    conc = {n: 100 * ranked.head(n).trial_site_pairs_active.sum() / total
            for n in (10, 25, 50, 100)}

    big = eligible[eligible.population_quintile == 5]
    adj_t, adj_p = stats.ttest_ind(
        big.loc[big.has_site_active, "stroke_crudeprev"],
        big.loc[~big.has_site_active, "stroke_crudeprev"], equal_var=False)

    top_states = (df[df.potential_desert_active.fillna(False)]
                  .groupby("stateabbr").size().sort_values(ascending=False).head(8))

    return "\n".join([
        "# EDA findings",
        "",
        f"Generated by `scripts/04_visualize.py`. Snapshot {snapshot_date()}.",
        "Site definition: broader active cohort. Burden: crude prevalence, adults 18+.",
        "Counties with no PLACES estimate (KY, PA) are excluded from every comparison.",
        "",
        "## Q1. How many counties have no active stroke trial site?",
        "",
        f"- **{int((~df.has_site_active).sum()):,}** of {len(df):,} counties "
        f"({100 * (~df.has_site_active).mean():.1f}%) have none.",
        f"- Those counties hold **{int(df.loc[~df.has_site_active, 'totalpop18plus'].sum()):,}** "
        f"adults, {100 * df.loc[~df.has_site_active, 'totalpop18plus'].sum() / df.totalpop18plus.sum():.1f}% "
        "of the adult population.",
        "",
        "## Q2. Are sites concentrated?",
        "",
        *[f"- Top {n} counties hold **{v:.1f}%** of all active trial/site pairs."
          for n, v in conc.items()],
        f"- Only **{int(df.has_site_active.sum()):,}** counties "
        f"({100 * df.has_site_active.mean():.1f}%) host any active site.",
        "",
        "## Q3. Unadjusted burden comparison",
        "",
        f"- Counties with a site: mean crude prevalence **{with_t.mean():.2f}%** (n = {len(with_t):,})",
        f"- Counties without a site: mean crude prevalence **{without.mean():.2f}%** (n = {len(without):,})",
        f"- Welch t = {t:.1f}, p = {p:.2e}",
        "",
        "## Q4. The same comparison, adjusted for county population size",
        "",
        "This is the check that decides how the result may be described.",
        "",
        strat.to_markdown(index=False),
        "",
        "Within the largest-population quintile alone, mean crude prevalence is "
        f"**{big.loc[big.has_site_active, 'stroke_crudeprev'].mean():.2f}%** for counties with "
        f"a site and **{big.loc[~big.has_site_active, 'stroke_crudeprev'].mean():.2f}%** for "
        f"counties without (Welch t = {adj_t:.1f}, p = {adj_p:.2g}).",
        "",
        "**Interpretation.** The unadjusted gap in Q3 largely reflects county population",
        "size rather than trial siting: populous counties host the academic medical",
        "centres that run trials, and populous counties have lower stroke prevalence.",
        "The defensible claim is that trial capacity tracks population and research",
        "infrastructure, and that stroke burden does not follow either. That is a",
        "statement about where capacity was built, not about sponsors avoiding sick",
        "places, and it should be worded that way in public materials.",
        "",
        "## Q5. Potential trial deserts",
        "",
        f"- **{int(df.potential_desert_active.fillna(False).sum()):,}** counties are above the "
        "median crude prevalence with zero active sites.",
        f"- Strict recruiting cohort instead: "
        f"**{int(df.potential_desert_recruiting.fillna(False).sum()):,}** counties.",
        f"- Age-adjusted burden instead: "
        f"**{int(df.potential_desert_active_ageadj.fillna(False).sum()):,}** counties.",
        "- The spread across these three definitions is the sensitivity range; quote it.",
        f"- States with the most desert counties: "
        + ", ".join(f"{s} ({n})" for s, n in top_states.items()),
        "",
    ])


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    df, geo, sites = load()
    strat = pd.read_csv(PROCESSED / "population_stratified_check.csv")

    fig_burden_map(geo)
    fig_overlay(geo, sites)
    fig_desert_counties(df)
    fig_stratified(strat)
    fig_cohort_sensitivity(df)

    text = findings(df, strat)
    (REPORTS / "eda_findings.md").write_text(text)
    print(text)
    print(f"\nwrote 5 figures to {FIGURES} and reports/eda_findings.md")


if __name__ == "__main__":
    main()
