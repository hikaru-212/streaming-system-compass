"""PR5 experiment stimuli and logical trajectories; no production retry authority."""

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from random import Random

from experiments.load_capacity_protection.evidence import Cohort, LoadRunPlan
from experiments.load_capacity_protection.model import (
    LoadAcknowledgement, LoadCellIdentity, LoadCellObservation, LoadWorkItem,
)
from experiments.load_capacity_protection.pr4_model import (
    Protection, ProtectionMode, RequestObservation, VerificationEvidence,
)
from src.core.order.enums import CommandType
from src.storage.idempotency_store import RequestSignature


class RetryPolicy(str, Enum):
    NO_RETRY = "no_retry"
    IMMEDIATE_RETRY = "immediate_retry"
    FIXED_BACKOFF = "fixed_backoff"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    EXPONENTIAL_BACKOFF_WITH_JITTER = "exponential_backoff_with_jitter"


JITTER_ALGORITHM = "sha256-ascii-seed:index:attempt-mod-span-plus-one-v1"


@dataclass(frozen=True)
class RetryConfig:
    """Explicit per-request bound, including first attempt; unused parameters are None.

NO_RETRY requires max_attempts=1. Other policies may also use one as a bounded
degenerate case. Refusal on the last permitted attempt exhausts the experiment
budget; acceptance or any writer result/failure never consumes a further attempt.
"""

    policy: RetryPolicy
    max_attempts_per_logical_request: int
    fixed_delay_ns: int | None
    base_delay_ns: int | None
    backoff_cap_ns: int | None
    jitter_max_ns: int | None
    jitter_seed: int | None
    jitter_algorithm: str | None

    def __post_init__(self):
        if type(self.policy) is not RetryPolicy:
            raise TypeError("explicit RetryPolicy required")
        if type(self.max_attempts_per_logical_request) is not int or self.max_attempts_per_logical_request < 1:
            raise ValueError("explicit positive per-logical-request attempt bound required")
        if self.policy is RetryPolicy.NO_RETRY and self.max_attempts_per_logical_request != 1:
            raise ValueError("NO_RETRY requires exactly one attempt")
        used = set()
        if self.policy is RetryPolicy.FIXED_BACKOFF:
            used.add("fixed_delay_ns")
        if self.policy in (RetryPolicy.EXPONENTIAL_BACKOFF, RetryPolicy.EXPONENTIAL_BACKOFF_WITH_JITTER):
            used.update(("base_delay_ns", "backoff_cap_ns"))
        if self.policy is RetryPolicy.EXPONENTIAL_BACKOFF_WITH_JITTER:
            used.update(("jitter_max_ns", "jitter_seed", "jitter_algorithm"))
        for name in ("fixed_delay_ns", "base_delay_ns", "backoff_cap_ns", "jitter_max_ns",
                     "jitter_seed", "jitter_algorithm"):
            value = getattr(self, name)
            if name not in used:
                if value is not None:
                    raise ValueError("unused retry parameters must be explicitly absent")
            elif name == "jitter_algorithm":
                if value != JITTER_ALGORITHM:
                    raise ValueError("unsupported jitter algorithm")
            elif type(value) is not int or (name != "jitter_seed" and value < 0):
                raise ValueError("delay/span must be nonnegative integer ns; seed must be integer")
        if self.base_delay_ns is not None and self.backoff_cap_ns < self.base_delay_ns:
            raise ValueError("backoff cap must be at least base delay")


def seeded_jitter(seed: int, logical_request_index: int, attempt_index: int, span_ns: int) -> int:
    """Hash ASCII 'seed:index:attempt'; big-endian digest modulo (span_ns + 1).

This is bounded additive deterministic jitter, with possible modulo bias. It is
independent of thread interleaving and makes no statistical-uniformity claim.
"""
    raw = f"{seed}:{logical_request_index}:{attempt_index}".encode("ascii")
    return int.from_bytes(sha256(raw).digest(), "big") % (span_ns + 1)


