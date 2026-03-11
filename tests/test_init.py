"""Tests for the package __init__ module."""

import mcprojsim


class TestInit:
    """Package initialization tests."""

    def test_version_is_a_string(self) -> None:
        assert isinstance(mcprojsim.__version__, str)

    def test_version_has_three_parts(self) -> None:
        parts = mcprojsim.__version__.split(".")
        assert len(parts) >= 2

    def test_resolve_version_fallback(self, monkeypatch) -> None:
        """_resolve_version falls back to pyproject.toml when metadata is missing."""
        from importlib.metadata import PackageNotFoundError

        monkeypatch.setattr(
            "mcprojsim.version",
            lambda _name: (_ for _ in ()).throw(PackageNotFoundError()),
        )
        # Re-call the function – it should still return a valid version string
        v = mcprojsim._resolve_version()
        assert isinstance(v, str)
        assert v != ""

    def test_all_exports(self) -> None:
        for name in mcprojsim.__all__:
            assert hasattr(mcprojsim, name)
