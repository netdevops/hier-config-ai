"""Dependencies handed to the agent's tools and output validators."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING, Protocol

from hier_config import WorkflowRemediation

if TYPE_CHECKING:
    from hier_config import HConfig
    from hier_config.models import Platform
    from hier_config.platforms.driver_base import HConfigDriverBase

    from .models import AIRemediationExample


class Retriever(Protocol):
    """Supplies extra context to the model.

    No implementation ships in 0.2.0. The protocol is declared now so that
    `RemediationDeps.retriever` can be typed, because adding the field later
    would change the signature of every tool and output validator.
    """

    async def search(
        self,
        query: str,
        *,
        platform: Platform,
        k: int = 5,
    ) -> list[str]:
        """Return context snippets relevant to `query` for `platform`."""
        ...  # pylint: disable=unnecessary-ellipsis

    async def similar_remediations(
        self,
        running_config: HConfig,
        generated_config: HConfig,
        *,
        platform: Platform,
        k: int = 3,
    ) -> list[AIRemediationExample]:
        """Return past remediations resembling this running/generated pair."""
        ...  # pylint: disable=unnecessary-ellipsis


@dataclass(frozen=True)
class RemediationDeps:
    """Per-run state shared by the prompt, the tools, and the validators.

    The configs are fixed for the life of a run, so everything derived from
    them is computed once and cached. `cached_property` writes through the
    frozen dataclass by assigning into `__dict__`; do not add `slots=True`.
    """

    running_config: HConfig
    generated_config: HConfig
    # The whole device config, so `get_config_section` can reach past the
    # section under remediation. Defaults to the scoped configs when a caller
    # builds deps directly.
    full_running_config: HConfig | None = None
    full_generated_config: HConfig | None = None
    retriever: Retriever | None = None

    @property
    def whole_running_config(self) -> HConfig:
        """The device's full running config, falling back to the scoped one."""
        return self.full_running_config or self.running_config

    @property
    def whole_generated_config(self) -> HConfig:
        """The device's full intended config, falling back to the scoped one."""
        return self.full_generated_config or self.generated_config

    @property
    def driver(self) -> HConfigDriverBase:
        """The driver that parsed the running config."""
        return self.running_config.driver

    @cached_property
    def canonical_future(self) -> HConfig:
        """The configuration a correct plan must produce.

        hier-config's own remediation is applied to the running config, giving
        the intended result expressed the way `HConfig.future` expresses it.
        Candidate plans are compared against this rather than against the
        generated config directly, so both sides pass through the same
        normalization.
        """
        deterministic = WorkflowRemediation(
            self.running_config,
            self.generated_config,
        ).remediation_config
        return self.running_config.future(deterministic)

    @cached_property
    def canonical_lines(self) -> tuple[str, ...]:
        """`canonical_future` rendered to lines.

        Cached because every convergence check needs it, and rendering walks
        the whole tree.
        """
        return tuple(self.canonical_future.to_lines())

    @cached_property
    def canonical_line_set(self) -> frozenset[str]:
        """`canonical_lines` as a set, for membership tests."""
        return frozenset(self.canonical_lines)
