from __future__ import annotations

import math
from dataclasses import replace
from io import BytesIO

from PIL import Image, ImageChops, ImageFilter, ImageStat

from backend.app.services.image_quality import (
    ImageQualityAnalyzer,
    QualityThresholds,
)


def checkerboard_jpeg(*, size: tuple[int, int]) -> bytes:
    image = Image.new("L", size)
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            pixels[x, y] = 0 if (x // 16 + y // 16) % 2 == 0 else 255

    content = BytesIO()
    image.save(content, format="JPEG", quality=100, subsampling=0)
    return content.getvalue()


def grayscale_png(*, size: tuple[int, int], luminance: int) -> bytes:
    content = BytesIO()
    Image.new("L", size, color=luminance).save(content, format="PNG")
    return content.getvalue()


def blurred_checkerboard_png(*, size: tuple[int, int]) -> bytes:
    image = Image.open(BytesIO(checkerboard_jpeg(size=size)))
    content = BytesIO()
    image.filter(ImageFilter.GaussianBlur(radius=10)).save(content, format="PNG")
    return content.getvalue()


def neutral_checkerboard_png(*, size: tuple[int, int]) -> bytes:
    image = Image.new("L", size)
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            pixels[x, y] = 96 if (x // 16 + y // 16) % 2 == 0 else 160
    content = BytesIO()
    image.save(content, format="PNG")
    return content.getvalue()


def test_analyzer_returns_explainable_metrics_and_thresholds():
    result = ImageQualityAnalyzer().analyze(
        BytesIO(checkerboard_jpeg(size=(1280, 800))),
        artifact_id="art_quality",
    )
    payload = result.as_payload()

    assert payload["artifact_id"] == "art_quality"
    assert payload["analyzer_version"] == "0.1.0"
    assert payload["checks"]["resolution"] == "pass"
    assert payload["thresholds"]["resolution"]["min_short_side_px"] == 720
    assert payload["quality_status"] in {"pass", "warn"}
    assert all(math.isfinite(value) for value in payload["metrics"].values())
    assert payload["metrics"]["short_side_px"] == 800.0
    assert isinstance(payload["reasons"], list)


def test_analyzer_classifies_low_resolution_as_failure_with_chinese_reason():
    payload = ImageQualityAnalyzer().analyze(
        BytesIO(checkerboard_jpeg(size=(719, 1400))), artifact_id="art_low_resolution"
    ).as_payload()

    assert payload["checks"]["resolution"] == "fail"
    assert payload["quality_status"] == "fail"
    assert "图像短边低于 720 px" in payload["reasons"]


def test_analyzer_keeps_exact_resolution_boundaries_as_pass():
    payload = ImageQualityAnalyzer().analyze(
        BytesIO(neutral_checkerboard_png(size=(1000, 1000))),
        artifact_id="art_resolution_boundary",
    ).as_payload()

    assert payload["metrics"]["short_side_px"] == 1000.0
    assert payload["metrics"]["total_pixels"] == 1_000_000.0
    assert payload["checks"]["resolution"] == "pass"


def test_analyzer_classifies_dark_and_bright_exposure_with_strict_boundaries():
    analyzer = ImageQualityAnalyzer()

    dark = analyzer.analyze(
        BytesIO(grayscale_png(size=(1280, 800), luminance=19)), artifact_id="art_dark"
    ).as_payload()
    dark_boundary = analyzer.analyze(
        BytesIO(grayscale_png(size=(1280, 800), luminance=20)), artifact_id="art_dark_boundary"
    ).as_payload()
    bright = analyzer.analyze(
        BytesIO(grayscale_png(size=(1280, 800), luminance=236)), artifact_id="art_bright"
    ).as_payload()
    bright_boundary = analyzer.analyze(
        BytesIO(grayscale_png(size=(1280, 800), luminance=235)), artifact_id="art_bright_boundary"
    ).as_payload()

    assert dark["checks"]["exposure"] == "fail"
    assert dark_boundary["checks"]["exposure"] == "warn"
    assert bright["checks"]["exposure"] == "fail"
    assert bright_boundary["checks"]["exposure"] == "warn"
    assert "平均亮度低于 20" in dark["reasons"]
    assert "平均亮度高于 235" in bright["reasons"]


def test_analyzer_classifies_clip_ratios_at_inclusive_boundaries():
    thresholds = QualityThresholds(
        min_short_side_px=1,
        min_total_pixels=1,
        exposure_fail_low=0.0,
        exposure_warn_low=0.0,
        exposure_warn_high=255.0,
        exposure_fail_high=255.0,
        sharpness_fail_below=0.0,
        sharpness_warn_below=0.0,
    )
    analyzer = ImageQualityAnalyzer(thresholds)
    half_dark = Image.new("L", (100, 100), color=128)
    for x in range(50):
        for y in range(100):
            half_dark.putpixel((x, y), 10)
    content = BytesIO()
    half_dark.save(content, format="PNG")

    warn = analyzer.analyze(BytesIO(content.getvalue()), artifact_id="art_clip_warn").as_payload()
    fail_thresholds = replace(thresholds, clip_warn_ratio=0.1, clip_fail_ratio=0.5)
    fail = ImageQualityAnalyzer(fail_thresholds).analyze(
        BytesIO(content.getvalue()), artifact_id="art_clip_fail"
    ).as_payload()

    assert warn["metrics"]["dark_clip_ratio"] == 0.5
    assert warn["checks"]["dark_clipping"] == "warn"
    assert fail["checks"]["dark_clipping"] == "fail"
    assert warn["checks"]["bright_clipping"] == "pass"


def test_analyzer_classifies_bright_clip_ratio_at_inclusive_boundary():
    thresholds = QualityThresholds(
        min_short_side_px=1,
        min_total_pixels=1,
        exposure_fail_low=0.0,
        exposure_warn_low=0.0,
        exposure_warn_high=255.0,
        exposure_fail_high=255.0,
        sharpness_fail_below=0.0,
        sharpness_warn_below=0.0,
    )
    image = Image.new("L", (100, 100), color=128)
    for x in range(50):
        for y in range(100):
            image.putpixel((x, y), 245)
    content = BytesIO()
    image.save(content, format="PNG")

    payload = ImageQualityAnalyzer(thresholds).analyze(
        BytesIO(content.getvalue()), artifact_id="art_bright_clip"
    ).as_payload()

    assert payload["metrics"]["bright_clip_ratio"] == 0.5
    assert payload["checks"]["bright_clipping"] == "warn"
    assert "亮部裁剪比例不低于 0.50" in payload["reasons"]


def test_analyzer_classifies_blurred_image_and_overall_precedence():
    analyzer = ImageQualityAnalyzer()
    blurred = analyzer.analyze(
        BytesIO(blurred_checkerboard_png(size=(1280, 800))), artifact_id="art_blurred"
    ).as_payload()
    dark_and_low_resolution = analyzer.analyze(
        BytesIO(grayscale_png(size=(700, 700), luminance=10)), artifact_id="art_multiple_failures"
    ).as_payload()

    assert blurred["checks"] == {
        "resolution": "pass",
        "exposure": "pass",
        "dark_clipping": "pass",
        "bright_clipping": "pass",
        "sharpness": "fail",
    }
    assert blurred["quality_status"] == "fail"
    assert dark_and_low_resolution["quality_status"] == "fail"
    assert dark_and_low_resolution["reasons"] == [
        "图像短边低于 720 px",
        "图像总像素低于 1000000",
        "平均亮度低于 20",
        "暗部裁剪比例不低于 0.80",
        "清晰度低于 2",
    ]


def test_analyzer_classifies_neutral_sharp_image_as_pass():
    payload = ImageQualityAnalyzer().analyze(
        BytesIO(neutral_checkerboard_png(size=(1280, 800))), artifact_id="art_neutral"
    ).as_payload()

    assert set(payload["checks"].values()) == {"pass"}
    assert payload["quality_status"] == "pass"
    assert payload["reasons"] == []


def test_analyzer_uses_unrounded_sharpness_for_strict_boundary_classification():
    content = neutral_checkerboard_png(size=(1280, 800))
    gray = Image.open(BytesIO(content)).convert("L")
    raw_sharpness = float(
        ImageStat.Stat(
            ImageChops.difference(gray, gray.filter(ImageFilter.GaussianBlur(radius=1)))
        ).rms[0]
    )
    thresholds = QualityThresholds(
        sharpness_fail_below=0.0,
        sharpness_warn_below=raw_sharpness,
    )

    payload = ImageQualityAnalyzer(thresholds).analyze(
        BytesIO(content), artifact_id="art_sharpness_boundary"
    ).as_payload()

    assert payload["metrics"]["sharpness_rms"] == round(raw_sharpness, 4)
    assert payload["checks"]["sharpness"] == "pass"
