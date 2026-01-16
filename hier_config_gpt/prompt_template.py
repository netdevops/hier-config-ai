"""Configurable prompt templates for LLM remediation plan generation."""

from __future__ import annotations

from typing import Optional

from .models import GPTRemediationContext


class PromptTemplate:
    """Configurable prompt template for generating remediation plans.

    Allows customization of the prompt structure while maintaining
    the necessary context for plan generation.
    """

    DEFAULT_TEMPLATE = """### Network Configuration Remediation Plan Generation
**Objective**
Generate a network configuration remediation plan as a JSON object with a **plan** array of string commands to be executed *sequentially* for remediation.

**Current Configuration:**
```
{running_config}
```

**Desired Generated Configuration:**
```
{generated_config}
```

**Remediation Rules:**
{description}

Use the following example as a guide for the format and structure of the commands:

**Example:**
*running config:*
```
{example_running_config}
```

*remediation config:*
```
{example_remediation_config}
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

    def __init__(self, template: Optional[str] = None) -> None:
        """Initialize the prompt template.

        Args:
            template: Custom template string (uses DEFAULT_TEMPLATE if None).
                     Must include placeholders: {running_config}, {generated_config},
                     {description}, {example_running_config}, {example_remediation_config}.
        """
        self.template = template or self.DEFAULT_TEMPLATE

        # Validate template has required placeholders
        required_placeholders = [
            "{running_config}",
            "{generated_config}",
            "{description}",
            "{example_running_config}",
            "{example_remediation_config}",
        ]

        for placeholder in required_placeholders:
            if placeholder not in self.template:
                raise ValueError(
                    f"Template must include placeholder: {placeholder}. "
                    f"Missing placeholders prevent proper context injection."
                )

    def build(self, context: GPTRemediationContext) -> str:
        """Build a prompt from the context using this template.

        Args:
            context: The remediation context to inject into the template.

        Returns:
            The formatted prompt string.
        """
        return self.template.format(
            running_config=context.running_config,
            generated_config=context.generated_config,
            description=context.description,
            example_running_config=context.example.running_config,
            example_remediation_config=context.example.remediation_config,
        )

    @classmethod
    def from_file(cls, file_path: str) -> PromptTemplate:
        """Load a prompt template from a file.

        Args:
            file_path: Path to the template file.

        Returns:
            A PromptTemplate instance with the loaded template.
        """
        with open(file_path, "r") as f:
            template = f.read()
        return cls(template=template)
