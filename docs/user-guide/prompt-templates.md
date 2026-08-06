# Prompt Templates

Prompt templates control how hier-config-gpt communicates with LLMs. Customizing templates can improve accuracy and adapt the system to your specific needs.

## Understanding Prompt Templates

A prompt template defines the structure and content of the request sent to the LLM. It includes:

- **Instructions**: What the LLM should do
- **Context**: Current and desired configurations
- **Rules**: Remediation guidelines
- **Examples**: Sample transformations
- **Format**: Expected response structure

## Default Template

hier-config-gpt uses a default template optimized for network configuration remediation:

```python
from hier_config_gpt import PromptTemplate

# The default template (automatically used)
default_template = PromptTemplate()
```

The default template includes:
- Clear instructions for generating remediation commands
- Configuration diff context
- Remediation rules and examples
- JSON response format specification

## Custom Templates

Create custom templates for specialized use cases:

```python
from hier_config_gpt import PromptTemplate, GPTWorkflowRemediation

# Define custom template
custom_template = """
You are a network automation expert. Generate commands to transform the configuration.

CURRENT CONFIGURATION:
{running_config}

DESIRED CONFIGURATION:
{generated_config}

REMEDIATION RULES:
{description}

EXAMPLE TRANSFORMATION:
Input: {example_running_config}
Output: {example_remediation_config}

Generate a JSON response with a "plan" array containing command strings.
Ensure commands are safe and maintain network connectivity.
"""

# Use custom template
template = PromptTemplate(template=custom_template)

wfr = GPTWorkflowRemediation(
    running_config=running,
    generated_config=generated,
    prompt_template=template
)
```

## Template Variables

Templates support these variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `{running_config}` | Current device configuration | `interface GigabitEthernet0/1\n shutdown` |
| `{generated_config}` | Desired configuration state | `interface GigabitEthernet0/1\n no shutdown` |
| `{description}` | Remediation rule description | `Enable the interface safely...` |
| `{example_running_config}` | Example current state | From `GPTRemediationExample` |
| `{example_remediation_config}` | Example remediation | From `GPTRemediationExample` |

## Template Best Practices

### 1. Be Explicit

Clear instructions produce better results:

```python
# Good: Explicit and detailed
template = """
Generate Cisco IOS commands to safely transform the configuration.

REQUIREMENTS:
1. Maintain network connectivity during changes
2. Use proper command syntax for Cisco IOS
3. Include all necessary steps in order
4. Do not skip intermediate states

CURRENT STATE:
{running_config}

DESIRED STATE:
{generated_config}
"""

# Less good: Vague instructions
template = """
Fix the configuration:
{running_config}
to:
{generated_config}
"""
```

### 2. Provide Context

Help the LLM understand your environment:

```python
template = """
You are configuring a Cisco IOS router in a production network.
Changes must maintain connectivity and follow change control procedures.

Platform: Cisco IOS 15.x
Environment: Production
Risk Level: High

CURRENT CONFIGURATION:
{running_config}

TARGET CONFIGURATION:
{generated_config}

REMEDIATION RULES:
{description}
"""
```

### 3. Include Examples

Examples significantly improve accuracy:

```python
template = """
Generate remediation commands following this pattern:

EXAMPLE 1:
Current: {example_running_config}
Commands: {example_remediation_config}

Now apply the same logic to:
Current: {running_config}
Target: {generated_config}

Rules to follow:
{description}
"""
```

### 4. Specify Output Format

Be explicit about the expected response structure:

```python
template = """
[... instructions ...]

RESPONSE FORMAT:
Return valid JSON with this exact structure:
{{
    "plan": [
        "command 1",
        "command 2",
        "command 3"
    ]
}}

Do not include any text outside the JSON object.
Each command must be a complete, valid configuration command.
"""
```

## Template Examples

### Template for ACL Changes

```python
acl_template = """
You are an expert in Cisco IOS Access Control List (ACL) configuration.

TASK: Generate commands to safely modify the ACL while maintaining connectivity.

CURRENT ACL:
{running_config}

DESIRED ACL:
{generated_config}

SAFETY REQUIREMENTS:
1. Never remove all permits before adding new ones
2. Use sequence numbers divisible by 10
3. Resequence if needed
4. Add temporary permit if necessary

EXAMPLE:
{example_running_config}
Commands: {example_remediation_config}

Return JSON: {{"plan": ["command1", "command2", ...]}}
"""

template = PromptTemplate(template=acl_template)
```

