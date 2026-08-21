"""hier-config-ai: hierarchical network configuration remediation with LLMs.

Extends hier-config with model-generated remediation for the config sections
that deterministic diffing cannot resolve on its own. Plans are checked back
against hier-config before they are returned, so the model's output is verified
rather than trusted.
"""

__version__ = "0.2.0"

from .agent import build_agent
from .cache import ResponseCache
from .consensus import consensus_plan
from .deps import RemediationDeps, Retriever
from .exceptions import (
    AIClientInitializationError,
    ConsensusError,
    HierConfigAIError,
    RemediationError,
)
from .model_wrappers import CachedModel, RateLimitedModel
from .models import (
    AIPlanResponse,
    AIRemediationContext,
    AIRemediationExample,
    AIRemediationRule,
)
from .prompt_template import PromptTemplate
from .rate_limiter import RateLimiter
from .workflows import AIWorkflowRemediation, scoped_config

__all__ = (
    "AIClientInitializationError",
    "AIPlanResponse",
    "AIRemediationContext",
    "AIRemediationExample",
    "AIRemediationRule",
    "AIWorkflowRemediation",
    "CachedModel",
    "ConsensusError",
    "HierConfigAIError",
    "PromptTemplate",
    "RateLimitedModel",
    "RateLimiter",
    "RemediationDeps",
    "RemediationError",
    "ResponseCache",
    "Retriever",
    "__version__",
    "build_agent",
    "consensus_plan",
    "scoped_config",
)