def retry_delay_ns(config, logical_request_index, attempt_index, *, jitter_source=seeded_jitter):
    """Delay after 1-based refused attempt a: min(cap, base * 2**(a-1)) + jitter.

Return None if no further attempt is allowed. The exponential cap applies before
additive jitter; total delay is bounded by cap + jitter_max_ns. Avoid constructing
unbounded powers after reaching the explicitly configured cap.
"""
    config.__post_init__()
    if type(attempt_index) is not int or attempt_index < 1:
        raise ValueError("attempt index must be positive")
    if type(logical_request_index) is not int or logical_request_index < 0:
        raise ValueError("logical request index must be nonnegative")
    if attempt_index >= config.max_attempts_per_logical_request:
        return None
    if config.policy is RetryPolicy.IMMEDIATE_RETRY:
        return 0
    if config.policy is RetryPolicy.FIXED_BACKOFF:
        return config.fixed_delay_ns
    base, cap = config.base_delay_ns, config.backoff_cap_ns
    delay = (0 if base == 0 else cap if attempt_index - 1 >= cap.bit_length()
             else min(cap, base << (attempt_index - 1)))
    if config.policy is RetryPolicy.EXPONENTIAL_BACKOFF_WITH_JITTER:
        jitter = jitter_source(config.jitter_seed, logical_request_index, attempt_index, config.jitter_max_ns)
        if type(jitter) is not int or not 0 <= jitter <= config.jitter_max_ns:
            raise ValueError("jitter source exceeded declared span")
        delay += jitter
    return delay


@dataclass(frozen=True)
class RetryPlan(LoadRunPlan):
    """Same-source policy comparison; all numbers and order are caller supplied."""

    protection_bound: int
    policies: tuple[RetryConfig, ...]
    policy_order: str

    def __post_init__(self):
        super().__post_init__()
        Protection(ProtectionMode.PROTECTED, self.protection_bound)
        if type(self.policies) is not tuple or not self.policies:
            raise ValueError("explicit policies required")
        for config in self.policies:
            if type(config) is not RetryConfig:
                raise TypeError("RetryConfig required")
            config.__post_init__()
        kinds = [p.policy for p in self.policies]
        if len(set(kinds)) != len(kinds) or RetryPolicy.NO_RETRY not in kinds:
            raise ValueError("distinct policies including contemporaneous NO_RETRY required")
        if self.policy_order != "rotating_policy_blocks":
            raise ValueError("unsupported deterministic policy order")


@dataclass(frozen=True)
class ScheduledCell:
    identity: LoadCellIdentity
    cohort: Cohort
    retry: RetryConfig
    execution_index: int
    block_index: int
    position_in_block: int


def declared_cells(plan: RetryPlan) -> tuple[ScheduledCell, ...]:
    """Adjacent policy blocks rotate by (repetition + level_index) modulo P.

Warmup and recorded rotation both start at repetition zero. P recorded rounds
give every policy each position at each N. Partial rotations retain imbalance.
"""
    plan.__post_init__()
    result = []
    for cohort, count in ((Cohort.WARMUP, plan.warmups), (Cohort.RECORDED, plan.repetitions)):
        for repetition in range(count):
            for level, n in enumerate(plan.concurrency_levels):
                shift = (repetition + level) % len(plan.policies)
                policies = plan.policies[shift:] + plan.policies[:shift]
                block = len(result) // len(policies)
                for position, config in enumerate(policies):
                    result.append(ScheduledCell(LoadCellIdentity(
                        plan.run_id, f"pr5-level-{level}-{cohort.value}-{config.policy.value}", repetition, n,
                    ), cohort, config, len(result), block, position))
    return tuple(result)


