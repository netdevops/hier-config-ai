# hier-config-gpt

**AI-powered network configuration remediation with GPT/LLM integration**

[![PyPI version](https://badge.fury.io/py/hier-config-gpt.svg)](https://badge.fury.io/py/hier-config-gpt)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

## Overview

`hier-config-gpt` extends the powerful [hier-config](https://github.com/netdevops/hier-config) library by adding AI-driven custom remediation workflows. It addresses complex network configuration edge cases that fall outside standard negation and idempotency workflows by leveraging Large Language Models (LLMs) to dynamically generate remediation plans.

## Key Features

- **Multi-Provider LLM Support**: Works with OpenAI GPT, Anthropic Claude, and Ollama (self-hosted) models
- **Intelligent Remediation**: Automatically generates complex configuration remediation steps
- **Quorum Mode**: Optional consensus mechanism across multiple LLM providers for increased reliability
- **Response Caching**: Built-in caching to reduce API costs and improve performance
- **Rate Limiting**: Token bucket algorithm to prevent API throttling
- **Configurable Prompts**: Customize prompt templates for your specific needs
- **Production Ready**: Comprehensive error handling, retry logic, and logging

## Quick Example

```python
import os
from hier_config import get_hconfig, Platform
from hier_config.models import MatchRule
from hier_config_gpt import GPTWorkflowRemediation
from hier_config_gpt.models import GPTRemediationRule, GPTRemediationExample
from hier_config_gpt.clients import ChatGPTClient

# Load configurations
running_config = get_hconfig(Platform.CISCO_IOS, open("running.conf").read())
generated_config = get_hconfig(Platform.CISCO_IOS, open("desired.conf").read())

# Initialize workflow
wfr = GPTWorkflowRemediation(
    running_config=running_config,
    generated_config=generated_config
)

# Define remediation rule
description = """When remediating an access-list on Cisco IOS devices:
1. Resequence the access-list so each sequence number is a multiple of 10
2. Add a temporary 'permit any' statement at sequence 1
3. Apply the required changes from the generated configuration
4. Remove the temporary permit statement
"""

lineage = (MatchRule(startswith="ip access-list"),)
example = GPTRemediationExample(
    running_config="ip access-list extended TEST\n  12 permit ip host 10.0.0.1 any",
    remediation_config="ip access-list resequence TEST 10 10\nip access-list extended TEST\n  1 permit ip any any\n  no 10\n  10 permit ip host 10.0.0.2 any\n  no 1"
)

gpt_rule = GPTRemediationRule(
    description=description,
    lineage=lineage,
    example=example
)

# Add rule and set up client
wfr.add_gpt_rule(gpt_rule)
client = ChatGPTClient(api_key=os.getenv("OPENAI_API_KEY"), model="gpt-4o")
wfr.set_gpt_client(client)

# Generate remediation plan
remediation = wfr.gpt_remediation_config()
print(remediation)
```

## Use Cases

hier-config-gpt is perfect for scenarios where standard configuration remediation isn't sufficient:

- **Access List Resequencing**: Automatically handle complex ACL resequencing with temporary permit statements
- **Interface Configuration**: Generate safe interface configuration changes with proper ordering
- **Routing Protocol Updates**: Handle complex routing protocol transitions
- **VLAN Reconfiguration**: Manage VLAN changes across multiple switches
- **QoS Policy Updates**: Coordinate policy-map and class-map changes

## Why Use hier-config-gpt?

Network configuration remediation often requires more than simple diffs and negations. Some scenarios demand:

- Specific command ordering to maintain connectivity
- Temporary configurations to prevent service disruption
- Complex multi-step procedures
- Context-aware decision making

Traditional automation handles the straightforward cases. hier-config-gpt handles everything else by leveraging AI to understand context and generate intelligent remediation plans.

## Getting Started

1. **[Install](installation.md)** hier-config-gpt with your preferred LLM provider
2. **[Follow the Quick Start](quickstart.md)** guide for your first implementation
3. **[Explore Examples](examples.md)** for real-world use cases
4. **[Configure Advanced Features](user-guide/advanced-features.md)** like caching and rate limiting

## Supported LLM Providers

| Provider | Best For | Cost | Deployment |
|----------|----------|------|------------|
| **OpenAI** | Production use, high accuracy | Pay per use | Cloud API |
| **Anthropic** | Complex reasoning, safety | Pay per use | Cloud API |
| **Ollama** | Privacy, no API costs | Free | Self-hosted |

## Documentation Navigation

<div class="grid cards" markdown>

- **Getting Started**
  - [Installation](installation.md)
  - [Quick Start](quickstart.md)

- **User Guide**
  - [LLM Clients](user-guide/clients.md)
  - [Advanced Features](user-guide/advanced-features.md)
  - [Prompt Templates](user-guide/prompt-templates.md)

- **Reference**
  - [Examples](examples.md)
  - [API Reference](api-reference.md)

- **Community**
  - [Contributing](contributing.md)
  - [Changelog](changelog.md)

</div>

## Requirements

- Python 3.10 or higher
- hier-config 3.2.0 or higher
- At least one LLM provider:
  - OpenAI API key (for GPT models)
  - Anthropic API key (for Claude models)
  - Ollama installation (for self-hosted models)

## Community & Support

- **Issues**: [GitHub Issues](https://github.com/netdevops/hier-config-gpt/issues)
- **Discussions**: [GitHub Discussions](https://github.com/netdevops/hier-config-gpt/discussions)
- **Source Code**: [GitHub Repository](https://github.com/netdevops/hier-config-gpt)

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](https://github.com/netdevops/hier-config-gpt/blob/main/LICENSE) file for details.

## Credits

- Built on top of [hier-config](https://github.com/netdevops/hier-config) by James Williams
- Supports [OpenAI GPT](https://openai.com/), [Anthropic Claude](https://www.anthropic.com/), and [Ollama](https://ollama.ai/)
