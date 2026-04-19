"""Typed domain errors for predictable exit-code mapping."""


class GitsemError(Exception):
    """Base class for all gitsem domain errors."""

    exit_code: int = 99
    token: str = "error"

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        # Optional one-line remedy shown to both humans and agents.
        self.hint: str | None = hint


class InvalidVersionError(GitsemError):
    """Raised when the version string is not a valid semver form."""

    exit_code = 1
    token = "invalid-version"


class UnhealthyRepositoryError(GitsemError):
    """Raised when the Git repository is not in a state safe for tag mutation."""

    exit_code = 2
    token = "unhealthy-repo"


class StyleMismatchError(GitsemError):
    """Raised when the requested prefix style differs from the repository's established style."""

    exit_code = 3
    token = "style-mismatch"


class TagConflictError(GitsemError):
    """Raised when a local tag conflict prevents safe operation."""

    exit_code = 4
    token = "tag-conflict"


class RemoteConflictError(GitsemError):
    """Raised when a remote tag conflict prevents safe operation."""

    exit_code = 5
    token = "remote-conflict"


class RemotePermissionError(GitsemError):
    """Raised when remote operations fail due to access or server-side policy."""

    exit_code = 6
    token = "remote-permission"


class GitExecutionError(GitsemError):
    """Raised when a Git subprocess call fails for an unexpected reason."""

    exit_code = 7
    token = "git-execution"
