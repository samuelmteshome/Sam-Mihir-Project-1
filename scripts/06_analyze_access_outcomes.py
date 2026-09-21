"""Offline population distance and stroke-mortality access extension.

Run after 03_clean_merge.py and 05_get_access_outcomes.py. Does not modify the
partner's processed tables. See docs/ACCESS_OUTCOMES.md before quoting results.
"""

import hashlib
from datetime import datetime
import json

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from _common import ROOT, RAW, read_manifest, use_cached
from access_metrics import nearest_miles, weighted_summary

OUT = ROOT / "data/processed"
REPORTS = ROOT / "reports"
FIGURES = ROOT / "figures"
US_STATES = set("01 02 04 05 06 08 09 10 11 12 13 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 44 45 46 47 48 49 50 51 53 54 55 56".split())
DEATH_FIELD = "stroke_deaths_annual_avg_2021_2023"


def load_inputs():
    for key in ("census_population_centers_2020", "census_boundaries_2020", "hrsa_ahrf_mortality_2025"):
        if not use_cached(key, False):
            raise ValueError("Run 05_get_access_outcomes.py first")
    tracts = pd.read_csv(RAW / "tract_population_centers_2020.txt", dtype={"STATEFP": str, "COUNTYFP": str, "TRACTCE": str})
    tracts = tracts.loc[tracts.STATEFP.isin(US_STATES)].copy()
    tracts["countyfips_2020"] = tracts.STATEFP + tracts.COUNTYFP
    tracts["tractfips_2020"] = tracts.countyfips_2020 + tracts.TRACTCE
    if not tracts.tractfips_2020.is_unique or tracts.POPULATION.sum() != 331449281:
        raise ValueError("Census tract coverage differs from the 2020 US resident population")
    boundaries = gpd.read_file(RAW / "cb_2020_us_county_500k.zip").to_crs(4326)
    boundaries = boundaries.loc[boundaries.STATEFP.isin(US_STATES)].copy()
    if not boundaries.GEOID.is_unique or set(tracts.countyfips_2020) != set(boundaries.GEOID):
        raise ValueError("Tract/county geography coverage mismatch")
    sites = pd.read_csv(OUT / "trial_sites_clean.csv", dtype={"countyfips": str})
    # The existing pipeline holds missing coordinates / disputed locations for review.
    sites = sites.loc[sites.state_agrees.eq(True) & sites.lat.notna() & sites.lon.notna()].copy()
    points = gpd.GeoDataFrame(sites, geometry=gpd.points_from_xy(sites.lon, sites.lat), crs=4326)
    assigned = gpd.sjoin(points, boundaries[["GEOID", "STATE_NAME", "geometry"]], how="left", predicate="within")
    if assigned.index.duplicated().any() or assigned.GEOID.isna().any() or assigned.state.ne(assigned.STATE_NAME).any():
        raise ValueError("Unresolved 2020 county assignment; review sites before generating claims")
    assigned = assigned.rename(columns={"GEOID": "countyfips_2020"})
    ahrf = pd.read_csv(RAW / "ahrf_stroke_mortality_2025.csv", dtype={"fips_st_cnty": str})
    ahrf = ahrf.rename(columns={"fips_st_cnty": "countyfips_2020", "cerbrvsc_dis_deth_3yr_23": DEATH_FIELD,
                                "cerbrvsc_dis_deth_3yr_22": "stroke_deaths_annual_avg_2020_2022"})
    county = boundaries[["GEOID", "NAME", "STUSPS", "ALAND"]].rename(columns={"GEOID": "countyfips_2020"})
    county = county.merge(ahrf, on="countyfips_2020", how="left", validate="one_to_one", indicator=True)
    if county._merge.ne("both").any():
        raise ValueError("AHRF missing a 2020 county record")
    county = county.drop(columns="_merge")
    county["mortality_published"] = county[DEATH_FIELD].notna()
    county["metro_status_2023"] = np.select(
        [county.rural_urban_contnm_23.between(1, 3), county.rural_urban_contnm_23.between(4, 9)],
        ["metro", "nonmetro"], default="unavailable")
    return tracts, assigned, county


