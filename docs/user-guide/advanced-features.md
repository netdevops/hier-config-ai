# Advanced Features

hier-config-gpt includes several advanced features designed for production environments, including response caching, rate limiting, and multi-provider quorum consensus.

## Response Caching

Caching reduces API costs and improves performance by storing and reusing LLM responses for identical prompts.

### Why Use Caching?

- **Cost Savings**: Avoid paying for duplicate API calls
- **Performance**: Instant responses for cached queries
- **Consistency**: Same input always produces the same output
- **Development**: Faster iteration during testing

### Basic Caching

```python
from hier_config_gpt.clients import (
    ChatGPTClient,
    CachedGPTClient,
    ResponseCache
)

# Create base client
base_client = ChatGPTClient(api_key=os.getenv("OPENAI_API_KEY"))

# Wrap with caching (default 1 hour TTL)
cache = ResponseCache(ttl_seconds=3600)
client = CachedGPTClient(base_client, cache=cache)

wfr.set_gpt_client(client)
```

### Cache Configuration

```python
# Custom TTL (time-to-live)
cache = ResponseCache(ttl_seconds=7200)  # 2 hours

# Long-term caching for stable rules
cache = ResponseCache(ttl_seconds=86400)  # 24 hours

# Short-term caching for development
cache = ResponseCache(ttl_seconds=300)  # 5 minutes
```

### How It Works

1. Before making an API call, the client checks if an identical prompt exists in cache
2. If found and not expired, the cached response is returned immediately
3. If not found, the API is called and the response is stored in cache
4. Cache entries automatically expire after the TTL period

### Cache Key Generation

The cache key is generated from:
- The complete prompt text
- Model name and parameters
- Provider type

This ensures that different configurations don't accidentally share cached responses.

## Rate Limiting

Rate limiting prevents API throttling by controlling the request rate using a token bucket algorithm.

### Why Use Rate Limiting?

- **Avoid Throttling**: Stay within API provider limits
- **Cost Control**: Limit spending on API calls
- **Graceful Degradation**: Handle burst traffic smoothly
- **Fair Usage**: Distribute resources across multiple workflows

### Basic Rate Limiting

```python
from hier_config_gpt.clients import (
    ChatGPTClient,
    RateLimitedGPTClient
)

# Create base client
base_client = ChatGPTClient(api_key=os.getenv("OPENAI_API_KEY"))

# Wrap with rate limiting (60 requests per minute)
client = RateLimitedGPTClient(
    base_client,
    max_requests=60,
    time_window_seconds=60.0
)

wfr.set_gpt_client(client)
```

### Rate Limit Configuration

```python
# Conservative rate (30 RPM)
client = RateLimitedGPTClient(
    base_client,
    max_requests=30,
    time_window_seconds=60.0
)

# OpenAI tier limits (example)
# Tier 1: 500 RPM
client = RateLimitedGPTClient(
    base_client,
    max_requests=500,
    time_window_seconds=60.0
)

# Per-hour limiting
client = RateLimitedGPTClient(
    base_client,
    max_requests=1000,
    time_window_seconds=3600.0  # 1 hour
)
```

### Token Bucket Algorithm

The rate limiter uses a token bucket algorithm:

1. A bucket holds tokens (available requests)
2. Tokens are added at a constant rate
3. Each request consumes one token
4. If no tokens are available, the request waits
5. Burst traffic is handled smoothly up to the bucket capacity

## Combining Caching and Rate Limiting

For production systems, combine both features for optimal performance:

```python
from hier_config_gpt.clients import (
    ChatGPTClient,
    CachedGPTClient,
    RateLimitedGPTClient,
    ResponseCache
)

# Create layered client: rate limiting -> caching -> base client
base_client = ChatGPTClient(api_key=os.getenv("OPENAI_API_KEY"))

# Add caching layer
cached_client = CachedGPTClient(
    base_client,
    cache=ResponseCache(ttl_seconds=3600)
)

# Add rate limiting layer
client = RateLimitedGPTClient(
    cached_client,
    max_requests=60,
    time_window_seconds=60.0
)

wfr.set_gpt_client(client)
```

### How Layering Works

1. Request enters rate limiter (waits if needed)
2. Passes to cache layer (returns cached if available)
3. Falls through to base client (makes API call if needed)
4. Response flows back through cache (stored) and rate limiter (returns)

This approach:
- Minimizes API calls (caching)
- Prevents throttling (rate limiting)
- Maintains good performance (fast cache hits)

