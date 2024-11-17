from typing import Optional, Iterator

from hier_config import get_hconfig_fast_load
from hier_config.root import HConfig

from .clients import GPTClient
from .exceptions import GPTClientInitializationError, RemediationError
from .models import GPTRemediationContext


class GPTWorkflowRemediation(WorkflowRemediation):
    """Extends WorkflowRemediation to include GPT-based remediation functionality."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._gpt_remediation_config: Optional[HConfig] = None
        self._gpt_client: Optional[GPTClient] = None

    def set_gpt_client(self, gpt_client: GPTClient) -> None:
        """Set GPT client for remediation planning."""
        self._gpt_client = gpt_client

    def gpt_remediation_config(self) -> HConfig:
        """Generate GPT-based remediation plan.

        Returns:
            HConfig: The configuration created by an GPT to remediate the device.
        """
        if not self._gpt_client:
            raise GPTClientInitializationError("No GPT client is initialized.")

        for context in self._build_remediation_context():
            try:
                prompt = self._build_gpt_prompt(context)
                response = self._gpt_client.generate_plan(prompt)
                self._gpt_remediation_config = get_hconfig_fast_load(
                    self.running_config.driver, response
                )
            except Exception as e:
                raise RemediationError(
                    f"Failed to generate remediation plan: {e}"
                ) from e

        return self._gpt_remediation_config or HConfig(self.running_config.driver)

    def _build_remediation_context(self) -> Iterator[GPTRemediationContext]:
        """Generate context for GPT Prompt."""
        rules = self.running_config.driver.gpt_remediation_rules

        if not rules:
            raise RemediationError("No GPT remediation rules loaded.")

        for rule in rules:
            running_config = self.running_config.get_children_deep(rule.lineage)
            generated_config = self.generated_config.get_children_deep(rule.lineage)

            yield GPTRemediationContext(
                running_config="\n".join([str(line) for line in running_config]),
                generated_config="\n".join([str(line) for line in generated_config]),
                description=rule.description,
                example=rule.example,
            )

    @staticmethod
    def _build_gpt_prompt(context: GPTRemediationContext) -> str:
        """Build GPT prompt from context."""
        return f"""
### Network Configuration Remediation Plan Generation
**Objective**
Generate a network configuration remediation plan as a Python list of commands to be executed *sequentially* for remediation.

**Current Configuration:**
```
{context.running_config}
```

**Desired Generated Configuration:**
```
{context.generated_config}
```

**Remediation Rules:**
{context.description}

Use the following example as a guide for the format and structure of the commands:

**Example:**
*running config:*
```
{context.example.running_config}
```

*remediation config:*
```
{context.example.remediation_config}
```

**Instructions:**
- **Generate a Python list** of commands for the remediation plan.
- *Follow the format and structure** demonstrated in the Example context above.
- **Maintain the command hierarchy** by using indentation to denote child commands under parent commands.
- **Each command should be a string** in the list.
- **Do not include** rollback or validation steps. The list should only contain the commands required to implement the generated configuration.

**Example output format:**
```python
[
    "command1",
    "parent_command",
    "    child_command1",
    "    child_command2",
    "command2"
]
```
    """
