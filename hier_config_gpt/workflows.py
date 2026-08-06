import logging
from typing import TYPE_CHECKING

from hier_config import HConfig, WorkflowRemediation

from .exceptions import GPTClientInitializationError, RemediationError
from .models import GPTRemediationContext, GPTRemediationRule

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator

    from .clients import GPTClient

logger = logging.getLogger(__name__)


class GPTWorkflowRemediation(WorkflowRemediation):
    """Extends WorkflowRemediation to include GPT-based remediation functionality."""

    def __init__(
        self,
        running_config: HConfig,
        generated_config: HConfig,
        plugins: "Iterable[Callable[[HConfig], None]]" = (),
    ) -> None:
        super().__init__(running_config, generated_config, plugins)
        self.gpt_rules: list[GPTRemediationRule] = []
        self._gpt_remediation_config: HConfig | None = None
        self._gpt_client: GPTClient | None = None

    def set_gpt_client(self, gpt_client: "GPTClient") -> None:
        """Set GPT client for remediation planning."""
        self._gpt_client = gpt_client

    def clear_gpt_rules(self) -> None:
        """Clear all GPT rules from the workflow."""
        self.gpt_rules.clear()

    def add_gpt_rule(self, rule: GPTRemediationRule) -> None:
        """Add a GPT rule to the workflow.

        Args:
            rule: The GPTRemediationRule to add to the workflow.

        """
        self.gpt_rules.append(rule)

    def gpt_remediation_config(self) -> HConfig:
        """Generate GPT-based remediation plan.

        Returns:
            HConfig: The configuration created by an GPT to remediate the device.

        """
        if not self._gpt_client:
            msg = "No GPT client is initialized."
            raise GPTClientInitializationError(msg)

        try:
            remediation_config = self._generate_remediation_config(self._gpt_client)
        except RemediationError:
            raise
        except Exception as exc:
            msg = f"Failed to generate remediation plan: {exc}"
            raise RemediationError(msg) from exc

        self._gpt_remediation_config = remediation_config
        return remediation_config

    def _generate_remediation_config(self, gpt_client: "GPTClient") -> HConfig:
        """Build the remediation config from GPT-generated plans."""
        remediation_plans: list[str] = []

        for context in self._build_remediation_context():
            prompt = self._build_gpt_prompt(context)
            response = gpt_client.generate_plan(prompt)
            remediation_plans.append(self._format_plan(response.plan))
            logger.debug("GPT remediation metadata: %s", response.metadata)

        combined_plan = "\n".join(remediation_plans)
        if not combined_plan.strip():
            msg = "GPT remediation plan is empty."
            raise RemediationError(msg)

        return HConfig.from_lines(self.running_config.driver, combined_plan)

    @staticmethod
    def _format_plan(plan: "Iterable[str]") -> str:
        """Validate and format plan output from GPT client into text."""
        commands = [
            str(command).strip("\n") for command in plan if str(command).strip()
        ]
        if not commands:
            msg = "GPT remediation plan is empty."
            raise RemediationError(msg)

        for command in commands:
            if "\t" in command:
                msg = "Commands must not contain tab characters."
                raise RemediationError(msg)

        return "\n".join(commands)

    def _build_remediation_context(self) -> "Iterator[GPTRemediationContext]":
        """Generate context for GPT Prompt."""
        if not self.gpt_rules:
            msg = "No GPT remediation rules loaded."
            raise RemediationError(msg)

        for rule in self.gpt_rules:
            running_config = self.running_config.get_children_deep(rule.lineage)
            generated_config = self.generated_config.get_children_deep(rule.lineage)

            yield GPTRemediationContext(
                running_config="\n".join(str(line) for line in running_config),
                generated_config="\n".join(str(line) for line in generated_config),
                description=rule.description,
                example=rule.example,
            )

    @staticmethod
    def _build_gpt_prompt(context: GPTRemediationContext) -> str:
        """Build GPT prompt from context."""
        return f"""
### Network Configuration Remediation Plan Generation
**Objective**
Generate a network configuration remediation plan as a JSON object with a **plan** array of string commands to be executed *sequentially* for remediation.

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
- **Respond ONLY with JSON**, no additional narrative. The root object must include a key named "plan" whose value is an array of strings.
- **Follow the format and structure** demonstrated in the Example context above.
- **Maintain the command hierarchy** by using indentation (multiples of four spaces) to denote child commands under parent commands.
- **Each command should be a string** in the list.
- **Do not include** rollback or validation steps. The list should only contain the commands required to implement the generated configuration.

**Example output format:**
{{
    "plan": [
        "command1",
        "parent_command",
        "    child_command1",
        "    child_command2",
        "command2"
    ]
}}
    """
