# Prompt Templates

## The default

Each rule's prompt is built by `PromptTemplate`. The default states the
objective, shows the running and intended configuration for the rule's section,
gives the rule description and worked example, and asks for a plan.

The platform's own rules are added separately, read from the hier-config driver
rather than written into the template.

## Customising

```python
from hier_config_ai import AIWorkflowRemediation, PromptTemplate

template = PromptTemplate(template="""
Bring this device section into line with the intended configuration.

Current:
{running_config}

Intended:
{generated_config}

Rules:
{description}

Example running config:
{example_running_config}

Example remediation:
{example_remediation_config}
""")

workflow = AIWorkflowRemediation(running, intended, prompt_template=template)
```

!!! warning "This argument did not exist before 0.2.0"
    0.1.x documented `prompt_template=` on the constructor, exported
    `PromptTemplate`, and never wired it in. Every documented example raised
    `TypeError`. It works now.

## Required placeholders

All five must appear, or the constructor raises `ValueError`:

- `{running_config}`
- `{generated_config}`
- `{description}`
- `{example_running_config}`
- `{example_remediation_config}`

## Loading from a file

```python
template = PromptTemplate.from_file("prompts/remediation.txt")
```

!!! warning "Braces are format placeholders"
    The template is rendered with `str.format`, so a literal brace must be
    doubled. A template containing a JSON example needs `{{` and `}}`.

## Writing the example

`AIRemediationExample` is few-shot input, not documentation. The model copies
its shape, so anything incoherent in it is something you are teaching the model
to do.

Keep it internally consistent: one device, one section, one access list. An
example that renumbers one access list and then edits a different one is not a
harmless slip — it is a worked demonstration of the wrong thing.

Do not name a command the task cannot use. Mentioning
`ip access-list resequence` in a rule whose target needs individual entries
renumbered invites the model to reach for a command that renumbers everything
by a fixed stride, and it will spend retries discovering that it cannot.

## What not to put in a template

Do not restate the output format. Structured output enforces it, and repeating
it wastes tokens and invites contradictions.

Do not restate platform behaviour such as indent width or negation prefixes.
Those are read from the driver, and a hand-written copy will drift from the
parser that validates the answer.

Do put domain context in: naming standards, address plans, which changes need a
maintenance window.
