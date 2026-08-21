"""Cases and scorers for remediation evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hier_config import HConfig, Platform
from hier_config.models import MatchRule
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from hier_config_ai.deps import RemediationDeps
from hier_config_ai.models import AIRemediationExample, AIRemediationRule
from hier_config_ai.validation import plan_converges
from hier_config_ai.workflows import scoped_config

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


@dataclass
class RemediationTask:
    """One remediation problem to put to a model."""

    name: str
    platform: Platform
    running_config: str
    generated_config: str
    rule: AIRemediationRule

    def configs(self) -> tuple[HConfig, HConfig]:
        """Parse this task's running and generated configurations."""
        return (
            HConfig.from_text(self.platform, self.running_config),
            HConfig.from_text(self.platform, self.generated_config),
        )

    def deps(self) -> RemediationDeps:
        """Build deps scoped to this task's rule."""
        running, generated = self.configs()
        return RemediationDeps(
            running_config=scoped_config(running, self.rule.lineage),
            generated_config=scoped_config(generated, self.rule.lineage),
        )


@dataclass
class Converges(Evaluator[RemediationTask, list[str]]):
    """Score a plan by whether it actually reaches the intended config.

    This is the only score that matters. A plan can read well, use the right
    commands, and still leave the device wrong, so the plan is applied and
    re-diffed rather than compared to a reference answer. There is usually more
    than one correct plan, which is why no reference answer is used.
    """

    def evaluate(
        self,
        ctx: EvaluatorContext[RemediationTask, list[str]],
    ) -> float:
        """Return 1.0 when the plan converges, otherwise 0.0."""
        return 1.0 if plan_converges(ctx.inputs.deps(), list(ctx.output)) else 0.0


@dataclass
class PlanLength(Evaluator[RemediationTask, list[str]]):
    """Record how many commands the plan contains.

    Not a pass or fail signal. It is recorded so that a change which keeps
    plans converging but makes them much longer is visible.
    """

    def evaluate(self, ctx: EvaluatorContext[RemediationTask, list[str]]) -> int:
        """Return the number of commands in the plan."""
        return len(ctx.output)


def read_fixture(name: str) -> str:
    """Read a config fixture from the test fixtures directory."""
    return (FIXTURES / name).read_text(encoding="utf-8")


def acl_resequencing_case() -> Case[RemediationTask, list[str], None]:
    """Resequence an extended ACL and add an entry ahead of the existing one.

    hier-config cannot resolve this deterministically: the existing entry has
    to move from sequence 12 to 20 so a new entry can take 10. Getting it wrong
    either drops traffic or leaves the entries in the wrong order.
    """
    task = RemediationTask(
        name="acl-resequencing",
        platform=Platform.CISCO_IOS,
        running_config=read_fixture("running_config_acl.conf"),
        generated_config=read_fixture("generated_config_acl.conf"),
        rule=AIRemediationRule(
            description=(
                "Rewrite the access list so its entries end up in the intended "
                "order with the intended sequence numbers. Remove entries that "
                "are no longer wanted before adding their replacements."
            ),
            lineage=(MatchRule(startswith="ip access-list"),),
            example=AIRemediationExample(
                running_config=(
                    "ip access-list extended EXAMPLE\n 20 permit ip any any"
                ),
                remediation_config=(
                    "ip access-list extended EXAMPLE\n"
                    " no 20 permit ip any any\n"
                    " 10 permit ip 192.0.2.0 0.0.0.255 any\n"
                    " 20 permit ip any any"
                ),
            ),
        ),
    )
    return Case(name=task.name, inputs=task)


def build_dataset() -> Dataset[RemediationTask, list[str], None]:
    """Build the evaluation dataset."""
    return Dataset(
        name="remediation",
        cases=[acl_resequencing_case()],
        evaluators=[Converges(), PlanLength()],
    )
