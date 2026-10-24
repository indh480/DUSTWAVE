"""Image analysis helpers for DUSTWAVE.

The dust score is a *relative* indicator: it only means something when two photos
are taken with the same camera position and lighting (e.g. before / after a test).
It is NOT a trained dust classifier.
"""
import cv2
import numpy as np

# Fixed, absolute threshold (grey levels). The original version used the image's own
# 65th percentile, which forces ~35% of any textured image to count as "dust".
DETAIL_THRESHOLD = 10


def to_gray(rgb: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)


def _normalize_exposure(gray: np.ndarray, target_mean: float = 128.0) -> np.ndarray:
    gain = target_mean / max(float(gray.mean()), 1.0)
    return np.clip(gray.astype(np.float32) * gain, 0, 255).astype(np.uint8)


def dust_map(rgb: np.ndarray, kernel: int = 9, threshold: int = DETAIL_THRESHOLD):
    """Return (mask, score). score = % of pixels with local contrast above a fixed threshold."""
    gray = _normalize_exposure(to_gray(rgb))
    k = kernel | 1  # kernel must be odd
    smooth = cv2.GaussianBlur(gray, (k, k), 0)
    detail = cv2.absdiff(gray, smooth)
    mask = (detail > threshold).astype(np.uint8) * 255
    return mask, float(np.mean(mask > 0) * 100.0)


def compare_before_after(before_rgb: np.ndarray, after_rgb: np.ndarray) -> dict:
    """Compare two photos of the same surface. Returns scores, efficiency and a change map."""
    h, w = before_rgb.shape[:2]
    after_rgb = cv2.resize(after_rgb, (w, h), interpolation=cv2.INTER_AREA)
    mask_b, score_b = dust_map(before_rgb)
    mask_a, score_a = dust_map(after_rgb)
    efficiency = 0.0 if score_b < 1e-6 else (score_b - score_a) / score_b * 100.0
    change = cv2.absdiff(_normalize_exposure(to_gray(before_rgb)),
                         _normalize_exposure(to_gray(after_rgb)))
    return {
        "score_before": score_b,
        "score_after": score_a,
        "cleaning_efficiency_pct": efficiency,
        "change_map": change,
        "mask_before": mask_b,
        "mask_after": mask_a,
    }
