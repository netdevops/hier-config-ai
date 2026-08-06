"""Tests for the configurable prompt template."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from hier_config_gpt.models import GPTRemediationContext
from hier_config_gpt.prompt_template import PromptTemplate
from tests.conftest import build_gpt_remediation_example

if TYPE_CHECKING:
    from pathlib import Path


def _context() -> GPTRemediationContext:
    """Build a sample remediation context."""
    return GPTRemediationContext(
        description="Enable interface and add IP address",
        running_config="interface GigabitEthernet0/1\n shutdown",
        generated_config="interface GigabitEthernet0/1\n no shutdown",
        example=build_gpt_remediation_example(),
    )


def test_default_template_build() -> None:
    template = PromptTemplate()

    prompt = template.build(_context())

    assert "Network Configuration Remediation Plan Generation" in prompt
    assert "interface GigabitEthernet0/1" in prompt
    assert "Enable interface and add IP address" in prompt
    assert "ip address 192.168.1.1 255.255.255.0" in prompt


def test_custom_template_build() -> None:
    template = PromptTemplate(
        template=(
            "{running_config}|{generated_config}|{description}"
            "|{example_running_config}|{example_remediation_config}"
        )
    )

    prompt = template.build(_context())

    assert prompt.startswith("interface GigabitEthernet0/1\n shutdown|")
    assert "Enable interface and add IP address" in prompt


def test_template_missing_placeholder() -> None:
    with pytest.raises(
        ValueError, match=r"Template must include placeholder: \{running_config\}"
    ):
        PromptTemplate(template="no placeholders here")


def test_template_from_file(tmp_path: Path) -> None:
    template_file = tmp_path / "template.txt"
    template_file.write_text(
        "{running_config} {generated_config} {description} "
        "{example_running_config} {example_remediation_config}",
        encoding="utf-8",
    )

    template = PromptTemplate.from_file(template_file)

    assert template.build(_context()).startswith("interface GigabitEthernet0/1")
