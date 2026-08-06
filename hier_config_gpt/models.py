from hier_config.models import MatchRule
from pydantic import BaseModel


class GPTRemediationExample(BaseModel):
    """Example running/remediation config pair used to guide the LLM."""

    running_config: str
    remediation_config: str


class GPTRemediationRule(BaseModel):
    """Rule describing a config section to remediate with GPT assistance."""

    description: str
    lineage: tuple[MatchRule, ...]
    example: GPTRemediationExample


class GPTRemediationContext(BaseModel):
    """Context passed to the LLM when building a remediation prompt."""

    description: str
    running_config: str
    generated_config: str
    example: GPTRemediationExample
