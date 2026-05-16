"""Custom exception hierarchy for ContractHub.

This module defines specific exceptions to support strict error handling
in automated GitOps pipelines and programmatic API usage.
"""


class ContractHubError(Exception):
    """The base exception for ContractHub."""

    pass


class ValidationError(ContractHubError):
    """Raised when a contract fails governance or structure validation."""

    pass


class MergeConflictError(ContractHubError):
    """Raised by the merge engine when business and technical metadata fatally conflict."""

    pass


class LifecycleError(ContractHubError):
    """Raised for invalid promotion or deployment actions."""

    pass


class StorageError(ContractHubError):
    """Wraps Azure ADLS / file system / Unity Catalog connection errors."""

    pass
