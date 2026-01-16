import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from hier_config import HConfig
from hier_config.models import MatchRule
from hier_config.platforms import driver_base

from hier_config_gpt.models import GPTRemediationExample, GPTRemediationRule
from hier_config_gpt.workflows import GPTWorkflowRemediation

# Ensure the repository root is importable when running tests directly
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def mock_openai_response():
    """Create a mock OpenAI chat completion response"""
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content='Here\'s a plan: ["command1", "command2", "command3"]'
            )
        )
    ]
    return mock_response


@pytest.fixture
def mock_anthropic_response():
    """Create a mock Anthropic message response"""
    mock_content = MagicMock()
    mock_content.text = 'Here\'s a plan: ["command1", "command2", "command3"]'

    mock_response = MagicMock()
    mock_response.content = [mock_content]
    return mock_response


@pytest.fixture
def mock_ollama_response():
    """Create a mock Ollama chat response"""
    return {
        "model": "llama3",
        "message": {
            "role": "assistant",
            "content": 'Here\'s a plan: ["command1", "command2", "command3"]',
        },
        "created_at": "2023-03-01T12:00:00.000Z",
    }


@pytest.fixture
def sample_prompt():
    """Sample prompt for testing"""
    return "Generate a remediation plan for this configuration."


@pytest.fixture
def sample_api_key():
    """Sample API key for testing"""
    return "test-api-key-12345"


# Workflow test fixtures
@pytest.fixture
def mock_driver():
    """Create a mock driver for HConfig."""
    driver = MagicMock(spec=driver_base.HConfigDriverBase)

    # Set up rules for the driver
    driver.rules = MagicMock()
    driver.rules.ordering = []

    return driver


@pytest.fixture
def running_config(mock_driver):
    """Create an actual running HConfig instance."""
    running_config = HConfig(mock_driver)

    # Add some basic configuration
    running_config.add_child("hostname ROUTER1")
    interface_g00 = running_config.add_child("interface GigabitEthernet0/0")
    interface_g00.add_child("ip address 10.0.0.1 255.255.255.0")
    interface_g00.add_child("no shutdown")

    interface_g01 = running_config.add_child("interface GigabitEthernet0/1")
    interface_g01.add_child("shutdown")

    return running_config


@pytest.fixture
def generated_config(mock_driver):
    """Create an actual generated HConfig instance."""
    generated_config = HConfig(mock_driver)

    # Add configuration including changes
    generated_config.add_child("hostname ROUTER1")
    interface_g00 = generated_config.add_child("interface GigabitEthernet0/0")
    interface_g00.add_child("ip address 10.0.0.1 255.255.255.0")
    interface_g00.add_child("no shutdown")

    interface_g01 = generated_config.add_child("interface GigabitEthernet0/1")
    interface_g01.add_child("ip address 10.0.1.1 255.255.255.0")
    interface_g01.add_child("no shutdown")

    return generated_config


@pytest.fixture
def gpt_remediation_example():
    """Create a sample GPT remediation example."""
    return GPTRemediationExample(
        running_config="interface GigabitEthernet0/1\n shutdown",
        remediation_config="interface GigabitEthernet0/1\n no shutdown\n ip address 192.168.1.1 255.255.255.0",
    )


@pytest.fixture
def match_rule():
    """Create a real MatchRule instance."""
    # Using equals as it's the most literal match
    return MatchRule(equals="interface GigabitEthernet0/1")


@pytest.fixture
def gpt_rule(gpt_remediation_example, match_rule):
    """Create a sample GPT remediation rule."""
    return GPTRemediationRule(
        lineage=(match_rule,),
        description="Configure IP address and enable interface",
        example=gpt_remediation_example,
    )


@pytest.fixture
def remediation_workflow(running_config, generated_config):
    """Create a GPTWorkflowRemediation instance with real HConfig objects."""
    workflow = GPTWorkflowRemediation(
        running_config=running_config,
        generated_config=generated_config,
    )

    return workflow