def death_summary(county, cohort):
    observed = county.loc[county.mortality_published]
    no_site = observed[f"trial_site_pairs_{cohort}"].eq(0)
    total = float(observed[DEATH_FIELD].sum())
    numerator = float(observed.loc[no_site, DEATH_FIELD].sum())
    return {
        "counties_with_published_counts": len(observed),
        "counties_without_published_counts": int((~county.mortality_published).sum()),
        "sum_published_annual_average_deaths": total,
        "sum_published_annual_average_deaths_in_no_site_counties": numerator,
        "percent_published_deaths_in_no_site_counties": 100 * numerator / total if total else None,
        "no_site_counties_with_published_counts": int(no_site.sum()),
        "no_site_counties_without_published_counts": int((~county.mortality_published & county[f"trial_site_pairs_{cohort}"].eq(0)).sum()),
    }


def main():
    tracts, sites, county = load_inputs()
    for directory in (OUT, REPORTS, FIGURES):
        directory.mkdir(parents=True, exist_ok=True)
    cohorts = {
        "active": sites.is_active_site.eq(True),
        "recruiting": sites.is_recruiting_site.eq(True),
        "active_plus_unknown_sensitivity": sites.is_active_site.eq(True) | sites.site_status.isna(),
    }
    summary = {
        "population_year": 2020, "population_scope": "50 states and DC, all ages, residents (not citizenship)",
        "mortality_period": "2021–2023", "county_geography": 2020,
        "trial_snapshot_utc": read_manifest()["sources"]["clinicaltrials"]["retrieved_at_utc"],
        "distance_method": "Tract population-weighted mean center to nearest registry coordinate; great-circle miles",
        "death_denominator": "Sum of published county annual-average counts; excludes suppressed/missing counties",
        "processed_input_sha256": {name: hashlib.sha256((OUT / name).read_bytes()).hexdigest()
                                   for name in ("trial_sites_clean.csv", "site_assignment_review.csv", "county_analysis.csv")},
        "county_count": len(county), "tract_count": len(tracts),
        "review_rows_excluded_upstream": len(pd.read_csv(OUT / "site_assignment_review.csv")),
        "cohorts": {},
    }
    for name, mask in cohorts.items():
        selected = sites.loc[mask]
        coords = selected[["lat", "lon"]].drop_duplicates()
        distance_col = f"nearest_{name}_miles"
        tracts[distance_col] = nearest_miles(tracts[["LATITUDE", "LONGITUDE"]], coords)
        county[f"trial_site_pairs_{name}"] = county.countyfips_2020.map(selected.groupby("countyfips_2020").size()).fillna(0).astype(int)
        # County mean is a resident-population proxy, never deceased-person distance.
        numerator = (tracts[distance_col] * tracts.POPULATION).groupby(tracts.countyfips_2020).sum()
        denominator = tracts.POPULATION.groupby(tracts.countyfips_2020).sum()
        county[f"population_mean_{name}_miles"] = county.countyfips_2020.map(numerator / denominator)
        summary["cohorts"][name] = {
            "geocoded_trial_site_pairs": len(selected), "unique_registry_coordinates": len(coords),
            "counties_with_site": int(county[f"trial_site_pairs_{name}"].gt(0).sum()),
            **weighted_summary(tracts[distance_col], tracts.POPULATION),
            "mortality": death_summary(county, name),
        }
    summary["mortality_by_metro_status_active"] = {
        name: death_summary(group, "active") for name, group in county.groupby("metro_status_2023")
    }
    tracts = tracts.merge(county[["countyfips_2020", "metro_status_2023"]], on="countyfips_2020", validate="many_to_one")
    summary["population_distance_by_metro_status_active"] = {
        name: weighted_summary(group.nearest_active_miles, group.POPULATION)
        for name, group in tracts.groupby("metro_status_2023")
    }
    county = county.sort_values("countyfips_2020")
    tracts = tracts.sort_values("tractfips_2020")
    tracts.to_csv(OUT / "tract_trial_distance.csv", index=False, float_format="%.6f")
    county.to_csv(OUT / "county_mortality_access.csv", index=False, float_format="%.6f")

    # Convenient current-geography join; retain explicit missingness for Connecticut.
    places = pd.read_csv(OUT / "county_analysis.csv", dtype={"countyfips": str})
    features = county[["countyfips_2020", DEATH_FIELD, "mortality_published", "metro_status_2023", "population_mean_active_miles"]]
    combined = places.merge(features, left_on="countyfips", right_on="countyfips_2020", how="left", validate="one_to_one", indicator=True)
    combined["mortality_geography_match"] = combined.pop("_merge").eq("both")
    combined.to_csv(OUT / "county_analysis_with_mortality.csv", index=False, float_format="%.6f")
    summary["places_counties_without_matching_2020_geography"] = combined.loc[~combined.mortality_geography_match, "countyfips"].tolist()
    (REPORTS / "access_outcomes_summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    plot_results(tracts, summary)
    write_report(summary)
    print(json.dumps(summary["cohorts"]["active"], indent=2))


def plot_results(tracts, summary):
    snapshot_label = datetime.fromisoformat(summary["trial_snapshot_utc"]).strftime("%B %Y")
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "axes.spines.top": False, "axes.spines.right": False})
    fig, ax = plt.subplots(figsize=(10, 6))
    for cohort, label, color in (("active", "Known active sites", "#176b70"), ("recruiting", "Confirmed recruiting sites", "#b26739")):
        distance = tracts[f"nearest_{cohort}_miles"].to_numpy()
        order = np.argsort(distance)
        cumulative = np.cumsum(tracts.POPULATION.to_numpy()[order]) / tracts.POPULATION.sum() * 100
        ax.plot(distance[order], cumulative, label=label, color=color, linewidth=2)
    ax.set(xlim=(0, 250), ylim=(0, 100), xlabel="Straight-line miles to nearest recorded trial site", ylabel="Estimated share of U.S. residents within distance (%)")
    ax.set_title("How far do Americans live from stroke trial sites?", loc="left", fontsize=17, pad=17)
    ax.grid(alpha=.15)
    ax.legend(loc="lower right", frameon=False)
    beyond = summary["cohorts"]["active"]["percent_beyond_miles"]["50"]
    ax.annotate(f"{beyond:.1f}% live more than 50 miles away*", xy=(50, 100-beyond), xytext=(95, 47),
                arrowprops={"arrowstyle": "->", "color": "#176b70"}, color="#176b70", fontsize=12)
    fig.text(.10, .035, f"*Estimate using 2020 tract population centers; 50 states + DC. Registry snapshot: {snapshot_label}.\nNot driving distance, patient addresses, emergency treatment access, or trial eligibility. Axis ends at 250 miles.", fontsize=9, color="#444444")
    fig.subplots_adjust(bottom=.22, top=.87, left=.1, right=.96)
    fig.savefig(FIGURES / "population_trial_distance.png", dpi=180)
    plt.close(fig)
    mortality = summary["cohorts"]["active"]["mortality"]
    share = mortality["percent_published_deaths_in_no_site_counties"]
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.barh([0], [share], color="#b26739", height=.45)
    ax.barh([0], [100-share], left=[share], color="#176b70", height=.45)
    ax.text(share/2, 0, f"{share:.1f}%\nNo recorded active site", va="center", ha="center", color="white", fontsize=14)
    ax.text(share+(100-share)/2, 0, f"{100-share:.1f}%\nAt least one active site", va="center", ha="center", color="white", fontsize=14)
    ax.set(xlim=(0, 100), yticks=[], xlabel="Share of published average annual stroke deaths (%)")
    ax.set_title("Stroke deaths and county trial-site presence", loc="left", fontsize=17, pad=22)
    ax.spines['left'].set_visible(False)
    fig.text(.08, .045, f"HRSA/NCHS, 2021–2023 average annual cerebrovascular deaths (I60–I69), by residence.\nPublished counts: {mortality['counties_with_published_counts']:,} counties; {mortality['counties_without_published_counts']:,} suppressed/missing counties excluded.\nTrial sites: {snapshot_label} snapshot. This is not the share of all U.S. stroke deaths or evidence of causation.", fontsize=9, color="#444444")
    fig.subplots_adjust(bottom=.32, top=.8, left=.08, right=.96)
    fig.savefig(FIGURES / "stroke_mortality_trial_access.png", dpi=180)
    plt.close(fig)


