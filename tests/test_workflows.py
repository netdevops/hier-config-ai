import pytest
from unittest.mock import MagicMock, patch

from hier_config import HConfig
from hier_config_gpt.workflows import GPTWorkflowRemediation
from hier_config_gpt.models import GPTRemediationContext, GPTRemediationExample
from hier_config_gpt.exceptions import GPTClientInitializationError, RemediationError


class TestGPTWorkflowRemediation:
    def test_init(self, remediation_workflow, running_config, generated_config):
        """Test initialization of GPTWorkflowRemediation."""
        assert remediation_workflow.running_config == running_config
        assert remediation_workflow.generated_config == generated_config
        assert remediation_workflow.gpt_rules == []
        assert remediation_workflow._gpt_remediation_config is None
        assert remediation_workflow._gpt_client is None

    def test_set_gpt_client(self, remediation_workflow):
        """Test setting GPT client."""
        mock_client = MagicMock()
        remediation_workflow.set_gpt_client(mock_client)
        assert remediation_workflow._gpt_client == mock_client

    def test_add_and_clear_gpt_rules(self, remediation_workflow, gpt_rule):
        """Test adding and clearing GPT rules."""
        # Add a rule
        remediation_workflow.add_gpt_rule(gpt_rule)
        assert len(remediation_workflow.gpt_rules) == 1
        assert remediation_workflow.gpt_rules[0] == gpt_rule

        # Clear rules
        remediation_workflow.clear_gpt_rules()
        assert len(remediation_workflow.gpt_rules) == 0

    def test_build_gpt_prompt(self):
        """Test building GPT prompt from context."""
        example = GPTRemediationExample(
            running_config="interface Eth0\n shutdown",
            remediation_config="interface Eth0\n no shutdown",
        )

        context = GPTRemediationContext(
            running_config="interface GigabitEthernet0/1\n shutdown",
            generated_config="interface GigabitEthernet0/1\n no shutdown\n ip address 10.0.1.1 255.255.255.0",
            description="Enable interface and add IP address",
            example=example,
        )

        prompt = GPTWorkflowRemediation._build_gpt_prompt(context)

        assert "Network Configuration Remediation Plan Generation" in prompt
        assert "interface GigabitEthernet0/1" in prompt
        assert "Enable interface and add IP address" in prompt
        assert "interface Eth0" in prompt

    def test_gpt_remediation_config_no_client(self, remediation_workflow):
        """Test error when no GPT client is set."""
        with pytest.raises(
            GPTClientInitializationError, match="No GPT client is initialized"
        ):
            remediation_workflow.gpt_remediation_config()

    def test_gpt_remediation_config_no_rules(self, remediation_workflow):
        """Test error when no GPT rules are added."""
        # Set up a mock client
        mock_client = MagicMock()
        remediation_workflow.set_gpt_client(mock_client)

        with pytest.raises(RemediationError, match="No GPT remediation rules loaded"):
            remediation_workflow.gpt_remediation_config()

    @patch("hier_config_gpt.workflows.get_hconfig_fast_load")
    def test_gpt_remediation_config_success(
        self, mock_get_hconfig, remediation_workflow, gpt_rule, mock_driver
    ):
        """Test successful GPT remediation plan generation."""
        # Set up mocks
        mock_client = MagicMock()
        mock_client.generate_plan.return_value = [
            "interface GigabitEthernet0/1",
            " ip address 10.0.1.1 255.255.255.0",
            " no shutdown",
        ]

        # Create a real HConfig instance for the result
        result_config = HConfig(mock_driver)
        mock_get_hconfig.return_value = result_config

        # Prepare mocks for _build_remediation_context
        example = GPTRemediationExample(
            running_config="interface Eth0\n shutdown",
            remediation_config="interface Eth0\n no shutdown",
        )

        context = GPTRemediationContext(
            running_config="interface GigabitEthernet0/1\n shutdown",
            generated_config="interface GigabitEthernet0/1\n no shutdown\n ip address 10.0.1.1 255.255.255.0",
            description="Enable interface and add IP address",
            example=example,
        )

        # Configure workflow and mocks
        with patch.object(
            remediation_workflow, "_build_remediation_context"
        ) as mock_build_context:
            mock_build_context.return_value = iter(
                [context]
            )  # Return an iterator of contexts
            remediation_workflow.set_gpt_client(mock_client)
            remediation_workflow.add_gpt_rule(gpt_rule)

            # Run test
            result = remediation_workflow.gpt_remediation_config()

            # Verify results
            assert result is result_config
            mock_client.generate_plan.assert_called_once()
            prompt = GPTWorkflowRemediation._build_gpt_prompt(context)
            mock_client.generate_plan.assert_called_once_with(prompt)
            mock_get_hconfig.assert_called_once_with(
                remediation_workflow.running_config.driver,
                mock_client.generate_plan.return_value,
            )

    @patch("hier_config_gpt.workflows.get_hconfig_fast_load")
    def test_gpt_remediation_config_error(
        self, mock_get_hconfig, remediation_workflow, gpt_rule
    ):
        """Test error handling during GPT remediation plan generation."""
        # Set up mocks
        mock_client = MagicMock()
        mock_client.generate_plan.side_effect = Exception("API error")

        # Prepare mocks for _build_remediation_context
        example = GPTRemediationExample(
            running_config="interface Eth0\n shutdown",
            remediation_config="interface Eth0\n no shutdown",
        )

        context = GPTRemediationContext(
            running_config="interface GigabitEthernet0/1\n shutdown",
            generated_config="interface GigabitEthernet0/1\n no shutdown\n ip address 10.0.1.1 255.255.255.0",
            description="Enable interface and add IP address",
            example=example,
        )

        # Configure workflow and mocks
        with patch.object(
            remediation_workflow, "_build_remediation_context"
        ) as mock_build_context:
            mock_build_context.return_value = iter(
                [context]
            )  # Return an iterator of contexts
            remediation_workflow.set_gpt_client(mock_client)
            remediation_workflow.add_gpt_rule(gpt_rule)

            # Run test
            with pytest.raises(
                RemediationError, match="Failed to generate remediation plan: API error"
            ):
                remediation_workflow.gpt_remediation_config()
