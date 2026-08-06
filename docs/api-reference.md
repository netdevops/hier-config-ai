# API Reference

Complete API documentation for hier-config-gpt classes and functions.

## Core Classes

### GPTWorkflowRemediation

Main class that extends `hier_config.WorkflowRemediation` with GPT capabilities.

```python
from hier_config_gpt import GPTWorkflowRemediation
```

#### Constructor

```python
GPTWorkflowRemediation(
    running_config: HConfig,
    generated_config: HConfig,
    prompt_template: Optional[PromptTemplate] = None
)
```

**Parameters:**

- `running_config` (HConfig): Current device configuration
- `generated_config` (HConfig): Desired configuration state
- `prompt_template` (PromptTemplate, optional): Custom prompt template for LLM communication

**Example:**

```python
from hier_config import HConfig, Platform

wfr = GPTWorkflowRemediation(
    running_config=HConfig.from_text(Platform.CISCO_IOS, running_text),
    generated_config=HConfig.from_text(Platform.CISCO_IOS, generated_text)
)
```

#### Methods

##### set_gpt_client()

```python
set_gpt_client(gpt_client: GPTClient) -> None
```

Sets the LLM client for generating remediation plans.

**Parameters:**

- `gpt_client` (GPTClient): An instance of ChatGPTClient, ClaudeGPTClient, or OllamaGPTClient

**Example:**

```python
from hier_config_gpt.clients import ChatGPTClient

client = ChatGPTClient(api_key="your-key")
wfr.set_gpt_client(client)
```

##### add_gpt_rule()

```python
add_gpt_rule(rule: GPTRemediationRule) -> None
```

Adds a remediation rule to the workflow.

**Parameters:**

- `rule` (GPTRemediationRule): Rule defining how to remediate specific configuration sections

**Example:**

```python
from hier_config_gpt.models import GPTRemediationRule, GPTRemediationExample
from hier_config.models import MatchRule

rule = GPTRemediationRule(
    description="How to remediate...",
    lineage=(MatchRule(startswith="ip access-list"),),
    example=GPTRemediationExample(
        running_config="...",
        remediation_config="..."
    )
)
wfr.add_gpt_rule(rule)
```

##### clear_gpt_rules()

```python
clear_gpt_rules() -> None
```

Removes all GPT rules from the workflow.

**Example:**

```python
wfr.clear_gpt_rules()
```

##### gpt_remediation_config()

```python
gpt_remediation_config() -> HConfig
```

Generates the GPT-based remediation plan.

**Returns:**

- `HConfig`: Configuration object containing remediation commands

**Raises:**

- `GPTClientInitializationError`: If no GPT client is set
- `RemediationError`: If remediation plan generation fails

**Example:**

```python
try:
    remediation = wfr.gpt_remediation_config()
    print(remediation)
except RemediationError as e:
    print(f"Error: {e}")
```

## Model Classes

### GPTRemediationRule

Defines a rule for AI-driven configuration remediation.

```python
from hier_config_gpt.models import GPTRemediationRule
```

#### Attributes

```python
class GPTRemediationRule(BaseModel):
    description: str
    lineage: tuple[MatchRule, ...]
    example: GPTRemediationExample
```

**Fields:**

- `description` (str): Detailed instructions for the LLM on how to remediate
- `lineage` (tuple[MatchRule, ...]): Match rules to identify which configurations this rule applies to
- `example` (GPTRemediationExample): Example transformation to guide the LLM

**Example:**

```python
from hier_config.models import MatchRule
from hier_config_gpt.models import GPTRemediationRule, GPTRemediationExample

rule = GPTRemediationRule(
    description="When remediating ACLs: 1. Resequence, 2. Add temp permit...",
    lineage=(MatchRule(startswith="ip access-list"),),
    example=GPTRemediationExample(
        running_config="ip access-list extended TEST\n  10 permit ip any any",
        remediation_config="ip access-list resequence TEST 10 10"
    )
)
```

### GPTRemediationExample

Example configuration transformation for LLM guidance.

```python
from hier_config_gpt.models import GPTRemediationExample
```

#### Attributes

```python
class GPTRemediationExample(BaseModel):
    running_config: str
    remediation_config: str
```

**Fields:**

- `running_config` (str): Example of current configuration state
- `remediation_config` (str): Example of commands to transform it

**Example:**

```python
example = GPTRemediationExample(
    running_config="interface Gi0/1\n  ip address 10.0.0.1 255.255.255.0",
    remediation_config="interface Gi0/1\n  shutdown\n  ip address 10.0.1.1 255.255.255.0\n  no shutdown"
)
```

