"""Deterministic technical image-quality analysis for verified Artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO

from PIL import Image, ImageChops, ImageFilter, ImageStat


@dataclass(frozen=True)
class QualityThresholds:
    """Versioned defaults used to classify technical image quality."""

    min_short_side_px: int = 720
    min_total_pixels: int = 1_000_000
    exposure_fail_low: float = 20.0
    exposure_warn_low: float = 40.0
    exposure_warn_high: float = 215.0
    exposure_fail_high: float = 235.0
    dark_pixel_max: int = 10
    bright_pixel_min: int = 245
    clip_warn_ratio: float = 0.50
    clip_fail_ratio: float = 0.80
    sharpness_fail_below: float = 2.0
    sharpness_warn_below: float = 5.0


@dataclass(frozen=True)
class ImageQualityResult:
    """JSON-safe image-quality finding for a single Artifact."""

    artifact_id: str
    quality_status: str
    analyzer_version: str
    metrics: dict[str, float]
    thresholds: dict[str, dict[str, float | int]]
    checks: dict[str, str]
    reasons: tuple[str, ...]

    def as_payload(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact_id,
            "quality_status": self.quality_status,
            "analyzer_version": self.analyzer_version,
            "metrics": self.metrics,
            "thresholds": self.thresholds,
            "checks": self.checks,
            "reasons": list(self.reasons),
        }


class ImageQualityAnalyzer:
    """Pillow-only deterministic analyzer for technical image properties."""

    VERSION = "0.1.0"

    def __init__(self, thresholds: QualityThresholds | None = None) -> None:
        self._thresholds = thresholds or QualityThresholds()

    def analyze(self, stream: BinaryIO, *, artifact_id: str) -> ImageQualityResult:
        """Analyze a verified image stream without changing its bytes or metadata."""
        with Image.open(stream) as image:
            image.load()
            gray = image.convert("L")

        thresholds = self._thresholds
        histogram = gray.histogram()
        pixel_count = gray.width * gray.height
        mean_luminance = float(ImageStat.Stat(gray).mean[0])
        dark_clip_ratio = (
            sum(histogram[: thresholds.dark_pixel_max + 1]) / pixel_count
        )
        bright_clip_ratio = sum(histogram[thresholds.bright_pixel_min :]) / pixel_count
        blurred = gray.filter(ImageFilter.GaussianBlur(radius=1))
        sharpness_rms = float(ImageStat.Stat(ImageChops.difference(gray, blurred)).rms[0])

        metrics_unrounded = {
            "short_side_px": float(min(gray.width, gray.height)),
            "total_pixels": float(pixel_count),
            "mean_luminance": mean_luminance,
            "dark_clip_ratio": dark_clip_ratio,
            "bright_clip_ratio": bright_clip_ratio,
            "sharpness_rms": sharpness_rms,
        }
        checks, reasons = self._classify(metrics_unrounded)
        quality_status = _overall_status(checks.values())

        return ImageQualityResult(
            artifact_id=artifact_id,
            quality_status=quality_status,
            analyzer_version=self.VERSION,
            metrics={key: round(value, 4) for key, value in metrics_unrounded.items()},
            thresholds=_threshold_payload(thresholds),
            checks=checks,
            reasons=tuple(reasons),
        )

    def _classify(
        self, metrics: dict[str, float]
    ) -> tuple[dict[str, str], list[str]]:
        thresholds = self._thresholds
        checks: dict[str, str] = {}
        reasons: list[str] = []

        resolution_failures: list[str] = []
        if metrics["short_side_px"] < thresholds.min_short_side_px:
            resolution_failures.append(
                f"图像短边低于 {thresholds.min_short_side_px} px"
            )
        if metrics["total_pixels"] < thresholds.min_total_pixels:
            resolution_failures.append(
                f"图像总像素低于 {thresholds.min_total_pixels}"
            )
        checks["resolution"] = "fail" if resolution_failures else "pass"
        reasons.extend(resolution_failures)

        exposure_status, exposure_reason = _classify_exposure(
            metrics["mean_luminance"], thresholds
        )
        checks["exposure"] = exposure_status
        if exposure_reason:
            reasons.append(exposure_reason)

        dark_status, dark_reason = _classify_clip_ratio(
            metrics["dark_clip_ratio"],
            warn_ratio=thresholds.clip_warn_ratio,
            fail_ratio=thresholds.clip_fail_ratio,
            label="暗部裁剪比例",
        )
        checks["dark_clipping"] = dark_status
        if dark_reason:
            reasons.append(dark_reason)

        bright_status, bright_reason = _classify_clip_ratio(
            metrics["bright_clip_ratio"],
            warn_ratio=thresholds.clip_warn_ratio,
            fail_ratio=thresholds.clip_fail_ratio,
            label="亮部裁剪比例",
        )
        checks["bright_clipping"] = bright_status
        if bright_reason:
            reasons.append(bright_reason)

        sharpness_status, sharpness_reason = _classify_sharpness(
            metrics["sharpness_rms"], thresholds
        )
        checks["sharpness"] = sharpness_status
        if sharpness_reason:
            reasons.append(sharpness_reason)

        return checks, reasons


def _threshold_payload(
    thresholds: QualityThresholds,
) -> dict[str, dict[str, float | int]]:
    return {
        "resolution": {
            "min_short_side_px": thresholds.min_short_side_px,
            "min_total_pixels": thresholds.min_total_pixels,
        },
        "exposure": {
            "fail_low": thresholds.exposure_fail_low,
            "warn_low": thresholds.exposure_warn_low,
            "warn_high": thresholds.exposure_warn_high,
            "fail_high": thresholds.exposure_fail_high,
        },
        "dark_clipping": {
            "pixel_max": thresholds.dark_pixel_max,
            "warn_ratio": thresholds.clip_warn_ratio,
            "fail_ratio": thresholds.clip_fail_ratio,
        },
        "bright_clipping": {
            "pixel_min": thresholds.bright_pixel_min,
            "warn_ratio": thresholds.clip_warn_ratio,
            "fail_ratio": thresholds.clip_fail_ratio,
        },
        "sharpness": {
            "fail_below": thresholds.sharpness_fail_below,
            "warn_below": thresholds.sharpness_warn_below,
        },
    }


def _classify_exposure(
    mean_luminance: float, thresholds: QualityThresholds
) -> tuple[str, str | None]:
    if mean_luminance < thresholds.exposure_fail_low:
        return "fail", f"平均亮度低于 {_format_number(thresholds.exposure_fail_low)}"
    if mean_luminance > thresholds.exposure_fail_high:
        return "fail", f"平均亮度高于 {_format_number(thresholds.exposure_fail_high)}"
    if mean_luminance < thresholds.exposure_warn_low:
        return "warn", f"平均亮度低于 {_format_number(thresholds.exposure_warn_low)}"
    if mean_luminance > thresholds.exposure_warn_high:
        return "warn", f"平均亮度高于 {_format_number(thresholds.exposure_warn_high)}"
    return "pass", None


def _classify_clip_ratio(
    ratio: float, *, warn_ratio: float, fail_ratio: float, label: str
) -> tuple[str, str | None]:
    if ratio >= fail_ratio:
        return "fail", f"{label}不低于 {fail_ratio:.2f}"
    if ratio >= warn_ratio:
        return "warn", f"{label}不低于 {warn_ratio:.2f}"
    return "pass", None


def _classify_sharpness(
    sharpness_rms: float, thresholds: QualityThresholds
) -> tuple[str, str | None]:
    if sharpness_rms < thresholds.sharpness_fail_below:
        return "fail", f"清晰度低于 {_format_number(thresholds.sharpness_fail_below)}"
    if sharpness_rms < thresholds.sharpness_warn_below:
        return "warn", f"清晰度低于 {_format_number(thresholds.sharpness_warn_below)}"
    return "pass", None


def _overall_status(statuses: object) -> str:
    status_set = set(statuses)
    if "fail" in status_set:
        return "fail"
    if "warn" in status_set:
        return "warn"
    return "pass"


def _format_number(value: float | int) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)
