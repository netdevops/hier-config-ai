"""Evaluation harness for model-generated remediation.

Kept out of the blocking CI job because it calls real providers and costs real
money. Run it by hand, or on a schedule, when a prompt, a model, or the
validation loop changes.
"""
