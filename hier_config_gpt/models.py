from pydantic import BaseModel

from hier_config import MatchRule


class GPTRemediationExample(BaseModel):
    running_config: str
    remediation_config: str


class GPTRemediationRule(BaseModel):
    description: str
    lineage: tuple[MatchRule, ...]
    example: GPTRemediationExample


class GPTRemediationContext(BaseModel):
    description: str
    running_config: str
    generated_config: str
    example: GPTRemediationExample
