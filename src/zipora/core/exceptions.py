"""Domain-specific exceptions."""


class ArchiveError(Exception):
    """Base exception for archive operations."""


class UnsupportedFormatError(ArchiveError):
    """Raised when an archive format is not supported."""


class UnsafeArchiveError(ArchiveError):
    """Raised when an archive member would escape the destination path."""


class MissingOptionalDependencyError(ArchiveError):
    """Raised when a format requires an unavailable optional dependency."""


class PasswordRequiredError(ArchiveError):
    """Raised when an encrypted archive needs a password."""
