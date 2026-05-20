"""Registry of detection rules."""

from __future__ import annotations

from .base import Rule, RuleContext
from .caching import MissingCacheRule
from .checkout import RedundantCheckoutRule
from .concurrency import MissingConcurrencyRule
from .docker import DockerLayerCacheRule
from .matrix import MatrixDuplicatesRule, MatrixFailFastRule
from .parallelization import SelfHostedCandidateRule, SequentialNeedsRule
from .path_filters import DoubleTriggerRule, MissingPathFiltersRule
from .runners import ExpensivePlatformRule, OversizedRunnerRule
from .sharding import MissingShardingRule
from .timeouts import MissingTimeoutRule
from .versions import OutdatedActionsRule

ALL_RULES: list[Rule] = [
    MissingCacheRule(),
    OversizedRunnerRule(),
    MissingConcurrencyRule(),
    MissingTimeoutRule(),
    MissingPathFiltersRule(),
    RedundantCheckoutRule(),
    MatrixDuplicatesRule(),
    MatrixFailFastRule(),
    DockerLayerCacheRule(),
    MissingShardingRule(),
    ExpensivePlatformRule(),
    OutdatedActionsRule(),
    SequentialNeedsRule(),
    SelfHostedCandidateRule(),
    DoubleTriggerRule(),
]


__all__ = ["ALL_RULES", "Rule", "RuleContext"]
