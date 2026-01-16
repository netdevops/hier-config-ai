"""hier-config-gpt: Hierarchical Configuration with GPT Integration.

An enhanced hierarchical configuration library that integrates GPT/LLM
capabilities for advanced network configuration analysis and remediation.
"""

__version__ = "0.1.0"

from .workflows import GPTWorkflowRemediation
from .prompt_template import PromptTemplate
from .models import (
    GPTRemediationContext,
    GPTRemediationExample,
    GPTRemediationRule,
)

__all__ = (
    "GPTRemediationContext",
    "GPTRemediationExample",
    "GPTRemediationRule",
    "GPTWorkflowRemediation",
    "PromptTemplate",
)
