# Changelog

The complete changelog lives in
[CHANGELOG.md](https://github.com/netdevops/hier-config-ai/blob/main/CHANGELOG.md).

## 0.2.0

Renamed from `hier-config-gpt` to `hier-config-ai`, and rebuilt on
[PydanticAI](https://ai.pydantic.dev/). A deliberate break from 0.1.x, with no
compatibility shims.

- Plans are validated against hier-config and corrected by the model through
  `ModelRetry`, instead of being returned unchecked.
- The model can call `test_remediation` to see what its commands would do.
- Destructive commands are rejected; risky ones are surfaced for review.
- Platform rules come from the hier-config driver rather than a hardcoded
  prompt.
- Async support, with rules running concurrently.
- One provider extra replaces three, and Google, Bedrock, Groq, and Mistral join
  OpenAI and Anthropic.
- Fixed: extras that installed nothing, imports that required every SDK, a cache
  that could return an empty plan as success, quorum that could not reach
  agreement, and a `prompt_template` argument that was documented but never
  existed.

## 0.1.0

Initial release, as `hier-config-gpt`.

## Links

- [Full changelog](https://github.com/netdevops/hier-config-ai/blob/main/CHANGELOG.md)
- [Releases](https://github.com/netdevops/hier-config-ai/releases)
- [Issues](https://github.com/netdevops/hier-config-ai/issues)
