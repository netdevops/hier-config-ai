"""Exceptions raised by hier-config-ai."""


class HierConfigAIError(Exception):
    """Base class for every error raised by this package."""


class AIClientInitializationError(HierConfigAIError):
    """Raised when no model or agent is set on the workflow."""


class RemediationError(HierConfigAIError):
    """Raised when a remediation plan cannot be produced or is unusable."""


class ConsensusError(RemediationError):
    """Raised when providers fail, or when quorum finds no majority."""
