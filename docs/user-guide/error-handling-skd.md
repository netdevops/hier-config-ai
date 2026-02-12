# Error Handling

When working with LLMs for network configuration, failures can range from simple API timeouts to complex logic disagreements between providers. `hier-config-gpt` uses a mix of custom exceptions and standard Python exceptions to help you build resilient automation.

## Custom Exceptions

The library defines specific exceptions to differentiate between setup issues and execution failures.

* * *

## Core Error Logic

Understanding how the SDK handles errors internally allows you to write better `try/except` blocks.

### 1\. The Retry Mechanism

The SDK includes a `retry_with_backoff` utility used by most clients (OpenAI, Anthropic, Ollama).

*   **Transient Failures:** It automatically retries on general exceptions up to 2 times (default) with exponential backoff.
    
*   **Exhaustion:** If the retries fail, the original exception is re-raised to your application.
    

### 2\. Validation Errors

Before a response is returned to you, the SDK validates the structure of the LLM output using `parse_plan_payload`.

*   If the LLM returns invalid JSON or a payload missing the "plan" key, a **`ValueError`** is raised.
    

### 3\. Rate Limiting

If you use the `RateLimitedGPTClient` wrapper, the SDK will block (wait) until a token is available.

*   If a timeout is set and reached before a token is acquired, it will log a warning and return `False`, potentially leading to a failure in the calling function.
    

* * *

## Implementation Example

The following pattern is recommended for production environments to handle both library-specific errors and underlying provider issues (like OpenAI authentication or network timeouts).

* * *

## Best Practices

*   **Catch Provider Exceptions:** Since `hier-config-gpt` does not wrap every possible provider error, you should still catch native exceptions from `openai` or `anthropic` libraries.
    
*   **Use Quorum for Critical Tasks:** If high reliability is required, use `MultiProviderGPTClient` with `enable_quorum=True`. This prevents a single hallucinating or failing model from returning a bad configuration.
    
*   **Monitor Backoff Logs:** Enable `logging` at the `INFO` level to see retry attempts. If you see frequent "Provider call failed" logs, consider increasing your `timeout` or `retries` settings in the client constructor.

## Next Steps

- Apply custom templates to [real-world examples](../examples.md)
- Combine with [advanced features](advanced-features.md) like quorum mode
- Review [API reference](../api-reference.md) for `PromptTemplate` class details