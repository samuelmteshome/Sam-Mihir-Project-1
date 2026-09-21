"""Advanced visualizations: burden vs. access, mortality by metro status, and scatterplots.

Creates figures not in the initial EDA script:
- Scatterplot: stroke burden vs. sites per 100k (proposal requirement)
- Heatmap: mortality outcomes by metropolitan status and trial access
- Burden-distance relationship
- Metro/rural stratified mortality comparison

Run after 03_clean_merge.py and 06_analyze_access_outcomes.py:

    python scripts/07_advanced_visualizations.py

Outputs:
    figures/06_burden_vs_trial_access_scatter.png
    figures/07_mortality_by_metro_status.png
    figures/08_burden_distance_relationship.png
    figures/09_metro_rural_mortality_comparison.png
"""

import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
FIGURES = ROOT / "figures"
REPORTS = ROOT / "reports"

mpl.rcParams.update({
    "figure.dpi": 150, "font.size": 10,
    "axes.spines.top": False, "axes.spines.right": False,
})
INK, ACCENT, ACCENT2, NO_DATA = "#1b2a41", "#c1440e", "#176b70", "#d9d6d0"
SOURCE_NOTE = "Sources: CDC PLACES (2023) · ClinicalTrials.gov API v2 · HRSA AHRF (2021–2023)"


def load_data():
    """Load both prevalence and mortality datasets."""
    prevalence = pd.read_csv(PROCESSED / "county_analysis.csv", dtype={"countyfips": str})
    mortality_access = pd.read_csv(PROCESSED / "county_mortality_access.csv", dtype={"countyfips_2020": str})
    combined = pd.read_csv(PROCESSED / "county_analysis_with_mortality.csv", dtype={"countyfips": str})
    return prevalence, mortality_access, combined


def footer(fig, extra=""):
    """Source line under the whole figure."""
    text = f"{SOURCE_NOTE}. {extra}" if extra else SOURCE_NOTE
    fig.subplots_adjust(bottom=0.18)
    fig.text(0.01, 0.015, text, fontsize=6.5, color="#6a7179", wrap=True, va="bottom")


def fig_burden_vs_access_scatter(combined):
    """Scatter: crude prevalence vs. sites per 100k, colored by access gap."""
    fig, ax = plt.subplots(figsize=(9, 6))
    
    combined["is_desert"] = (
        combined["stroke_crudeprev"].notna() & 
        (combined["stroke_crudeprev"] > combined["stroke_crudeprev"].median()) &
        (combined["trial_site_pairs_active"] == 0)
    )
    
    has_sites = combined[combined["trial_site_pairs_active"] > 0]
    ax.scatter(has_sites["stroke_crudeprev"], has_sites["sites_per_100k_active"],
              s=60, alpha=0.6, color=ACCENT2, label="Has active trial site(s)", edgecolors="none")
    
    desert = combined[combined["is_desert"] == True]
    if len(desert) > 0:
        ax.scatter(desert["stroke_crudeprev"], desert["sites_per_100k_active"],
                  s=100, alpha=0.8, color=ACCENT, marker="X", label="High burden, no active site", edgecolors="none")
    
    median_burden = combined["stroke_crudeprev"].median()
    ax.axvline(median_burden, color=INK, linestyle="--", linewidth=1, alpha=0.5, label="Median burden")
    ax.axhline(0.5, color=INK, linestyle="--", linewidth=1, alpha=0.3)
    
    ax.set_xlabel("Crude stroke prevalence, adults 18+ (%)", fontsize=11, weight="bold")
    ax.set_ylabel("Active trial sites per 100,000 residents", fontsize=11, weight="bold")
    ax.set_title("Stroke Burden vs. Trial Site Availability: The Access Mismatch",
                loc="left", fontsize=13, weight="bold", color=INK, pad=15)
    ax.legend(loc="upper right", frameon=False, fontsize=9)
    ax.grid(alpha=0.25, axis="both")
    
    footer(fig, "Counties above median burden with zero active sites marked as high-burden/no-access.")
    fig.tight_layout()
    fig.savefig(FIGURES / "06_burden_vs_trial_access_scatter.png", bbox_inches="tight")
    plt.close(fig)


