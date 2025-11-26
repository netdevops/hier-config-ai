from typing import Optional, Iterator, Iterable

from hier_config import get_hconfig_fast_load, WorkflowRemediation
from hier_config.root import HConfig

from .clients import GPTClient
from .exceptions import GPTClientInitializationError, RemediationError
from .models import GPTRemediationContext, GPTRemediationRule


class GPTWorkflowRemediation(WorkflowRemediation):
    """Extends WorkflowRemediation to include GPT-based remediation functionality."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gpt_rules: list[GPTRemediationRule] = []
        self._gpt_remediation_config: Optional[HConfig] = None
        self._gpt_client: Optional[GPTClient] = None

    def set_gpt_client(self, gpt_client: GPTClient) -> None:
        """Set GPT client for remediation planning."""
        self._gpt_client = gpt_client

    def clear_gpt_rules(self) -> list[GPTRemediationRule]:
        """Clear GPT rules."""
        return self.gpt_rules.clear()

    def add_gpt_rule(self, rule: GPTRemediationRule) -> list[GPTRemediationRule]:
        """Add GPT rule."""
        return self.gpt_rules.append(rule)

    def gpt_remediation_config(self) -> HConfig:
        """Generate GPT-based remediation plan.

        Returns:
            HConfig: The configuration created by an GPT to remediate the device.
        """
        if not self._gpt_client:
            raise GPTClientInitializationError("No GPT client is initialized.")

        remediation_plans: list[str] = []

        try:
            for context in self._build_remediation_context():
                prompt = self._build_gpt_prompt(context)
                response = self._gpt_client.generate_plan(prompt)
                remediation_plans.append(self._format_plan(response.plan))

            combined_plan = "\n".join(remediation_plans)
            if not combined_plan.strip():
                raise RemediationError("GPT remediation plan is empty.")

            self._gpt_remediation_config = get_hconfig_fast_load(
                self.running_config.driver, combined_plan
            )
        except RemediationError:
            raise
        except Exception as e:
            raise RemediationError(
                f"Failed to generate remediation plan: {e}"
            ) from e

        return self._gpt_remediation_config or HConfig(self.running_config.driver)

    @staticmethod
    def _format_plan(plan: Iterable[str]) -> str:
        """Validate and format plan output from GPT client into text."""

        if not isinstance(plan, Iterable) or isinstance(plan, (str, bytes)):
            raise RemediationError("GPT remediation plan must be a list of commands.")

        commands = [str(command).strip("\n") for command in plan if str(command).strip()]
        if not commands:
            raise RemediationError("GPT remediation plan is empty.")

        return "\n".join(commands)

    def _build_remediation_context(self) -> Iterator[GPTRemediationContext]:
        """Generate context for GPT Prompt."""

        if not self.gpt_rules:
            raise RemediationError("No GPT remediation rules loaded.")

        for rule in self.gpt_rules:
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
