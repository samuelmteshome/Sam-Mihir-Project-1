"""Reusable geographic distance and weighted-summary functions."""

import numpy as np

EARTH_RADIUS_MILES = 3958.7613


def coordinates(values):
    points = np.asarray(values, dtype=float)
    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError("Expected latitude/longitude pairs")
    if not np.isfinite(points).all() or (np.abs(points[:, 0]) > 90).any() or (np.abs(points[:, 1]) > 180).any():
        raise ValueError("Invalid latitude/longitude")
    return np.radians(points)


def nearest_miles(origins, destinations, chunk_size=1000):
    """Haversine distance to nearest destination, with bounded memory; no road model."""
    origin, destination = coordinates(origins), coordinates(destinations)
    if not len(destination) or chunk_size < 1:
        raise ValueError("Need destinations and a positive chunk size")
    result = np.empty(len(origin))
    for start in range(0, len(origin), chunk_size):
        block = origin[start:start + chunk_size]
        dlat = block[:, None, 0] - destination[None, :, 0]
        dlon = block[:, None, 1] - destination[None, :, 1]
        a = np.sin(dlat / 2) ** 2 + np.cos(block[:, None, 0]) * np.cos(destination[None, :, 0]) * np.sin(dlon / 2) ** 2
        result[start:start + len(block)] = 2 * EARTH_RADIUS_MILES * np.arcsin(np.sqrt(np.clip(a.min(axis=1), 0, 1)))
    return result


def weighted_summary(distances, population):
    """Empirical inverse-CDF percentiles; strict > thresholds (not >=)."""
    values, weights = np.asarray(distances, dtype=float), np.asarray(population, dtype=float)
    if values.ndim != 1 or values.shape != weights.shape or not len(values):
        raise ValueError("Need equally sized distance and population vectors")
    if not np.isfinite(values).all() or not np.isfinite(weights).all() or (values < 0).any() or (weights < 0).any() or weights.sum() <= 0:
        raise ValueError("Invalid distances or population weights")
    nonzero = weights > 0
    values, weights = values[nonzero], weights[nonzero]
    order = np.argsort(values)
    cdf = np.cumsum(weights[order]) / weights.sum()
    return {
        "population": int(weights.sum()),
        "percentiles_miles": {str(p): float(values[order][np.searchsorted(cdf, p / 100)]) for p in (50, 75, 90, 95)},
        "percent_beyond_miles": {str(d): float(100 * weights[values > d].sum() / weights.sum()) for d in (25, 50, 100)},
    }
