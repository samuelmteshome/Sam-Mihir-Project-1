"""Distance math, suppression handling, and committed feature consistency."""
import csv
import importlib.util
import io
import json
import math
from pathlib import Path
import sys
import unittest
from zipfile import ZipFile
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from access_metrics import EARTH_RADIUS_MILES, nearest_miles, weighted_summary
spec = importlib.util.spec_from_file_location('get_access', ROOT / 'scripts/05_get_access_outcomes.py')
acquire = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acquire)


class DistanceTests(unittest.TestCase):
    def test_known_distances_and_dateline(self):
        distance = nearest_miles([[0, 0], [0, 1], [90, 30]], [[0, 0]], chunk_size=1)
        np.testing.assert_allclose(distance, [0, math.pi * EARTH_RADIUS_MILES / 180, math.pi * EARTH_RADIUS_MILES / 2])
        self.assertAlmostEqual(nearest_miles([[0, 179]], [[0, -179]])[0], 2 * math.pi * EARTH_RADIUS_MILES / 180)

    def test_nearest_destination_across_border_and_duplicate(self):
        # No county/state filter is used: the geographically nearest point wins.
        self.assertAlmostEqual(nearest_miles([[0, 1]], [[0, 100], [0, 2], [0, 2]])[0], math.pi * EARTH_RADIUS_MILES / 180)

    def test_population_not_tract_weighting_and_strict_threshold(self):
        result = weighted_summary([0, 50, 100], [0, 90, 10])
        self.assertEqual(result['percentiles_miles']['50'], 50)
        self.assertEqual(result['percentiles_miles']['90'], 50)
        self.assertEqual(result['percent_beyond_miles']['50'], 10)
        self.assertEqual(result['percent_beyond_miles']['100'], 0)

    def test_bad_inputs_fail(self):
        for origins, destinations in [([[91, 0]], [[0, 0]]), ([[0, float('nan')]], [[0, 0]]), ([[0, 0]], np.empty((0, 2)))]:
            with self.assertRaises(ValueError):
                nearest_miles(origins, destinations)
        for distances, weights in [([1], [0]), ([1], [-1]), ([float('nan')], [1]), ([1, 2], [1])]:
            with self.assertRaises(ValueError):
                weighted_summary(distances, weights)


class AcquisitionTests(unittest.TestCase):
    def archive(self, rows):
        text = io.StringIO()
        writer = csv.DictWriter(text, fieldnames=acquire.AHRF_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
        payload = io.BytesIO()
        with ZipFile(payload, 'w') as archive:
            archive.writestr('example/AHRF2025.csv', text.getvalue())
        return payload.getvalue()

    def test_suppression_stays_blank_and_fips_keeps_zero(self):
        data, count = acquire.project_ahrf(self.archive([{'fips_st_cnty': '01001', 'cerbrvsc_dis_deth_3yr_23': ''}]))
        row = next(csv.DictReader(io.StringIO(data.decode())))
        self.assertEqual(count, 1)
        self.assertEqual(row['fips_st_cnty'], '01001')
        self.assertEqual(row['cerbrvsc_dis_deth_3yr_23'], '')

    def test_duplicate_counties_and_changed_suppression_rejected(self):
        for rows in [[{'fips_st_cnty': '01001'}] * 2, [{'fips_st_cnty': '01001', 'cerbrvsc_dis_deth_3yr_23': '-999'}]]:
            with self.assertRaises(ValueError):
                acquire.project_ahrf(self.archive(rows))


class FeatureIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = json.loads((ROOT / 'reports/access_outcomes_summary.json').read_text())
        cls.county = pd.read_csv(ROOT / 'data/processed/county_mortality_access.csv', dtype={'countyfips_2020': str})
        cls.tracts = pd.read_csv(ROOT / 'data/processed/tract_trial_distance.csv', dtype={'tractfips_2020': str})

    def test_full_population_and_nested_cohorts(self):
        self.assertEqual(self.tracts.POPULATION.sum(), 331449281)
        self.assertTrue(self.tracts.tractfips_2020.is_unique)
        self.assertTrue((self.tracts.nearest_recruiting_miles >= self.tracts.nearest_active_miles - 1e-6).all())
        self.assertTrue((self.tracts.nearest_active_miles >= self.tracts.nearest_active_plus_unknown_sensitivity_miles - 1e-6).all())
        self.assertTrue(self.tracts.filter(regex='^nearest_').notna().all().all())

    def test_count_denominator_and_missingness(self):
        field = 'stroke_deaths_annual_avg_2021_2023'
        raw = pd.read_csv(ROOT / 'data/raw/ahrf_stroke_mortality_2025.csv', dtype={'fips_st_cnty': str}).set_index('fips_st_cnty')
        expected = self.county.countyfips_2020.map(raw.cerbrvsc_dis_deth_3yr_23)
        pd.testing.assert_series_equal(expected, self.county[field], check_names=False)
        observed = self.county[self.county.mortality_published]
        total = observed[field].sum()
        numerator = observed.loc[observed.trial_site_pairs_active.eq(0), field].sum()
        self.assertAlmostEqual(100 * numerator / total, self.summary['cohorts']['active']['mortality']['percent_published_deaths_in_no_site_counties'])
        self.assertTrue(self.county.loc[~self.county.mortality_published, field].isna().all())
        self.assertEqual(len(self.county), 3143)

    def test_historical_connecticut_not_misjoined(self):
        old_ct = self.county[self.county.countyfips_2020.str.startswith('09')]
        self.assertEqual(len(old_ct), 8)
        self.assertTrue(old_ct.mortality_published.all())
        combined = pd.read_csv(ROOT / 'data/processed/county_analysis_with_mortality.csv', dtype={'countyfips': str})
        ct = combined[combined.countyfips.str.startswith('09')]
        self.assertEqual(len(ct), 9)
        self.assertFalse(ct.mortality_geography_match.any())
        self.assertTrue(ct.stroke_deaths_annual_avg_2021_2023.isna().all())


if __name__ == '__main__':
    unittest.main()