def fig_mortality_by_metro_heatmap(mortality_access):
    """Heatmap: metro/rural × trial access → mortality statistics."""
    data = mortality_access[
        mortality_access["mortality_published"] & 
        mortality_access["metro_status_2023"].notna()
    ].copy()
    
    data["access_category"] = pd.cut(
        data["trial_site_pairs_active"],
        bins=[-1, 0, 1, 5, 1000],
        labels=["No sites", "1 site", "2–5 sites", "6+ sites"]
    )
    
    heatmap_data = data.groupby(["metro_status_2023", "access_category"], observed=True).agg({
        "stroke_deaths_annual_avg_2021_2023": "mean",
        "population_mean_active_miles": "mean",
    }).unstack(fill_value=0)
    
    mortality_pivot = heatmap_data["stroke_deaths_annual_avg_2021_2023"]
    distance_pivot = heatmap_data["population_mean_active_miles"]
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))
    
    sns.heatmap(mortality_pivot, annot=True, fmt=".1f", cmap="YlOrRd", ax=ax1,
               cbar_kws={"label": "Mean annual deaths"}, linewidths=0.5, linecolor="white")
    ax1.set_title("Average Annual Stroke Deaths", fontsize=11, weight="bold", pad=10)
    ax1.set_xlabel("Trial Site Availability", fontsize=10)
    ax1.set_ylabel("County Classification", fontsize=10)
    
    sns.heatmap(distance_pivot, annot=True, fmt=".1f", cmap="RdYlGn_r", ax=ax2,
               cbar_kws={"label": "Mean distance (miles)"}, linewidths=0.5, linecolor="white")
    ax2.set_title("Mean Distance to Nearest Active Site", fontsize=11, weight="bold", pad=10)
    ax2.set_xlabel("Trial Site Availability", fontsize=10)
    ax2.set_ylabel("", fontsize=10)
    
    fig.suptitle("Stroke Deaths and Trial Distance: Metro vs. Rural Context",
                fontsize=13, weight="bold", y=0.98, color=INK)
    footer(fig, "Only counties with published mortality counts. Distance = population-weighted mean.")
    fig.tight_layout()
    fig.subplots_adjust(top=0.88, bottom=0.18)
    fig.savefig(FIGURES / "07_mortality_by_metro_status.png", bbox_inches="tight")
    plt.close(fig)


def fig_burden_distance_scatter(mortality_access):
    """Scatter: stroke burden vs. population-mean distance to trial site."""
    data = mortality_access[
        mortality_access["mortality_published"] &
        mortality_access["stroke_deaths_annual_avg_2021_2023"].notna()
    ].copy()
    
    prevalence = pd.read_csv(PROCESSED / "county_analysis.csv", dtype={"countyfips": str})
    data = data.merge(
        prevalence[["countyfips", "stroke_crudeprev", "stroke_adjprev"]],
        left_on="countyfips_2020", right_on="countyfips", how="left"
    )
    
    fig, ax = plt.subplots(figsize=(9, 6))
    
    colors = {"metro": ACCENT2, "nonmetro": ACCENT}
    for metro, color in colors.items():
        subset = data[data["metro_status_2023"] == metro]
        ax.scatter(subset["stroke_crudeprev"], subset["population_mean_active_miles"],
                  s=subset["stroke_deaths_annual_avg_2021_2023"] / 2 + 20,
                  alpha=0.6, color=color, label=metro.capitalize(), edgecolors="white", linewidth=0.5)
    
    valid = data[["stroke_crudeprev", "population_mean_active_miles"]].dropna()
    if len(valid) > 2:
        z = np.polyfit(valid["stroke_crudeprev"], valid["population_mean_active_miles"], 1)
        p = np.poly1d(z)
        x_trend = np.linspace(valid["stroke_crudeprev"].min(), valid["stroke_crudeprev"].max(), 100)
        ax.plot(x_trend, p(x_trend), "k--", alpha=0.3, linewidth=1.5, label="Trend")
        r, pval = stats.pearsonr(valid["stroke_crudeprev"], valid["population_mean_active_miles"])
        ax.text(0.05, 0.95, f"r = {r:.2f}, p = {pval:.3f}", transform=ax.transAxes,
               fontsize=9, verticalalignment="top", bbox=dict(boxstyle="round", facecolor="white", alpha=0.7))
    
    ax.set_xlabel("Crude stroke prevalence, adults 18+ (%)", fontsize=11, weight="bold")
    ax.set_ylabel("Mean distance to nearest active trial site (miles)", fontsize=11, weight="bold")
    ax.set_title("Stroke Burden vs. Geographic Distance to Trials",
                loc="left", fontsize=13, weight="bold", color=INK, pad=15)
    ax.legend(loc="upper right", frameon=False, fontsize=9, title="County type")
    ax.grid(alpha=0.25, axis="both")
    
    footer(fig, "Bubble size = average annual stroke deaths. Only counties with published mortality counts.")
    fig.tight_layout()
    fig.savefig(FIGURES / "08_burden_distance_relationship.png", bbox_inches="tight")
    plt.close(fig)


