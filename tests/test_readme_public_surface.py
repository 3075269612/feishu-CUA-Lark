from pathlib import Path


def test_readme_uses_generic_public_commands() -> None:
    readme = Path("README.md").read_text(encoding="utf-8").lower()

    assert ".conda310" not in readme
    assert "phase 8" not in readme
    assert "phase8" not in readme
    assert "20260506" not in readme
    assert "d:\\" not in readme
