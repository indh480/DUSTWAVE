"""Toy simulation of dust on a surface, to demonstrate the closed loop WITHOUT hardware.

THIS IS A MODEL, NOT EXPERIMENTAL EVIDENCE. It assumes dust is released when the drive
frequency is near a (hidden) resonance, scaled by duty cycle and by how sticky the dust is.
Use it to show the control loop works; use real before/after photos to show cleaning works.
"""
import numpy as np


class DustSurfaceSim:
    def __init__(self, size=64, resonance_hz=41_300.0, bandwidth_hz=1_500.0,
                 stickiness=0.6, seed=0):
        self.rng = np.random.default_rng(seed)
        self.dust = self.rng.uniform(0.3, 1.0, (size, size)) * (self.rng.random((size, size)) < 0.7)
        self.resonance = resonance_hz
        self.bw = bandwidth_hz
        self.stick = stickiness

    # what the vibration sensor would read at a given frequency (for the sweep step)
    def sensor_response(self, freq_hz, noise=0.03):
        lor = 1.0 / (1.0 + ((freq_hz - self.resonance) / self.bw) ** 2)
        return float(lor + self.rng.normal(0, noise) + 0.05)

    def dust_score(self):
        return float(np.mean(self.dust > 0.05) * 100.0)

    def apply(self, freq_hz, duty, burst_ms=100):
        """Run one burst. Returns dust-score reduction in percentage points."""
        before = self.dust_score()
        lor = 1.0 / (1.0 + ((freq_hz - self.resonance) / self.bw) ** 2)
        p_release = np.clip(lor * duty * 4.0 * (1.0 - self.stick) * (burst_ms / 100), 0, 0.9)
        released = self.rng.random(self.dust.shape) < p_release
        self.dust = np.where(released, self.dust * 0.3, self.dust)
        self.dust[self.dust < 0.05] = 0
        return before - self.dust_score()
