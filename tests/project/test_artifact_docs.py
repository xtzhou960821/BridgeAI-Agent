from pathlib import Path


def test_artifact_workflow_is_documented():
    required = {
        "README.md": ["POST /api/v1/artifacts", "BRIDGEAI_ARTIFACT_STORAGE_ROOT"],
        "docs/development/v0.2-local-runbook.md": [
            "0005_artifacts.sql",
            "ARTIFACT_INTEGRITY_MISMATCH",
            "quality_status",
        ],
    }

    for filename, markers in required.items():
        contents = Path(filename).read_text(encoding="utf-8")
        for marker in markers:
            assert marker in contents, f"{filename} is missing {marker!r}"