### GPTRemediationContext

Internal context object passed to LLMs (typically not used directly).

```python
class GPTRemediationContext(BaseModel):
    description: str
    running_config: str
    generated_config: str
    example: GPTRemediationExample
```

## Prompt Template

### PromptTemplate

Customizable prompt template for LLM communication.

```python
from hier_config_gpt import PromptTemplate
```

#### Constructor

```python
PromptTemplate(template: Optional[str] = None)
```

**Parameters:**

- `template` (str, optional): Custom template string with required placeholders

**Required Placeholders:**

- `{running_config}`: Current configuration
- `{generated_config}`: Desired configuration
- `{description}`: Remediation instructions
- `{example_running_config}`: Example input
- `{example_remediation_config}`: Example output

**Example:**

```python
custom_template = """
Generate commands to transform:
Current: {running_config}
Target: {generated_config}
Rules: {description}
Example: {example_running_config} -> {example_remediation_config}
"""

template = PromptTemplate(template=custom_template)
```

#### Class Methods

##### from_file()

```python
@classmethod
from_file(cls, file_path: str) -> PromptTemplate
```

Loads a prompt template from a file.

**Parameters:**

- `file_path` (str): Path to template file

**Returns:**

- `PromptTemplate`: Instance with loaded template

**Example:**

```python
template = PromptTemplate.from_file("my_template.txt")
wfr = GPTWorkflowRemediation(
    running_config=running,
    generated_config=generated,
    prompt_template=template
)
```

#### Instance Methods

##### build()

```python
build(context: GPTRemediationContext) -> str
```

Builds a prompt from context (typically called internally).

## Client Classes

### ChatGPTClient

OpenAI GPT client for configuration remediation.

```python
from hier_config_gpt.clients import ChatGPTClient
```

#### Constructor

```python
ChatGPTClient(
    api_key: str,
    model: str = "gpt-4o",
    timeout: float = 30.0,
    max_retries: int = 3,
    temperature: float = 0.0
)
```

**Parameters:**

- `api_key` (str): OpenAI API key
- `model` (str): Model name (default: "gpt-4o")
- `timeout` (float): Request timeout in seconds
- `max_retries` (int): Number of retry attempts
- `temperature` (float): Sampling temperature (0.0 = deterministic)

**Example:**

```python
import os
client = ChatGPTClient(
    api_key=os.getenv("OPENAI_API_KEY"),
    model="gpt-4o",
    timeout=30.0
)
```

### ClaudeGPTClient

Anthropic Claude client for configuration remediation.

```python
from hier_config_gpt.clients import ClaudeGPTClient
```

#### Constructor

```python
ClaudeGPTClient(
    api_key: str,
    model: str = "claude-3-5-sonnet-20241022",
    timeout: float = 30.0,
    max_retries: int = 3,
    max_tokens: int = 4096
)
```

**Parameters:**

- `api_key` (str): Anthropic API key
- `model` (str): Model name
- `timeout` (float): Request timeout in seconds
- `max_retries` (int): Number of retry attempts
- `max_tokens` (int): Maximum response length

**Example:**

```python
import os
client = ClaudeGPTClient(
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    model="claude-3-5-sonnet-20241022"
)
```

### OllamaGPTClient

Ollama client for self-hosted LLM models.

```python
from hier_config_gpt.clients import OllamaGPTClient
```

#### Constructor

```python
OllamaGPTClient(
    host: str = "http://localhost:11434",
    model: str = "llama3.2",
    timeout: float = 60.0,
    keep_alive: str = "5m"
)
```

**Parameters:**

- `host` (str): Ollama server URL
- `model` (str): Model name
- `timeout` (float): Request timeout in seconds
- `keep_alive` (str): How long to keep model in memory

**Example:**

```python
client = OllamaGPTClient(
    host="http://localhost:11434",
    model="llama3.2",
    timeout=60.0
)
```

### CachedGPTClient

Wrapper that adds response caching to any GPT client.

```python
from hier_config_gpt.clients import CachedGPTClient, ResponseCache
```

#### Constructor

```python
CachedGPTClient(
    base_client: GPTClient,
    cache: ResponseCache
)
```

**Parameters:**

- `base_client` (GPTClient): Underlying GPT client
- `cache` (ResponseCache): Cache instance

**Example:**