def fig_metro_rural_mortality_comparison(mortality_access):
    """Bar chart: share of deaths in no-site counties, by metro status."""
    data = mortality_access[
        mortality_access["mortality_published"] &
        mortality_access["metro_status_2023"].notna()
    ].copy()
    
    results = []
    for metro_type in ["metro", "nonmetro"]:
        subset = data[data["metro_status_2023"] == metro_type]
        no_site = subset[subset["trial_site_pairs_active"] == 0]
        
        total_deaths = subset["stroke_deaths_annual_avg_2021_2023"].sum()
        deaths_no_site = no_site["stroke_deaths_annual_avg_2021_2023"].sum()
        pct = 100 * deaths_no_site / total_deaths if total_deaths > 0 else 0
        
        results.append({
            "Type": metro_type.capitalize(),
            "No site": pct,
            "With site": 100 - pct,
            "Total deaths": int(total_deaths),
            "Deaths in no-site": int(deaths_no_site),
        })
    
    df_results = pd.DataFrame(results)
    
    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(df_results))
    width = 0.5
    
    bars1 = ax.bar(x - width/2, df_results["No site"], width, label="No site", color=ACCENT, alpha=0.85)
    bars2 = ax.bar(x + width/2, df_results["With site"], width, label="With site", color=ACCENT2, alpha=0.85)
    
    for bar in bars1:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height/2,
               f"{height:.1f}%", ha="center", va="center", color="white", fontweight="bold", fontsize=10)
    for bar in bars2:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height/2 + df_results["No site"].iloc[0],
               f"{height:.1f}%", ha="center", va="center", color="white", fontweight="bold", fontsize=10)
    
    ax.set_ylabel("Share of published annual average stroke deaths (%)", fontsize=11, weight="bold")
    ax.set_title("Stroke Deaths and Trial Presence: Metropolitan vs. Rural Counties",
                loc="left", fontsize=13, weight="bold", color=INK, pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(df_results["Type"])
    ax.set_ylim(0, 105)
    ax.legend(frameon=False, fontsize=10, loc="upper right")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    
    for i, row in df_results.iterrows():
        ax.text(i, -8, f"n = {row['Total deaths']:,} deaths", ha="center", fontsize=8, color="#666")
    
    footer(fig, "Only counties with published mortality counts. Metro = USDA codes 1–3; Rural = codes 4–9.")
    fig.tight_layout()
    fig.subplots_adjust(bottom=0.2)
    fig.savefig(FIGURES / "09_metro_rural_mortality_comparison.png", bbox_inches="tight")
    plt.close(fig)


def main():
    FIGURES.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    
    print("Loading data...")
    prevalence, mortality_access, combined = load_data()
    
    print("Creating Figure 6: Burden vs. Trial Access Scatter...")
    fig_burden_vs_access_scatter(combined)
    
    print("Creating Figure 7: Mortality by Metro Status Heatmap...")
    fig_mortality_by_metro_heatmap(mortality_access)
    
    print("Creating Figure 8: Burden vs. Distance Scatter...")
    fig_burden_distance_scatter(mortality_access)
    
    print("Creating Figure 9: Metro/Rural Mortality Comparison...")
    fig_metro_rural_mortality_comparison(mortality_access)
    
    print(f"\n✓ Wrote 4 new figures to {FIGURES}")
    print("  - 06_burden_vs_trial_access_scatter.png (proposal requirement)")
    print("  - 07_mortality_by_metro_status.png (heatmap)")
    print("  - 08_burden_distance_relationship.png (distance analysis)")
    print("  - 09_metro_rural_mortality_comparison.png (outcomes by region)")


if __name__ == "__main__":
    main()