## Quorum Mode (Multi-Provider Consensus)

Quorum mode uses multiple LLM providers with majority voting for critical operations, increasing reliability and accuracy.

### Why Use Quorum Mode?

- **Higher Reliability**: Reduces impact of any single model's errors
- **Increased Confidence**: Majority consensus validates results
- **Fault Tolerance**: System continues if one provider fails
- **Quality Assurance**: Critical changes get extra validation

### Basic Quorum Setup

```python
from hier_config_gpt.clients import (
    ChatGPTClient,
    ClaudeGPTClient,
    OllamaGPTClient,
    MultiProviderGPTClient
)

# Create multiple provider clients
openai_client = ChatGPTClient(
    api_key=os.getenv("OPENAI_API_KEY"),
    model="gpt-4o"
)

claude_client = ClaudeGPTClient(
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    model="claude-3-5-sonnet-20241022"
)

ollama_client = OllamaGPTClient(
    host="http://localhost:11434",
    model="llama3.2"
)

# Create quorum client (requires majority agreement)
client = MultiProviderGPTClient(
    providers=[openai_client, claude_client, ollama_client],
    enable_quorum=True
)

wfr.set_gpt_client(client)
```

### How Quorum Works

1. The same prompt is sent to all providers simultaneously
2. Each provider generates a remediation plan
3. Plans are compared for consensus
4. The majority response is returned
5. If no majority exists, the first response is used (with warning)

### Quorum Strategies

```python
# Strict quorum (all must agree)
client = MultiProviderGPTClient(
    providers=[openai_client, claude_client],
    enable_quorum=True,
    require_unanimous=True  # Requires 100% agreement
)

# Simple majority (default)
client = MultiProviderGPTClient(
    providers=[openai_client, claude_client, ollama_client],
    enable_quorum=True  # Requires > 50% agreement
)

# Fallback mode (no quorum, just use first)
client = MultiProviderGPTClient(
    providers=[openai_client, claude_client],
    enable_quorum=False  # Uses first successful response
)
```

### Cost Considerations

Quorum mode multiplies API costs by the number of providers. Use it selectively:

```python
# Use quorum for critical configs
critical_client = MultiProviderGPTClient(
    providers=[openai_client, claude_client],
    enable_quorum=True
)

# Use single provider for routine changes
routine_client = openai_client

# Switch based on importance
if is_production_device:
    wfr.set_gpt_client(critical_client)
else:
    wfr.set_gpt_client(routine_client)
```

## Advanced Client Composition

You can combine all features for maximum control:

```python
from hier_config_gpt.clients import (
    ChatGPTClient,
    ClaudeGPTClient,
    CachedGPTClient,
    RateLimitedGPTClient,
    MultiProviderGPTClient,
    ResponseCache
)

# Build individual provider chains
openai_base = ChatGPTClient(api_key=os.getenv("OPENAI_API_KEY"))
openai_cached = CachedGPTClient(openai_base, ResponseCache())
openai_limited = RateLimitedGPTClient(openai_cached, max_requests=60)

claude_base = ClaudeGPTClient(api_key=os.getenv("ANTHROPIC_API_KEY"))
claude_cached = CachedGPTClient(claude_base, ResponseCache())
claude_limited = RateLimitedGPTClient(claude_cached, max_requests=50)

# Combine with quorum
client = MultiProviderGPTClient(
    providers=[openai_limited, claude_limited],
    enable_quorum=True
)

wfr.set_gpt_client(client)
```

This configuration provides:
- Individual rate limiting per provider
- Caching for each provider
- Quorum consensus for critical reliability

## Monitoring and Logging

Enable detailed logging to monitor performance:

```python
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hier_config_gpt")
logger.setLevel(logging.DEBUG)

# Now you'll see detailed logs for:
# - Cache hits/misses
# - Rate limit waits
# - Quorum decisions
# - API calls and responses
```

## Best Practices

1. **Use Caching in Development**: Speed up iteration with longer TTLs
2. **Use Rate Limiting in Production**: Prevent throttling and control costs
3. **Use Quorum for Critical Changes**: Production devices, security configs
4. **Layer Appropriately**: Cache before rate limit for best performance
5. **Monitor Costs**: Track API usage when using quorum mode
6. **Test Thoroughly**: Validate remediation plans in lab environments first

## Next Steps

- Customize [prompt templates](prompt-templates.md) for better LLM responses
- Explore [examples](../examples.md) of real-world use cases
- Review the [API reference](../api-reference.md) for detailed documentation