def write_report(summary):
    snapshot_label = datetime.fromisoformat(summary["trial_snapshot_utc"]).strftime("%B %Y")
    active = summary['cohorts']['active']
    mortality = active['mortality']
    lines = ["# Stroke mortality and distance to trial sites", "", "## Slide-ready statements", "",
        f"- **An estimated {active['percent_beyond_miles']['50']:.1f}% of U.S. residents live more than 50 straight-line miles from a recorded active stroke trial site.** Estimate uses 2020 Census tract population centers and the {snapshot_label} registry snapshot.",
        f"- **An estimated 90% of U.S. residents live within {active['percentiles_miles']['90']:.1f} straight-line miles of a recorded active stroke trial site.**",
        f"- **Among counties with published counts, {mortality['percent_published_deaths_in_no_site_counties']:.1f}% of average annual stroke deaths occurred among residents of counties with no recorded active trial site.** Deaths: 2021–2023; trial sites: {snapshot_label}.", "",
        f"Mortality denominator: {mortality['sum_published_annual_average_deaths']:,.0f} published annual-average deaths across {mortality['counties_with_published_counts']:,} counties; {mortality['counties_without_published_counts']:,} counties have suppressed/missing counts. The numerator is {mortality['sum_published_annual_average_deaths_in_no_site_counties']:,.0f}. These are sums of source-reported rounded annual averages, not exact three-year totals.", "",
        "Do not shorten the mortality statement to a percentage of **all** U.S. stroke deaths. Missing counts are not zeros. County site presence does not show how far deceased people lived from a site.", "",
        "## Distance and site-definition sensitivity", "",
        "| Site definition | More than 25 mi | More than 50 mi | More than 100 mi | Median mi | 90th percentile mi |", "|---|---:|---:|---:|---:|---:|"]
    for name, item in summary['cohorts'].items():
        values = item['percent_beyond_miles']; p = item['percentiles_miles']
        lines.append(f"| {name} | {values['25']:.1f}% | {values['50']:.1f}% | {values['100']:.1f}% | {p['50']:.1f} | {p['90']:.1f} |")
    lines += ["", "The active-plus-unknown row is an optimistic sensitivity scenario; unknown site status is not confirmed activity or enrollment availability.", "",
              "## Metropolitan context", "", "| County classification | Population >50 mi from active site | Counties with death counts | Published deaths in no-site counties |", "|---|---:|---:|---:|"]
    for name, item in summary['population_distance_by_metro_status_active'].items():
        deaths = summary['mortality_by_metro_status_active'][name]
        share = deaths['percent_published_deaths_in_no_site_counties']
        share_text = f"{share:.1f}%" if share is not None else "unavailable"
        lines.append(f"| {name} | {item['percent_beyond_miles']['50']:.1f}% | {deaths['counties_with_published_counts']} | {share_text} |")
    lines += ["", "Metro/nonmetro uses USDA 2023 Rural-Urban Continuum Codes carried in AHRF. Nonmetro is a county classification, not a measure of each resident's rurality. Historical Connecticut counties have no 2023 code. Suppression particularly affects small counties.", "",
              "## Interpretation", "", "These are geographic descriptions of a broad stroke-related interventional research cohort, including prevention and rehabilitation. They do not identify thrombolysis-capable hospitals or demonstrate that rural residents were excluded from enrollment. They cannot establish different tPA treatment windows, treatment effectiveness, or a causal effect of trial-site location on mortality.", "",
              "Population: all ages, 331,449,281 residents in 50 states + DC. Distances are approximate, not road travel times; registry coordinates may represent cities. Active sites include active/not recruiting sites. See the recruiting-only sensitivity for enrollment-oriented wording.", "",
              "## Reproduce and inspect", "", "Run `python scripts/06_analyze_access_outcomes.py` after the existing cleaning pipeline. See [methods and field guide](../docs/ACCESS_OUTCOMES.md), [machine-readable results](access_outcomes_summary.json), and the two new figures. Data acquisition URLs, hashes, periods, and source field definitions are in the raw manifest and archived HRSA documentation.", ""]
    (REPORTS / "access_outcomes.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
