"""Configurable prompt templates for LLM remediation plan generation."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import AIRemediationContext

_REQUIRED_PLACEHOLDERS = (
    "{running_config}",
    "{generated_config}",
    "{description}",
    "{example_running_config}",
    "{example_remediation_config}",
)


class PromptTemplate:
    """Configurable prompt template for generating remediation plans.

    Allows customization of the prompt structure while maintaining
    the necessary context for plan generation.
    """

    # Carries the task and its context only. The output shape is enforced by
    # the agent's structured output, and the platform's syntax comes from the
    # driver, so restating either here would contradict the system prompt --
    # the previous version told the model to reply with raw JSON, which stops
    # it calling the output tool and burns retries.
    DEFAULT_TEMPLATE = """### Network configuration remediation

**Current configuration**
```
{running_config}
```

**Intended configuration**
```
{generated_config}
```

**What to achieve**
{description}

**Example**
*running config:*
```
{example_running_config}
```

*remediation:*
```
{example_remediation_config}
```

**Instructions**
- Return only the commands that turn the current configuration into the
  intended one.
- Follow the structure shown in the example above.
- Do not include rollback or validation steps.
"""

    def __init__(self, template: str | None = None) -> None:
        """Initialize the prompt template.

        Args:
            template: Custom template string (uses DEFAULT_TEMPLATE if None).
                     Must include placeholders: {running_config}, {generated_config},
                     {description}, {example_running_config}, {example_remediation_config}.

        """
        self.template = template or self.DEFAULT_TEMPLATE

        # Validate template has required placeholders
        for placeholder in _REQUIRED_PLACEHOLDERS:
            if placeholder not in self.template:
                msg = (
                    f"Template must include placeholder: {placeholder}. "
                    "Missing placeholders prevent proper context injection."
                )
                raise ValueError(msg)

    def build(self, context: AIRemediationContext) -> str:
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
    def from_file(cls, file_path: str | Path) -> PromptTemplate:
        """Load a prompt template from a file.

        Args:
            file_path: Path to the template file.

        Returns:
            A PromptTemplate instance with the loaded template.

        """
        template = Path(file_path).read_text(encoding="utf-8")
        return cls(template=template)
