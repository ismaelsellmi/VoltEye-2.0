"""Tests de VoltEye Grid : répartition des démarrages entre zones."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from volteye import config as C  # noqa: E402
from volteye import grid  # noqa: E402
from volteye.optimization import TASKS  # noqa: E402


def _toy():
    hours = np.arange(24)
    base = np.where((hours >= 7) & (hours < 21), 800.0, 200.0) + 150 * np.exp(-((hours - 15) / 2.5) ** 2)
    bases = [base, base * 0.6, base * 1.3]
    kws = [30.0, 20.0, 40.0]
    prices = np.array([C.tariff(h, 7) for h in range(24)])
    return bases, kws, prices


def test_shares_are_complete_and_inside_windows():
    bases, kws, prices = _toy()
    shares, status = grid.plan_grid(bases, kws, prices)
    assert status == "Optimal"
    for zone in shares:
        for k, task_shares in enumerate(zone):
            assert abs(sum(task_shares.values()) - 1) < 1e-6
            lo, hi = TASKS[k]["fenetre"]
            assert all(lo <= s < hi and s + TASKS[k]["duree"] <= 24 for s in task_shares)


def test_grid_peak_not_above_uncoordinated_strategies():
    bases, kws, prices = _toy()
    shares, _ = grid.plan_grid(bases, kws, prices)

    def peak(strategy):
        return max(sum(b + grid.flex_profile(s, kw) for b, s, kw in zip(bases, strategy, kws)))

    current = [grid.fixed_shares([max(t["fenetre"][0], 7) for t in TASKS])] * 3
    tariff = [grid.fixed_shares(grid.tariff_aware_starts(prices))] * 3
    assert peak(shares) <= peak(current) + 1e-6 and peak(shares) <= peak(tariff) + 1e-6


def test_flex_profile_conserves_energy():
    shares = [{s: 0.5, s + 1: 0.5} for s in (6, 8, 0, 0, 0, 6)]
    prof = grid.flex_profile(shares, kw=10.0)
    assert abs(prof.sum() - 10.0 * sum(t["kW"] * t["duree"] for t in TASKS)) < 1e-6