def prepare_workload(plan, scheduled) -> tuple[LoadWorkItem, ...]:
    """Create each business identity once; attempts retain the same immutable item."""
    if scheduled not in declared_cells(plan):
        raise ValueError("undeclared PR5 cell")
    prefix = f"pr5-load:{plan.run_id}:{scheduled.identity.cell_id}:{scheduled.identity.repetition}"
    items = [LoadWorkItem(i, RequestSignature(
        f"{prefix}:request-{i}", CommandType.CREATE, f"{prefix}:order-{i}", plan.amount,
    )) for i in range(plan.k)]
    Random(plan.ordering_seed).shuffle(items)
    return tuple(items)


class LogicalTerminal(str, Enum):
    ACKNOWLEDGED_ACCEPTED = "acknowledged_accepted"
    RETRY_BUDGET_EXHAUSTED_AFTER_CAPACITY_REFUSAL = "retry_budget_exhausted_after_capacity_refusal"
    NATIVE_WRITER_FAILURE = "native_writer_failure"
    NON_ACCEPTED_WRITER_RESULT = "non_accepted_writer_result"
    INCOMPLETE = "incomplete"


@dataclass(frozen=True)
class AttemptEvidence:
    """A PR5 attempt identity plus unchanged safe PR4 call facts.

Scheduled timing is attached to the refused attempt; actual retry dispatch is
the next attempt's observation.dispatch_ns. A stop can leave a scheduled retry
unexecuted. No producer evidence is manufactured for that missing attempt.
"""

    attempt_index: int
    observation: RequestObservation
    scheduled_retry_delay_ns: int | None = None
    next_retry_eligible_ns: int | None = None

    def __post_init__(self):
        if type(self.attempt_index) is not int or self.attempt_index < 1:
            raise ValueError("positive 1-based attempt identity required")
        row = self.observation
        row.__post_init__()
        if row.protection.mode is not ProtectionMode.PROTECTED or row.verification is not None:
            raise ValueError("PR5 requires protected attempts; verification belongs to logical request")
        delay = self.scheduled_retry_delay_ns
        if delay is None:
            if self.next_retry_eligible_ns is not None:
                raise ValueError("eligibility requires delay")
        elif (type(delay) is not int or delay < 0 or row.capacity_refused_ns is None
              or row.terminal_observation_ns is None
              or self.next_retry_eligible_ns != row.capacity_refused_ns + delay):
            raise ValueError("retry requires terminal refusal and exact eligibility")


@dataclass(frozen=True)
class LogicalRequestEvidence:
    item: LoadWorkItem
    offer_ns: int | None
    attempts: tuple[AttemptEvidence, ...]
    terminal_state: LogicalTerminal
    final_terminal_ns: int | None
    verification: VerificationEvidence | None = None

    def __post_init__(self):
        if type(self.terminal_state) is not LogicalTerminal:
            raise TypeError("experiment logical state required")
        if self.offer_ns is not None and (type(self.offer_ns) is not int or self.offer_ns < 0):
            raise ValueError("invalid offer time")
        previous = None
        for index, attempt in enumerate(self.attempts, 1):
            attempt.__post_init__()
            row = attempt.observation
            if attempt.attempt_index != index or row.item != self.item or row.offer_ns != self.offer_ns:
                raise ValueError("attempt identity/signature/offer changed")
            if previous is not None:
                prior = previous.observation
                if (prior.capacity_refused_ns is None or prior.terminal_observation_ns is None
                        or previous.next_retry_eligible_ns is None or row.dispatch_ns is None
                        or row.dispatch_ns < max(prior.terminal_observation_ns, previous.next_retry_eligible_ns)
                        or row.lane_id != prior.lane_id):
                    raise ValueError("retry must follow eligible terminal refusal on the same lane")
            previous = attempt
        if self.final_terminal_ns is None:
            if self.terminal_state is not LogicalTerminal.INCOMPLETE:
                raise ValueError("terminal logical state requires final timestamp")
        else:
            if (type(self.final_terminal_ns) is not int or not self.attempts
                    or previous.observation.terminal_observation_ns is None
                    or self.final_terminal_ns < previous.observation.terminal_observation_ns
                    or previous.scheduled_retry_delay_ns is not None):
                raise ValueError("invalid logical terminal boundary")
            row = previous.observation
            expected = (
                LogicalTerminal.ACKNOWLEDGED_ACCEPTED
                if row.acknowledgement is LoadAcknowledgement.ACKNOWLEDGED_ACCEPTED
                else LogicalTerminal.RETRY_BUDGET_EXHAUSTED_AFTER_CAPACITY_REFUSAL
                if row.capacity_refused_ns is not None
                else LogicalTerminal.NATIVE_WRITER_FAILURE if row.failure is not None
                else LogicalTerminal.NON_ACCEPTED_WRITER_RESULT if row.result is not None
                else LogicalTerminal.INCOMPLETE
            )
            if self.terminal_state is not expected:
                raise ValueError("logical terminal state disagrees with attempt")

    @property
    def first_attempt_ns(self):
        return self.attempts[0].observation.dispatch_ns if self.attempts else None

    @property
    def completion_latency_ns(self):
        """Offer-to-final logical latency includes backlog and retry waiting."""
        return (self.final_terminal_ns - self.offer_ns
                if self.final_terminal_ns is not None and self.offer_ns is not None else None)


