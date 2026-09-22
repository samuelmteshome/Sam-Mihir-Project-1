"""Advanced visualizations: burden vs. access, mortality by metro status, and scatterplots.

Creates figures not in the initial EDA script:
- Scatterplot: stroke burden vs. sites per 100k (proposal requirement)
- Heatmap: stroke death rate vs. distance to the nearest active trial site
- Burden-distance relationship
- Metro/rural stratified mortality comparison
- US map: stroke death-rate heat with trial sites and disparity areas outlined

Run after 03_clean_merge.py and 06_analyze_access_outcomes.py:

    python scripts/07_advanced_visualizations.py

Outputs:
    figures/06_burden_vs_trial_access_scatter.png
    figures/07_stroke_mortality_vs_trial_distance_heatmap.png
    figures/08_burden_distance_relationship.png
    figures/09_metro_rural_mortality_comparison.png
    figures/10_stroke_mortality_trial_disparity_map.png
"""

import json
from pathlib import Path

import geopandas as gpd
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
FIGURES = ROOT / "figures"
REPORTS = ROOT / "reports"

mpl.rcParams.update({
    "figure.dpi": 150, "font.size": 10,
    "axes.spines.top": False, "axes.spines.right": False,
})
INK, ACCENT, ACCENT2, NO_DATA = "#1b2a41", "#c1440e", "#176b70", "#d9d6d0"
NOT_MAPPED_FIPS = {"02", "15", "60", "66", "69", "72", "78"}
EQUAL_AREA_CRS = "EPSG:5070"
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


