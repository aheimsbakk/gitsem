"""gitsem — Docker-like floating semantic-version tags for Git repositories."""

try:
    from importlib.metadata import PackageNotFoundError, version

    __version__ = version("gitsem")
except Exception:  # noqa: BLE001
    # Package not yet installed (e.g. running directly from source).
    __version__ = "0.0.0+dev"