@dataclass(frozen=True)
class Characterization:
    identity: LoadCellIdentity
    protection: Protection
    retry: RetryConfig
    planned: tuple[LoadWorkItem, ...]
    logical_requests: tuple[LogicalRequestEvidence, ...]

    def __post_init__(self):
        LoadCellObservation(self.identity, self.planned)
        self.retry.__post_init__()
        if self.protection.mode is not ProtectionMode.PROTECTED:
            raise ValueError("PR5 requires real protected composition")
        if tuple(r.item for r in self.logical_requests) != self.planned:
            raise ValueError("every planned logical request must remain represented")
        offers, lanes = set(), {}
        for request in self.logical_requests:
            request.__post_init__()
            if request.offer_ns is not None:
                offers.add(request.offer_ns)
            if len(request.attempts) > self.retry.max_attempts_per_logical_request:
                raise ValueError("attempt budget exceeded")
            for attempt in request.attempts:
                row = attempt.observation
                if row.protection != self.protection:
                    raise ValueError("wrong protection")
                if row.lane_id is not None and row.lane_id >= self.identity.configured_concurrency:
                    raise ValueError("invalid lane identity")
                if attempt.scheduled_retry_delay_ns is not None and attempt.scheduled_retry_delay_ns != retry_delay_ns(
                    self.retry, request.item.workload_index, attempt.attempt_index,
                ):
                    raise ValueError("scheduled delay disagrees with policy")
            if request.terminal_state is LogicalTerminal.RETRY_BUDGET_EXHAUSTED_AFTER_CAPACITY_REFUSAL:
                if len(request.attempts) != self.retry.max_attempts_per_logical_request:
                    raise ValueError("refusal-only terminal requires exhausted budget")
            if request.attempts:
                first = request.attempts[0].observation
                last = request.attempts[-1].observation
                if first.dispatch_ns is not None:
                    lanes.setdefault(first.lane_id, []).append((first.dispatch_ns, request.final_terminal_ns
                                                               or last.terminal_observation_ns))
        if len(offers) > 1:
            raise ValueError("multiple offer boundaries")
        for intervals in lanes.values():
            intervals.sort()
            if any(a[1] is None or b[0] < a[1] for a, b in zip(intervals, intervals[1:])):
                raise ValueError("overlapping logical ownership on retained lane")

    @property
    def observations(self):
        """Flatten call facts for interval analysis without PR4 logical accounting."""
        return tuple(a.observation for r in self.logical_requests for a in r.attempts)


def empty_characterization(identity, protection, retry, workload):
    return Characterization(identity, protection, retry, workload, tuple(
        LogicalRequestEvidence(item, None, (), LogicalTerminal.INCOMPLETE, None) for item in workload
    ))
