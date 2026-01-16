# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability, please email the maintainers directly rather than opening a public issue. We take security seriously and will respond promptly.

**Email**: james.williams@packetgeek.net

Please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We aim to respond within 48 hours and will keep you updated on the progress.

## Security Best Practices

### API Key Management

**DO:**

- ✅ Store API keys in environment variables
- ✅ Use secrets management tools (AWS Secrets Manager, HashiCorp Vault, etc.)
- ✅ Rotate API keys regularly
- ✅ Use separate keys for development, staging, and production
- ✅ Restrict API key permissions to minimum required
- ✅ Use `.gitignore` to exclude files containing secrets

**DON'T:**

- ❌ Hard-code API keys in source code
- ❌ Commit API keys to version control
- ❌ Share API keys in chat, email, or tickets
- ❌ Use production keys in development environments
- ❌ Store keys in plain text files

### Example: Secure API Key Usage

```python
import os
from pathlib import Path

# Good: Load from environment variable
api_key = os.getenv("OPENAI_API_KEY")

# Good: Load from secure file outside repository
api_key = Path("~/.config/hier-config-gpt/api_key").expanduser().read_text().strip()

# Good: Use secrets management
from your_secrets_manager import get_secret
api_key = get_secret("openai_api_key")

# BAD: Hard-coded key (NEVER DO THIS)
# api_key = "sk-proj-abc123..."  # ❌ NEVER!
```

### Environment Variables

Create a `.env` file (and add it to `.gitignore`):

```bash
# .env
OPENAI_API_KEY=your-openai-key-here
ANTHROPIC_API_KEY=your-anthropic-key-here
```

Load with python-dotenv:

```python
from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
```

### Network Security

When using self-hosted models (Ollama):

- Use TLS/SSL for remote connections
- Implement authentication
- Use firewall rules to restrict access
- Keep Ollama updated to the latest version

### Prompt Injection

Be aware of prompt injection risks when using user-provided inputs:

```python
# Sanitize user inputs before including in prompts
def sanitize_input(user_input: str) -> str:
    # Remove or escape potentially malicious content
    # Implement appropriate validation for your use case
    return user_input.strip()

description = sanitize_input(user_provided_description)
```

### Logging and Monitoring

- **DO** log API errors and failures
- **DO** monitor for unusual API usage patterns
- **DO** set up alerts for high API costs
- **DON'T** log API keys or sensitive data
- **DON'T** log full API responses that may contain sensitive information

### Example: Safe Logging

```python
import logging

logger = logging.getLogger(__name__)

# Good: Log without sensitive data
logger.info("Generating remediation plan with model: %s", model_name)
logger.debug("API call completed in %.2fs", duration)

# Bad: Logging sensitive data
# logger.debug("API key: %s", api_key)  # ❌ NEVER!
# logger.debug("Full API response: %s", response)  # May contain sensitive data
```

### Rate Limiting

Use rate limiting to:
- Prevent accidental runaway API costs
- Comply with provider rate limits
- Detect potential security issues (e.g., compromised keys)

```python
from hier_config_gpt.clients import RateLimitedGPTClient

# Limit to 60 requests per minute
client = RateLimitedGPTClient(
    base_client,
    max_requests=60,
    time_window_seconds=60.0
)
```

### Caching

Use caching to:
- Reduce API costs
- Minimize exposure from repeated calls
- Improve response times

```python
from hier_config_gpt.clients import CachedGPTClient, ResponseCache

# Cache responses for 1 hour
cache = ResponseCache(ttl_seconds=3600)
client = CachedGPTClient(base_client, cache=cache)
```

**Cache Security Considerations:**

- Cache files are stored in `~/.hier_config_gpt/cache` by default
- Cache files contain API responses (may include configuration data)
- Set appropriate file permissions on the cache directory
- Consider encrypting the cache directory if it contains sensitive data
- Regularly clean up old cache files

```bash
# Set restrictive permissions on cache directory
chmod 700 ~/.hier_config_gpt/cache
```

### Configuration Data

Network configuration files may contain sensitive information:

- IP addresses and network topology
- Access control lists
- SNMP community strings
- Routing protocol secrets
- VPN configurations

**Protect configuration data:**

- Store configuration files securely
- Encrypt sensitive configuration data at rest
- Use secure file permissions
- Implement access controls
- Consider data classification policies

### Dependencies

- Keep all dependencies up to date
- Monitor for security advisories
- Use `poetry show --outdated` to check for updates
- Review dependency licenses and security policies

```bash
# Check for outdated packages
poetry show --outdated

# Update dependencies
poetry update
```

### Audit Trail

Maintain an audit trail for:
- API usage and costs
- Configuration changes generated
- User actions and approvals
- Security events

### Compliance

Ensure compliance with relevant regulations:
- GDPR (if processing EU user data)
- SOC 2 (for service providers)
- Industry-specific regulations (PCI DSS, HIPAA, etc.)

### Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [OpenAI Safety Best Practices](https://platform.openai.com/docs/guides/safety-best-practices)
- [Anthropic Security Documentation](https://docs.anthropic.com/claude/docs/security)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)

## Security Checklist

Before deploying to production:

- [ ] API keys stored securely (not in code)
- [ ] Environment variables configured properly
- [ ] Rate limiting enabled
- [ ] Logging configured (without sensitive data)
- [ ] Cache directory permissions set restrictively
- [ ] Dependencies updated to latest secure versions
- [ ] Network connections use TLS/SSL
- [ ] Access controls implemented
- [ ] Monitoring and alerting configured
- [ ] Backup and recovery procedures documented

## Questions?

If you have security questions or concerns, please contact the maintainers.

Stay secure! 🔒