### Template for Interface Configuration

```python
interface_template = """
Generate Cisco IOS commands for interface configuration changes.

RULES:
{description}

CURRENT:
{running_config}

TARGET:
{generated_config}

SAFETY MEASURES:
- Shut down interface before major changes
- Apply all changes
- Bring interface back up
- Verify configuration

EXAMPLE SEQUENCE:
{example_running_config}
→
{example_remediation_config}

Output JSON with "plan" array.
"""

template = PromptTemplate(template=interface_template)
```

### Template for Routing Protocol Updates

```python
routing_template = """
Expert network engineer task: Update routing protocol configuration.

CONSTRAINTS:
- Maintain routing during transition
- Follow proper OSPF/EIGRP/BGP procedures
- No routing blackholes
- Graceful transitions only

FROM:
{running_config}

TO:
{generated_config}

PROCEDURE GUIDE:
{description}

REFERENCE EXAMPLE:
Before: {example_running_config}
Steps: {example_remediation_config}

Respond with JSON: {{"plan": [...]}}
"""

template = PromptTemplate(template=routing_template)
```

## Advanced: Dynamic Templates

Generate templates programmatically based on device type:

```python
def get_template_for_platform(platform: str) -> PromptTemplate:
    """Return appropriate template for device platform."""

    templates = {
        "cisco_ios": """
        Generate Cisco IOS commands...
        {running_config}
        {generated_config}
        {description}
        """,

        "cisco_nxos": """
        Generate Cisco NX-OS commands...
        {running_config}
        {generated_config}
        {description}
        """,

        "arista_eos": """
        Generate Arista EOS commands...
        {running_config}
        {generated_config}
        {description}
        """
    }

    return PromptTemplate(template=templates.get(platform, templates["cisco_ios"]))

# Use platform-specific template
template = get_template_for_platform("cisco_ios")
wfr = GPTWorkflowRemediation(
    running_config=running,
    generated_config=generated,
    prompt_template=template
)
```

## Testing Templates

Test your templates with known scenarios:

```python
from hier_config import HConfig, Platform
from hier_config_gpt import GPTWorkflowRemediation, PromptTemplate

# Test configuration
running = "ip access-list extended TEST\n  10 permit ip any any"
generated = "ip access-list extended TEST\n  10 deny ip any any\n  20 permit ip any any"

# Test your template
template = PromptTemplate(template=your_custom_template)
wfr = GPTWorkflowRemediation(
    running_config=HConfig.from_text(Platform.CISCO_IOS, running),
    generated_config=HConfig.from_text(Platform.CISCO_IOS, generated),
    prompt_template=template
)

# Generate and review
result = wfr.gpt_remediation_config()
print(result)
```

## Debugging Templates

Enable logging to see the actual prompts sent to LLMs:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("hier_config_gpt")

# Now you'll see the complete prompts in logs
wfr.gpt_remediation_config()
```

## Common Pitfalls

### ❌ Too Vague
```python
template = "Fix this: {running_config} to {generated_config}"
```

### ✅ Clear and Specific
```python
template = """
Generate Cisco IOS commands to transform the configuration.
Maintain connectivity. Use proper syntax. Return JSON format.

Current: {running_config}
Target: {generated_config}
Rules: {description}
Example: {example_remediation_config}
"""
```

### ❌ Missing Format Specification
```python
template = "Generate commands: {running_config} -> {generated_config}"
# LLM might return text, markdown, or other formats
```

### ✅ Explicit Format
```python
template = """
[...instructions...]

Return JSON only: {{"plan": ["cmd1", "cmd2"]}}
No markdown, no explanations, just JSON.
"""
```

## Next Steps

- Apply custom templates to [real-world examples](../examples.md)
- Combine with [advanced features](advanced-features.md) like quorum mode
- Review [API reference](../api-reference.md) for `PromptTemplate` class details
