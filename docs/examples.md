# Examples

This page provides real-world examples of using hier-config-gpt for various network configuration scenarios.

## Example 1: ACL Resequencing

One of the most common use cases is safely resequencing Access Control Lists (ACLs) on Cisco devices.

### Problem

When modifying ACLs, you need to:
1. Resequence entries to maintain consistent numbering
2. Avoid blocking all traffic during the change
3. Apply new rules correctly
4. Remove temporary rules

### Solution

```python
import os
from hier_config import HConfig, Platform
from hier_config.models import MatchRule
from hier_config_gpt import GPTWorkflowRemediation
from hier_config_gpt.models import GPTRemediationRule, GPTRemediationExample
from hier_config_gpt.clients import ChatGPTClient

# Sample configurations
running_config = """
ip access-list extended PRODUCTION-ACL
  12 permit tcp host 10.0.0.1 host 192.168.1.1 eq 443
  15 permit tcp host 10.0.0.2 host 192.168.1.1 eq 443
  27 permit tcp host 10.0.0.3 host 192.168.1.1 eq 443
"""

generated_config = """
ip access-list extended PRODUCTION-ACL
  10 permit tcp host 10.0.0.1 host 192.168.1.1 eq 443
  20 permit tcp host 10.0.0.4 host 192.168.1.1 eq 443
  30 permit tcp host 10.0.0.3 host 192.168.1.1 eq 443
"""

# Initialize workflow
wfr = GPTWorkflowRemediation(
    running_config=HConfig.from_text(Platform.CISCO_IOS, running_config),
    generated_config=HConfig.from_text(Platform.CISCO_IOS, generated_config)
)

# Define remediation rule
description = """
When remediating an access-list on Cisco IOS:
1. Resequence the ACL so each sequence number is a multiple of 10
2. Add a temporary 'permit ip any any' at sequence 1 to maintain connectivity
3. Remove old entries (using new sequence numbers after resequencing)
4. Add new entries
5. Remove the temporary permit
"""

lineage = (MatchRule(startswith="ip access-list"),)

example = GPTRemediationExample(
    running_config="ip access-list extended TEST\n  12 permit ip host 10.0.0.1 any",
    remediation_config="""ip access-list resequence TEST 10 10
ip access-list extended TEST
  1 permit ip any any
  no 10
  10 permit ip host 10.0.0.2 any
  no 1"""
)

gpt_rule = GPTRemediationRule(
    description=description,
    lineage=lineage,
    example=example
)

wfr.add_gpt_rule(gpt_rule)

# Set up client
client = ChatGPTClient(api_key=os.getenv("OPENAI_API_KEY"), model="gpt-4o")
wfr.set_gpt_client(client)

# Generate remediation
remediation = wfr.gpt_remediation_config()
print(remediation)
```

### Expected Output

```
ip access-list resequence PRODUCTION-ACL 10 10
ip access-list extended PRODUCTION-ACL
  1 permit ip any any
  no 10
  no 20
  no 30
  10 permit tcp host 10.0.0.1 host 192.168.1.1 eq 443
  20 permit tcp host 10.0.0.4 host 192.168.1.1 eq 443
  30 permit tcp host 10.0.0.3 host 192.168.1.1 eq 443
  no 1
```

## Example 2: Interface Configuration with Safety

Safely modify interface configurations with proper shutdown/no shutdown sequences.

### Problem

When making significant interface changes, you need to:
- Shut down the interface first
- Apply all changes
- Bring the interface back up
- Ensure changes are atomic

### Solution

```python
from hier_config import HConfig, Platform
from hier_config.models import MatchRule
from hier_config_gpt import GPTWorkflowRemediation
from hier_config_gpt.models import GPTRemediationRule, GPTRemediationExample
from hier_config_gpt.clients import ClaudeGPTClient

running_config = """
interface GigabitEthernet0/1
  description Old Description
  ip address 10.0.0.1 255.255.255.0
  no shutdown
"""

generated_config = """
interface GigabitEthernet0/1
  description New Production Interface
  ip address 10.0.1.1 255.255.255.0
  speed 1000
  duplex full
  no shutdown
"""

wfr = GPTWorkflowRemediation(
    running_config=HConfig.from_text(Platform.CISCO_IOS, running_config),
    generated_config=HConfig.from_text(Platform.CISCO_IOS, generated_config)
)

description = """
When changing interface IP address:
1. Shut down the interface
2. Apply new configuration
3. Bring the interface back up
This prevents routing issues during the change.
"""

lineage = (MatchRule(startswith="interface"),)

example = GPTRemediationExample(
    running_config="interface Gi0/1\n  ip address 1.1.1.1 255.255.255.0\n  no shutdown",
    remediation_config="interface Gi0/1\n  shutdown\n  ip address 2.2.2.2 255.255.255.0\n  no shutdown"
)

gpt_rule = GPTRemediationRule(description=description, lineage=lineage, example=example)
wfr.add_gpt_rule(gpt_rule)

client = ClaudeGPTClient(api_key=os.getenv("ANTHROPIC_API_KEY"))
wfr.set_gpt_client(client)

remediation = wfr.gpt_remediation_config()
print(remediation)
```

