"""Closed-loop pattern selection for DUSTWAVE.

Three parts:
  1. find_resonance()      - pick the drive frequency where the surface responds most
                             (from a measured sweep: frequency vs. sensor amplitude).
  2. AdaptiveController    - after each cycle, uses the measured cleaning result to adjust
                             frequency offset and duty cycle (a (1+1) evolution strategy).
  3. recommend_pattern()   - wraps the above into a candidate setting for a bench test.

All outputs are clamped to SAFE_LIMITS. These are conservative defaults for a small
piezo disc on a bench behind a proper driver circuit, NOT validated cleaning settings.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

import numpy as np

SAFE_LIMITS = {
    "freq_min_hz": 20_000,
    "freq_max_hz": 60_000,
    "duty_min": 0.05,
    "duty_max": 0.30,       # hard cap
    "burst_ms_max": 200,    # max continuous on-time per burst
}


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def find_resonance(freqs, responses, smooth: int = 5) -> dict:
    """Return the peak of a (smoothed) frequency sweep and how sharp it is."""
    f = np.asarray(freqs, dtype=float)
    r = np.asarray(responses, dtype=float)
    if f.size < 5 or f.size != r.size:
        raise ValueError("need >= 5 matching (frequency, response) points")
    order = np.argsort(f)
    f, r = f[order], r[order]
    k = max(1, min(smooth, f.size))
    rs = np.convolve(r, np.ones(k) / k, mode="same")
    i = int(np.argmax(rs))
    peak = float(rs[i])
    baseline = float(np.median(rs))
    half = baseline + (peak - baseline) / 2
    above = np.where(rs >= half)[0]
    bandwidth = float(f[above.max()] - f[above.min()]) if above.size > 1 else 0.0
    return {
        "resonance_hz": float(f[i]),
        "peak_response": peak,
        "baseline_response": baseline,
        "peak_to_baseline": peak / baseline if baseline > 0 else float("inf"),
        "bandwidth_hz": bandwidth,
        "reliable": bool(peak > 2 * baseline and bandwidth > 0),
    }


@dataclass
class Pattern:
    freq_hz: float
    duty: float
    burst_ms: int = 100

    def clamped(self) -> "Pattern":
        L = SAFE_LIMITS
        return Pattern(
            clamp(self.freq_hz, L["freq_min_hz"], L["freq_max_hz"]),
            clamp(self.duty, L["duty_min"], L["duty_max"]),
            int(clamp(self.burst_ms, 10, L["burst_ms_max"])),
        )

    def as_dict(self) -> dict:
        return {"frequency_hz": round(self.freq_hz, 1), "duty_cycle": round(self.duty, 3),
                "burst_ms": self.burst_ms}


@dataclass
class AdaptiveController:
    """Propose a pattern -> run it -> report reward (cleaning gain) -> repeat."""
    resonance_hz: float
    bandwidth_hz: float = 2_000.0
    seed: int | None = None
    best: Pattern = field(init=False)
    best_reward: float = field(default=float("-inf"), init=False)
    _step: float = field(default=1.0, init=False)
    _rng: random.Random = field(init=False, repr=False)
    _last: Pattern | None = field(default=None, init=False)

    def __post_init__(self):
        self._rng = random.Random(self.seed)
        self.best = Pattern(self.resonance_hz, SAFE_LIMITS["duty_min"] * 2).clamped()

    def propose(self) -> Pattern:
        if self._last is None:                    # first cycle: resonance, low duty
            self._last = self.best
            return self.best
        df = self._rng.gauss(0, self.bandwidth_hz * 0.5 * self._step)
        dd = self._rng.gauss(0, 0.05 * self._step)
        self._last = Pattern(self.best.freq_hz + df, self.best.duty + dd, self.best.burst_ms).clamped()
        return self._last

    def report(self, reward: float) -> None:
        """reward = dust-score reduction (percentage points) achieved by the last pattern,
        minus a small penalty for energy (duty) so it does not just max out power."""
        reward = reward - 5.0 * self._last.duty
        if reward > self.best_reward:
            self.best_reward, self.best = reward, self._last
        else:
            self._step = max(0.1, self._step * 0.85)   # shrink search when not improving


def recommend_pattern(surface: str, dust_score: float, sweep: dict | None = None) -> dict:
    """Candidate bench-test settings. Numeric values only if a measured sweep is available."""
    level = "low" if dust_score < 5 else "medium" if dust_score < 15 else "high"
    out = {"surface": surface.lower(), "dust_level": level}
    if sweep and sweep.get("reliable"):
        duty = {"low": 0.08, "medium": 0.12, "high": 0.18}[level]
        out["candidate_pattern"] = Pattern(sweep["resonance_hz"], duty).clamped().as_dict()
        out["basis"] = "measured resonance from sensor sweep"
    else:
        out["candidate_pattern"] = None
        out["basis"] = "run a frequency sweep first - no reliable resonance measured yet"
    out["note"] = "Start at the lowest duty; stop if the surface, mount or driver heats or buzzes audibly."
    return out