def fig_mortality_distance_heatmap(mortality_access):
    """Heatmap: stroke death-rate quintile x distance to nearest active trial site."""
    d = mortality_access.copy()
    d["death_rate"] = 100_000 * d["stroke_deaths_annual_avg_2021_2023"] / d["cens_popn_20"]
    bands = ["<10 mi", "10–25 mi", "25–50 mi", "50–100 mi", "100+ mi"]
    d["band"] = pd.cut(d["population_mean_active_miles"], [0, 10, 25, 50, 100, np.inf],
                       labels=bands, right=False)

    # Suppressed counts stay missing: excluded from the matrix, shown in their own strip.
    pub = d[d["mortality_published"]].copy()
    pub["quintile"], edges = pd.qcut(pub["death_rate"], 5, labels=False, retbins=True)
    counts = pd.crosstab(pub["quintile"], pub["band"]).reindex(columns=bands, fill_value=0)
    col_pct = 100 * counts / counts.sum()
    suppressed = d.loc[~d["mortality_published"], "band"].value_counts().reindex(bands, fill_value=0)
    band_total = d["band"].value_counts().reindex(bands)

    # Display highest death rate on top.
    counts, col_pct = counts.iloc[::-1], col_pct.iloc[::-1]
    row_names = ["Highest", "High", "Middle", "Low", "Lowest"]
    row_labels = [f"{name}\n{edges[4 - i]:.0f}–{edges[5 - i]:.0f}"
                  for i, name in enumerate(row_names)]

    zone_rows, zone_cols = [0, 1], [2, 3]
    zone = pub[pub["quintile"].isin([3, 4]) & pub["band"].isin([bands[c] for c in zone_cols])]
    top_two = pub[pub["quintile"].isin([3, 4])]
    near_top = top_two[top_two["band"] == bands[0]]

    fig = plt.figure(figsize=(12, 7.6))
    gs = fig.add_gridspec(2, 2, height_ratios=[5, 0.75], width_ratios=[3.1, 1],
                          hspace=0.08, wspace=0.04, left=0.14, right=0.98, top=0.83, bottom=0.2)
    ax = fig.add_subplot(gs[0, 0])
    strip = fig.add_subplot(gs[1, 0], sharex=ax)
    note = fig.add_subplot(gs[:, 1])
    note.set_axis_off()

    norm = mpl.colors.TwoSlopeNorm(vmin=0, vcenter=20, vmax=max(45, col_pct.values.max()))
    ax.imshow(col_pct.values, cmap="RdBu_r", norm=norm, aspect="auto")
    for r in range(5):
        for c in range(5):
            pct, n = col_pct.iat[r, c], counts.iat[r, c]
            color = "white" if abs(pct - 20) > 13 else INK
            ax.text(c, r - 0.1, f"{pct:.0f}%", ha="center", va="center",
                    fontsize=14, weight="bold", color=color)
            ax.text(c, r + 0.24, f"{n} counties", ha="center", va="center", fontsize=8, color=color)
    ax.set_xticks(range(5))
    ax.set_yticks(range(5))
    ax.set_yticklabels(row_labels, fontsize=9.5)
    ax.tick_params(axis="x", labelbottom=False, length=0)
    ax.tick_params(axis="y", length=0)
    ax.set_ylabel("Stroke death rate per 100,000 residents\n(county quintile)", fontsize=10.5)
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks(np.arange(-0.5, 5), minor=True)
    ax.set_yticks(np.arange(-0.5, 5), minor=True)
    ax.grid(which="minor", color="white", linewidth=2)
    ax.tick_params(which="minor", length=0)

    ax.add_patch(mpl.patches.Rectangle(
        (zone_cols[0] - 0.5, zone_rows[0] - 0.5), len(zone_cols), len(zone_rows),
        fill=False, edgecolor=ACCENT, linewidth=3.4, clip_on=False, zorder=5))
    ax.text(np.mean(zone_cols), zone_rows[0] - 0.62, "DISPARITY ZONE", ha="center", va="bottom",
            fontsize=10.5, weight="bold", color=ACCENT)

    strip.imshow(np.zeros((1, 5)), cmap="Greys", vmin=0, vmax=1, aspect="auto")
    for c, band in enumerate(bands):
        share = 100 * suppressed[band] / band_total[band]
        strip.text(c, 0, f"{suppressed[band]} ({share:.0f}%)", ha="center", va="center",
                   fontsize=9, color="#555")
    strip.set_yticks([0])
    strip.set_yticklabels(["Deaths suppressed\n(not shown above)"], fontsize=8.5, color="#555")
    strip.set_xticklabels([f"{b}\n{counts[b].sum()} counties" for b in bands], fontsize=9.5)
    strip.tick_params(length=0)
    strip.grid(False)
    for s in strip.spines.values():
        s.set_visible(False)
    strip.set_xlabel("Distance from county residents to the nearest active stroke trial site\n"
                     "(population-weighted average, straight-line miles)", fontsize=10.5, labelpad=8)

    zone_share = 100 * len(zone) / len(top_two)
    note.text(0.04, 0.83, "Where the gap is", fontsize=13, weight="bold", color=ACCENT,
              transform=note.transAxes, va="top")
    note.text(0.04, 0.76,
              f"Of the {len(top_two):,} counties in the two\n"
              f"highest death-rate rows, {len(zone):,} ({zone_share:.0f}%)\n"
              "are 25–100 miles from an active\nstroke trial (orange box).\n\n"
              f"Together they average\n{zone['stroke_deaths_annual_avg_2021_2023'].sum():,.0f} "
              "stroke deaths a year.\n\n"
              f"Only {len(near_top)} of those high-rate\ncounties are within 10 miles.",
              fontsize=10.5, color=INK, transform=note.transAxes, va="top", linespacing=1.35)
    fig.text(0.02, 0.965, "Counties with the highest stroke death rates are rarely near a stroke trial",
             fontsize=15, weight="bold", color=INK)
    fig.text(0.02, 0.915,
             "Each column shows how counties at that distance split across death-rate levels and sums to 100%.\n"
             "If distance made no difference, every cell would be 20%. Red cells have more counties than that; blue cells have fewer.",
             fontsize=9.5, color="#444", va="top")
    fig.text(0.02, 0.012,
             f"{SOURCE_NOTE}. Crude death rate = average annual cerebrovascular deaths 2021–2023 / 2020 Census population; "
             "not age-adjusted, so older rural populations raise it. Suppressed counts are left missing, not zero. "
             "Active sites: recruiting, enrolling by invitation, or active/not recruiting. Shows where deaths occur "
             "relative to trials, not that distance causes deaths. The 100+ mile column is mostly suppressed counties.",
             fontsize=6.8, color="#6a7179", wrap=True, va="bottom")
    fig.savefig(FIGURES / "07_stroke_mortality_vs_trial_distance_heatmap.png", bbox_inches="tight")
    plt.close(fig)