```python
from hier_config_gpt.clients import ChatGPTClient, CachedGPTClient, ResponseCache

base = ChatGPTClient(api_key="...")
cache = ResponseCache(ttl_seconds=3600)
client = CachedGPTClient(base, cache)
```

### RateLimitedGPTClient

Wrapper that adds rate limiting to any GPT client.

```python
from hier_config_gpt.clients import RateLimitedGPTClient
```

#### Constructor

```python
RateLimitedGPTClient(
    base_client: GPTClient,
    max_requests: int = 60,
    time_window_seconds: float = 60.0
)
```

**Parameters:**

- `base_client` (GPTClient): Underlying GPT client
- `max_requests` (int): Maximum requests per time window
- `time_window_seconds` (float): Time window in seconds

**Example:**

```python
from hier_config_gpt.clients import ChatGPTClient, RateLimitedGPTClient

base = ChatGPTClient(api_key="...")
client = RateLimitedGPTClient(base, max_requests=60, time_window_seconds=60.0)
```

### MultiProviderGPTClient

Client that uses multiple LLM providers with optional quorum consensus.

```python
from hier_config_gpt.clients import MultiProviderGPTClient
```

#### Constructor

```python
MultiProviderGPTClient(
    providers: list[GPTClient],
    enable_quorum: bool = False,
    require_unanimous: bool = False
)
```

**Parameters:**

- `providers` (list[GPTClient]): List of GPT clients to use
- `enable_quorum` (bool): Enable majority voting
- `require_unanimous` (bool): Require all providers to agree

**Example:**

```python
from hier_config_gpt.clients import (
    ChatGPTClient,
    ClaudeGPTClient,
    MultiProviderGPTClient
)

openai = ChatGPTClient(api_key="...")
claude = ClaudeGPTClient(api_key="...")

client = MultiProviderGPTClient(
    providers=[openai, claude],
    enable_quorum=True
)
```

### ResponseCache

Cache for storing LLM responses.

```python
from hier_config_gpt.clients import ResponseCache
```

#### Constructor

```python
ResponseCache(ttl_seconds: int = 3600)
```

**Parameters:**

- `ttl_seconds` (int): Time-to-live for cache entries (default: 1 hour)

**Example:**

```python
cache = ResponseCache(ttl_seconds=7200)  # 2 hours
```

## Exceptions

### GPTClientInitializationError

Raised when GPT client is not properly initialized.

```python
from hier_config_gpt.exceptions import GPTClientInitializationError
```

**Example:**

```python
try:
    remediation = wfr.gpt_remediation_config()
except GPTClientInitializationError as e:
    print("Please set a GPT client first")
```

### RemediationError

Raised when remediation plan generation fails.

```python
from hier_config_gpt.exceptions import RemediationError
```

**Example:**

```python
try:
    remediation = wfr.gpt_remediation_config()
except RemediationError as e:
    print(f"Remediation failed: {e}")
```

## Type Definitions

### GPTClient Protocol

Base protocol that all clients must implement.

```python
from typing import Protocol

class GPTClient(Protocol):
    def generate_plan(self, prompt: str) -> GPTResponse:
        """Generate remediation plan from prompt."""
        ...
```

## Usage Pattern

Complete example showing typical API usage:

```python
import os
from hier_config import HConfig, Platform
from hier_config.models import MatchRule
from hier_config_gpt import GPTWorkflowRemediation
from hier_config_gpt.models import GPTRemediationRule, GPTRemediationExample
from hier_config_gpt.clients import ChatGPTClient

# Load configurations
running = HConfig.from_text(Platform.CISCO_IOS, running_text)
generated = HConfig.from_text(Platform.CISCO_IOS, generated_text)

# Create workflow
wfr = GPTWorkflowRemediation(
    running_config=running,
    generated_config=generated
)

# Define rule
rule = GPTRemediationRule(
    description="Remediation instructions...",
    lineage=(MatchRule(startswith="ip access-list"),),
    example=GPTRemediationExample(
        running_config="...",
        remediation_config="..."
    )
)

# Add rule and client
wfr.add_gpt_rule(rule)
client = ChatGPTClient(api_key=os.getenv("OPENAI_API_KEY"))
wfr.set_gpt_client(client)

# Generate remediation
remediation = wfr.gpt_remediation_config()
print(remediation)
```

## See Also

- [Quick Start Guide](quickstart.md) - Get started quickly
- [Examples](examples.md) - Real-world usage examples
- [User Guide](user-guide/clients.md) - Detailed client documentation
- [Advanced Features](user-guide/advanced-features.md) - Caching, rate limiting, quorum
