"""Typed domain errors for predictable exit-code mapping."""


class GitsemError(Exception):
    """Base class for all gitsem domain errors."""

    exit_code: int = 99


class InvalidVersionError(GitsemError):
    """Raised when the version string is not a valid semver form."""

    exit_code = 1


class UnhealthyRepositoryError(GitsemError):
    """Raised when the Git repository is not in a state safe for tag mutation."""

    exit_code = 2


class StyleMismatchError(GitsemError):
    """Raised when the requested prefix style differs from the repository's established style."""

    exit_code = 3


class TagConflictError(GitsemError):
    """Raised when a local tag conflict prevents safe operation."""

    exit_code = 4


class RemoteConflictError(GitsemError):
    """Raised when a remote tag conflict prevents safe operation."""

    exit_code = 5


class RemotePermissionError(GitsemError):
    """Raised when remote operations fail due to access or server-side policy."""

    exit_code = 6


class GitExecutionError(GitsemError):
    """Raised when a Git subprocess call fails for an unexpected reason."""

    exit_code = 7