## Example 3: Multi-Provider Quorum for Critical Changes

Use multiple LLM providers with consensus for high-stakes configuration changes.

### Problem

For critical infrastructure, you want multiple AI models to agree on the remediation plan before applying changes.

### Solution

```python
from hier_config import HConfig, Platform
from hier_config.models import MatchRule
from hier_config_gpt import GPTWorkflowRemediation
from hier_config_gpt.models import GPTRemediationRule, GPTRemediationExample
from hier_config_gpt.clients import (
    ChatGPTClient,
    ClaudeGPTClient,
    OllamaGPTClient,
    MultiProviderGPTClient
)

# Production routing configuration
running_config = """
router bgp 65001
  neighbor 10.0.0.1 remote-as 65002
  neighbor 10.0.0.1 description OLD-PEER
"""

generated_config = """
router bgp 65001
  neighbor 10.0.0.2 remote-as 65002
  neighbor 10.0.0.2 description NEW-PEER
"""

wfr = GPTWorkflowRemediation(
    running_config=HConfig.from_text(Platform.CISCO_IOS, running_config),
    generated_config=HConfig.from_text(Platform.CISCO_IOS, generated_config)
)

description = """
When changing BGP neighbors:
1. Configure new neighbor first
2. Wait for BGP to establish
3. Remove old neighbor
This ensures no routing blackhole.
"""

lineage = (MatchRule(startswith="router bgp"),)
example = GPTRemediationExample(
    running_config="router bgp 65001\n  neighbor 1.1.1.1 remote-as 65002",
    remediation_config="router bgp 65001\n  neighbor 2.2.2.2 remote-as 65002\n  no neighbor 1.1.1.1"
)

gpt_rule = GPTRemediationRule(description=description, lineage=lineage, example=example)
wfr.add_gpt_rule(gpt_rule)

# Set up multiple providers
openai = ChatGPTClient(api_key=os.getenv("OPENAI_API_KEY"))
claude = ClaudeGPTClient(api_key=os.getenv("ANTHROPIC_API_KEY"))
ollama = OllamaGPTClient(model="llama3.2")

# Require majority consensus
client = MultiProviderGPTClient(
    providers=[openai, claude, ollama],
    enable_quorum=True
)

wfr.set_gpt_client(client)
remediation = wfr.gpt_remediation_config()
print(remediation)
```

## Example 4: Using Caching and Rate Limiting

Optimize API usage with caching and rate limiting for production environments.

### Problem

You're processing hundreds of device configurations and want to:
- Reduce API costs through caching
- Avoid rate limit throttling
- Maintain good performance

### Solution

```python
from hier_config import HConfig, Platform
from hier_config.models import MatchRule
from hier_config_gpt import GPTWorkflowRemediation
from hier_config_gpt.models import GPTRemediationRule, GPTRemediationExample
from hier_config_gpt.clients import (
    ChatGPTClient,
    CachedGPTClient,
    RateLimitedGPTClient,
    ResponseCache
)

# Create optimized client
base = ChatGPTClient(api_key=os.getenv("OPENAI_API_KEY"), model="gpt-4o-mini")
cached = CachedGPTClient(base, cache=ResponseCache(ttl_seconds=3600))
client = RateLimitedGPTClient(cached, max_requests=50, time_window_seconds=60.0)

# Process multiple devices
devices = ["router1.conf", "router2.conf", "router3.conf"]

for device_file in devices:
    running = open(f"running/{device_file}").read()
    generated = open(f"generated/{device_file}").read()

    wfr = GPTWorkflowRemediation(
        running_config=HConfig.from_text(Platform.CISCO_IOS, running),
        generated_config=HConfig.from_text(Platform.CISCO_IOS, generated)
    )

    # Add your rules...
    wfr.add_gpt_rule(your_rule)
    wfr.set_gpt_client(client)

    # Generate (uses cache if available, respects rate limits)
    remediation = wfr.gpt_remediation_config()
    print(f"\n=== {device_file} ===\n{remediation}")
```

