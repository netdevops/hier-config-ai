# Quick Start Guide

This guide will help you get started with hier-config-gpt in just a few minutes.

## Prerequisites

Before you begin, make sure you have:

1. Installed hier-config-gpt with at least one LLM provider (see [Installation](installation.md))
2. An API key for your chosen LLM provider (OpenAI, Anthropic, or Ollama setup)
3. Network configuration files to work with

## Basic Workflow

The typical workflow with hier-config-gpt involves:

1. Loading running and desired configurations
2. Creating a `GPTWorkflowRemediation` instance
3. Defining remediation rules for edge cases
4. Setting up an LLM client
5. Generating the remediation plan

## Your First Example

Let's walk through a complete example that handles ACL (Access Control List) resequencing on Cisco IOS devices.

### Step 1: Import Required Modules

```python
import os
from hier_config import get_hconfig, Platform
from hier_config.models import MatchRule
from hier_config_gpt import GPTWorkflowRemediation
from hier_config_gpt.models import GPTRemediationRule, GPTRemediationExample
from hier_config_gpt.clients import ChatGPTClient
```

### Step 2: Load Your Configurations

```python
# Load your network device configurations
running_config = open("running_config.conf").read()
generated_config = open("desired_config.conf").read()
```

### Step 3: Initialize the Workflow

```python
# Create the remediation workflow
wfr = GPTWorkflowRemediation(
    running_config=get_hconfig(Platform.CISCO_IOS, running_config),
    generated_config=get_hconfig(Platform.CISCO_IOS, generated_config)
)
```

### Step 4: Define a Remediation Rule

Here's where the AI comes in. Define a rule that describes how to handle complex configuration changes:

```python
# Describe the remediation process
description = """When remediating an access-list on Cisco IOS devices:
1. Resequence the access-list so each sequence number is a multiple of 10
2. Add a temporary 'permit any' statement at sequence 1
3. Apply the required changes from the generated configuration
4. Remove the temporary permit statement
"""

# Specify which configurations this rule applies to
lineage = (MatchRule(startswith="ip access-list"),)

# Provide an example for the LLM to learn from
example = GPTRemediationExample(
    running_config="ip access-list extended TEST\n  12 permit ip host 10.0.0.1 any",
    remediation_config="ip access-list resequence TEST 10 10\nip access-list extended TEST\n  1 permit ip any any\n  no 10\n  10 permit ip host 10.0.0.2 any\n  no 1"
)

# Create the rule
gpt_rule = GPTRemediationRule(
    description=description,
    lineage=lineage,
    example=example
)

# Add it to the workflow
wfr.add_gpt_rule(gpt_rule)
```

### Step 5: Set Up Your LLM Client

Choose your preferred LLM provider:

=== "OpenAI"
    ```python
    client = ChatGPTClient(
        api_key=os.getenv("OPENAI_API_KEY"),
        model="gpt-4o"
    )
    wfr.set_gpt_client(client)
    ```

=== "Anthropic Claude"
    ```python
    from hier_config_gpt.clients import ClaudeGPTClient

    client = ClaudeGPTClient(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        model="claude-3-5-sonnet-20241022"
    )
    wfr.set_gpt_client(client)
    ```

=== "Ollama"
    ```python
    from hier_config_gpt.clients import OllamaGPTClient

    client = OllamaGPTClient(
        host="http://localhost:11434",
        model="llama3.2"
    )
    wfr.set_gpt_client(client)
    ```

### Step 6: Generate the Remediation Plan

```python
# Let the AI generate the remediation commands
remediation = wfr.gpt_remediation_config()
print(remediation)
```

## What Happens Behind the Scenes

1. **Context Building**: The workflow identifies configuration sections matching your lineage rules
2. **Prompt Construction**: A structured prompt is created with your description, examples, and the actual configs
3. **LLM Generation**: The LLM analyzes the differences and generates appropriate remediation commands
4. **Output**: You receive a series of commands that safely transform the running config to match the desired state

## Example Output

For an ACL remediation, you might see output like:

```
ip access-list resequence TEST 10 10
ip access-list extended TEST
  1 permit ip any any
  no 10
  10 permit ip host 10.0.0.2 any
  20 permit ip host 10.0.0.3 any
  no 1
```

This sequence safely modifies the ACL by:

1. Resequencing entries to multiples of 10
2. Adding a temporary permit to maintain connectivity
3. Applying the new rules
4. Removing the temporary permit

## Next Steps

Now that you've seen the basics:

- Learn about different [LLM clients](user-guide/clients.md) and their configuration
- Explore [advanced features](user-guide/advanced-features.md) like caching, rate limiting, and quorum mode
- Customize [prompt templates](user-guide/prompt-templates.md) for your specific needs
- Check out more [examples](examples.md) for different use cases