def fig_mortality_disparity_map(mortality_access):
    """US county map: stroke death-rate heat, active trial sites, disparity areas outlined."""
    d = mortality_access.copy()
    d["death_rate"] = 100_000 * d["stroke_deaths_annual_avg_2021_2023"] / d["cens_popn_20"]
    pub = d["mortality_published"]
    d["rate_class"] = pd.Series(pd.NA, index=d.index, dtype="Int64")
    d.loc[pub, "rate_class"], edges = pd.qcut(d.loc[pub, "death_rate"], 5, labels=False, retbins=True)
    d["disparity"] = d["rate_class"].ge(3).fillna(False) & d["population_mean_active_miles"].ge(25)

    geo = gpd.read_file(ROOT / "data/raw/cb_2020_us_county_500k.zip")
    geo = geo[~geo["STATEFP"].isin(NOT_MAPPED_FIPS)].to_crs(EQUAL_AREA_CRS)
    geo = geo.merge(d.drop(columns=["NAME", "STUSPS", "ALAND"]), left_on="GEOID", right_on="countyfips_2020", how="inner", validate="one_to_one")
    states = geo.dissolve(by="STATEFP")
    zone = geo[geo["disparity"]].dissolve()

    sites = pd.read_csv(PROCESSED / "trial_sites_clean.csv")
    sites = sites[sites["is_active_site"] & sites["lat"].notna()].drop_duplicates(subset=["lat", "lon"])
    sites = gpd.GeoDataFrame(sites, geometry=gpd.points_from_xy(sites.lon, sites.lat), crs="EPSG:4326")
    sites = sites.to_crs(EQUAL_AREA_CRS)
    sites = sites[sites.within(states.union_all())]

    heat = ["#fff3d6", "#fdd08a", "#f9a059", "#e4613a", "#a8231f"]
    fig, ax = plt.subplots(figsize=(14, 8.8))
    geo[~geo["mortality_published"]].plot(ax=ax, color=NO_DATA, linewidth=0)
    for k, color in enumerate(heat):
        geo[geo["rate_class"] == k].plot(ax=ax, color=color, linewidth=0)
    states.boundary.plot(ax=ax, color="white", linewidth=0.8)
    zone.boundary.plot(ax=ax, color=INK, linewidth=1.3)
    sites.plot(ax=ax, color=ACCENT2, markersize=16, edgecolor="white", linewidth=0.5, zorder=4)
    ax.set_axis_off()

    handles = [mpl.patches.Patch(color=heat[k], label=f"{edges[k]:.0f}–{edges[k + 1]:.0f}")
               for k in range(4, -1, -1)]
    handles.append(mpl.patches.Patch(color=NO_DATA, label="Suppressed"))
    leg1 = ax.legend(handles=handles, title="Stroke deaths per 100,000 residents per year",
                     loc="upper left", bbox_to_anchor=(0.02, -0.01), frameon=False, ncol=6,
                     fontsize=10, title_fontsize=10.5, alignment="left", columnspacing=1.2)
    ax.add_artist(leg1)
    ax.legend(handles=[
        mpl.lines.Line2D([], [], marker="o", color="w", markerfacecolor=ACCENT2, markersize=8,
                         label="Active stroke trial site"),
        mpl.patches.Patch(facecolor="none", edgecolor=INK, linewidth=1.8,
                          label="Disparity area: high death rate\nand 25+ miles from any trial")],
        loc="upper right", bbox_to_anchor=(0.99, -0.01), frameon=False, fontsize=10.5)

    shown = geo[geo["disparity"]]
    top_states = shown.groupby("STUSPS").size().sort_values(ascending=False).head(6)
    fig.text(0.02, 0.965, "Where stroke deaths are high and stroke trials are far away",
             fontsize=18, weight="bold", color=INK)
    fig.text(0.02, 0.925,
             f"Outlined: {len(shown):,} counties in the top two-fifths for stroke death rate whose residents live "
             f"25+ miles, on average, from an active stroke trial site.\n"
             f"They average {shown['stroke_deaths_annual_avg_2021_2023'].sum():,.0f} stroke deaths a year. "
             "Most are in " + ", ".join(f"{s} ({n})" for s, n in top_states.items()) + ".",
             fontsize=11, color="#333", va="top")
    fig.text(0.02, -0.07,
             f"{SOURCE_NOTE}. Crude death rate = average annual cerebrovascular deaths 2021–2023 / 2020 Census "
             "population; not age-adjusted. Grey counties have suppressed counts (small numbers), not zero deaths. "
             "Distance is a population-weighted straight-line average, not drive time. Active = recruiting, enrolling by "
             "invitation, or active/not recruiting. Alaska and Hawaii not shown. Shows geographic overlap, not cause.",
             fontsize=7.5, color="#6a7179", wrap=True, va="bottom")
    fig.subplots_adjust(left=0.01, right=0.99, top=0.88, bottom=0.06)
    fig.savefig(FIGURES / "10_stroke_mortality_trial_disparity_map.png", bbox_inches="tight")
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
        r = np.corrcoef(valid["stroke_crudeprev"], valid["population_mean_active_miles"])[0, 1]
        ax.text(0.05, 0.95, f"Pearson r = {r:.2f}", transform=ax.transAxes,
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
    
    print("Creating Figure 7: Stroke Mortality vs. Trial Distance Heatmap...")
    fig_mortality_distance_heatmap(mortality_access)
    
    print("Creating Figure 8: Burden vs. Distance Scatter...")
    fig_burden_distance_scatter(mortality_access)
    
    print("Creating Figure 9: Metro/Rural Mortality Comparison...")
    fig_metro_rural_mortality_comparison(mortality_access)
    
    print("Creating Figure 10: US Stroke Mortality and Trial Disparity Map...")
    fig_mortality_disparity_map(mortality_access)

    print(f"\n✓ Wrote 5 new figures to {FIGURES}")
    print("  - 06_burden_vs_trial_access_scatter.png (proposal requirement)")
    print("  - 07_stroke_mortality_vs_trial_distance_heatmap.png (heatmap)")
    print("  - 08_burden_distance_relationship.png (distance analysis)")
    print("  - 09_metro_rural_mortality_comparison.png (outcomes by region)")
    print("  - 10_stroke_mortality_trial_disparity_map.png (US map)")


if __name__ == "__main__":
    main()