## Example 5: Custom Prompt Template

Tailor the AI prompt for your specific device platform and requirements.

### Problem

You need the AI to understand your specific environment, naming conventions, and safety requirements.

### Solution

```python
from hier_config import HConfig, Platform
from hier_config_gpt import GPTWorkflowRemediation, PromptTemplate
from hier_config_gpt.models import GPTRemediationRule, GPTRemediationExample
from hier_config_gpt.clients import ChatGPTClient

# Custom template for your environment
custom_template = """
You are configuring Cisco IOS routers in a financial services production environment.

CRITICAL REQUIREMENTS:
- All changes must maintain PCI-DSS compliance
- Network connectivity must never be interrupted
- Changes must be reversible
- Include explicit wait times where needed

CURRENT CONFIGURATION:
{running_config}

DESIRED CONFIGURATION:
{generated_config}

REMEDIATION GUIDELINES:
{description}

EXAMPLE TRANSFORMATION:
Input: {example_running_config}
Output: {example_remediation_config}

Generate JSON response: {{"plan": ["command1", "command2", ...]}}
Each command must be a complete Cisco IOS command.
"""

template = PromptTemplate(template=custom_template)

# Use custom template
running = open("router.conf").read()
generated = open("desired.conf").read()

wfr = GPTWorkflowRemediation(
    running_config=HConfig.from_text(Platform.CISCO_IOS, running),
    generated_config=HConfig.from_text(Platform.CISCO_IOS, generated),
    prompt_template=template
)

# Add rules and generate...
client = ChatGPTClient(api_key=os.getenv("OPENAI_API_KEY"))
wfr.set_gpt_client(client)
wfr.add_gpt_rule(your_rule)
remediation = wfr.gpt_remediation_config()
```

## Example 6: VLAN Configuration

Handle VLAN changes with proper dependency management.

### Problem

VLAN changes require careful ordering to avoid disrupting trunk ports and access ports.

### Solution

```python
from hier_config import HConfig, Platform
from hier_config.models import MatchRule
from hier_config_gpt import GPTWorkflowRemediation
from hier_config_gpt.models import GPTRemediationRule, GPTRemediationExample
from hier_config_gpt.clients import ChatGPTClient

running_config = """
vlan 10
  name OLD-DATA
interface GigabitEthernet0/1
  switchport access vlan 10
"""

generated_config = """
vlan 20
  name NEW-DATA
interface GigabitEthernet0/1
  switchport access vlan 20
"""

wfr = GPTWorkflowRemediation(
    running_config=HConfig.from_text(Platform.CISCO_IOS, running_config),
    generated_config=HConfig.from_text(Platform.CISCO_IOS, generated_config)
)

description = """
When changing VLAN assignments:
1. Create new VLAN first
2. Move interfaces to new VLAN
3. Remove old VLAN only after all interfaces are moved
This prevents interface errors.
"""

lineage = (MatchRule(startswith="vlan"),)
example = GPTRemediationExample(
    running_config="vlan 10\ninterface Gi0/1\n  switchport access vlan 10",
    remediation_config="vlan 20\ninterface Gi0/1\n  switchport access vlan 20\nno vlan 10"
)

gpt_rule = GPTRemediationRule(description=description, lineage=lineage, example=example)
wfr.add_gpt_rule(gpt_rule)

client = ChatGPTClient(api_key=os.getenv("OPENAI_API_KEY"))
wfr.set_gpt_client(client)
remediation = wfr.gpt_remediation_config()
print(remediation)
```

## Testing and Validation

Always test generated remediation plans in a lab environment:

```python
# Generate remediation
remediation = wfr.gpt_remediation_config()

# Save for review
with open("remediation_plan.txt", "w") as f:
    f.write(remediation)

# Test in lab first
print("REVIEW THIS PLAN BEFORE APPLYING TO PRODUCTION:")
print(remediation)

# After validation, apply to production
# apply_to_device(remediation)  # Your deployment function
```

## Next Steps

- Review the [API Reference](api-reference.md) for detailed class documentation
- Learn about [advanced features](user-guide/advanced-features.md) for production use
- Customize [prompt templates](user-guide/prompt-templates.md) for your environment
- Explore different [LLM clients](user-guide/clients.md) and their capabilities
