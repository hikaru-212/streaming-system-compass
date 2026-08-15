"""Recorded runner for Stage 4B.5 runtime-governance overhead.

Canonical runs are deliberately gated. Importing this module, running its
non-database smoke command, or running its unit tests cannot write canonical
evidence or touch PostgreSQL. The PostgreSQL command additionally requires
``TEST_DATABASE_URL`` and verifies that ``current_database()`` ends in
``_test`` before any reset or workload execution.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from decimal import Decimal
import gc
import importlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence
from uuid import NAMESPACE_URL, uuid5

# Direct script execution adds only this file's directory to ``sys.path``.
# Add the verified repository root so the experiment package resolves exactly
# as it does under pytest and ``python -m`` execution.
_ENTRYPOINT_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(_ENTRYPOINT_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_ENTRYPOINT_REPOSITORY_ROOT))

from experiments.stage4b5.runtime_governance_overhead import (
    BOOTSTRAP_REPETITIONS,
    MICRO_CONFIG,
    MICRO_SCENARIOS,
    POSTGRES_CONFIG,
    POSTGRES_SCENARIOS,
    REPOSITORY_ROOT,
    SCHEMA_LEVEL,
    SCHEMA_VERSION,
    SEQUENCE_RULE_ID,
    TIMER,
    Command,
    Layer,
    Placement,
    Sample,
    Scenario,
    Surface,
    Terminal,
    aggregate_evidence,
    compute_batch_comparisons,
    compute_batch_summaries,
    current_source_identity,
    environment_facts,
    fixed_surface_permutations,
    install_verified_historical_modules,
    load_and_verify_a_source_provenance,
    scenario_by_name,
    validate_recorded_population,
    validate_run_id,
    write_immutable_evidence,
)


TEST_DATABASE_URL_ENV = "TEST_DATABASE_URL"
CANONICAL_CONFIRMATION = "I_UNDERSTAND_THIS_IS_A_FIXED_RECORDED_RUN"
AMOUNT = Decimal("100.00")
EVIDENCE_ROOT = REPOSITORY_ROOT / "experiments" / "stage4b5" / "evidence"
MICRO_EVIDENCE_ROOT = EVIDENCE_ROOT / "runtime-governance-overhead-micro"
POSTGRES_EVIDENCE_ROOT = EVIDENCE_ROOT / "runtime-governance-overhead-postgres"

_RESET_TABLES_SQL = """
TRUNCATE
    decision_receipts,
    projection_snapshots,
    projection_order_progress,
    projection_checkpoints,
    projection_states,
    idempotency_records,
    order_events
RESTART IDENTITY CASCADE
"""

_REQUIRED_TABLES = frozenset(
    {
        "decision_receipts",
        "projection_snapshots",
        "projection_order_progress",
        "projection_checkpoints",
        "projection_states",
        "idempotency_records",
        "order_events",
    }
)


class RecordedRunError(RuntimeError):
    """Raised when a recorded run cannot preserve its evidence contract."""


def running_in_virtual_environment() -> bool:
    """Return whether this interpreter is isolated by venv or virtualenv."""

    return (
        sys.prefix != getattr(sys, "base_prefix", sys.prefix)
        or hasattr(sys, "real_prefix")
    )


def require_test_database_name(database_name: object) -> str:
    """Return a verified test database name or refuse destructive execution."""

    if not isinstance(database_name, str) or not database_name.endswith("_test"):
        raise RecordedRunError(
            "refusing destructive benchmark against a database whose name "
            "does not end in _test"
        )
    return database_name


class _WorkerRuntime:
    """Own one isolated A, B, or C production import graph and DB connection."""

    def __init__(self, surface: Surface) -> None:
        self.surface = surface
        self.a_provenance: dict[str, Any] | None = None
        if surface is Surface.A:
            self.a_provenance = install_verified_historical_modules()

        self._runtime_module = importlib.import_module(
            "src.compass.transition.runtime"
        )
        self._validators_module = importlib.import_module(
            "src.compass.transition.validators"
        )
        self._types_module = importlib.import_module(
            "src.compass.transition.types"
        )
        self._writer_module = importlib.import_module(
            "src.pipeline.transactional.postgres_write_side"
        )
        self._connection = None
        self._writers: dict[tuple[Placement, Terminal], Any] = {}

        if surface is Surface.C:
            feedback_module = importlib.import_module(
                "src.compass.runtime.write_side_rule_feedback"
            )
            self._map_feedback = (
                feedback_module
                .map_postgres_write_side_result_to_semantic_rule_feedback
            )
        else:
            self._map_feedback = None

    def hello(self) -> dict[str, Any]:
        """Return non-secret process identity and source-mode facts."""

        return {
            "surface": self.surface.value,
            "python_executable": sys.executable,
            "python_version": sys.version.split()[0],
            "python_implementation": platform.python_implementation(),
            "garbage_collection_enabled": gc.isenabled(),
            "a_source_provenance": self.a_provenance,
            "protected_module_files": {
                "validators": self._validators_module.__file__,
                "runtime": self._runtime_module.__file__,
                "postgres_write_side": self._writer_module.__file__,
            },
        }

    def _build_runtime(self) -> Any:
        return self._runtime_module.ValidationRuntime(
            dispatcher=self._runtime_module.ValidationDispatcher(
                strict_validator=self._validators_module.FullProofValidator(),
                off_validator=self._validators_module.NoOpValidator(),
            ),
            policy=self._runtime_module.ValidationPolicy(),
            mode=self._types_module.ValidationMode.STRICT,
        )

    def _micro_inputs(self, scenario: Scenario, token: str) -> tuple[Any, Any]:
        aggregate_module = importlib.import_module("src.core.order.aggregate")
        order_status_module = importlib.import_module("src.core.order.enums")
        aggregate = aggregate_module.OrderAggregate(f"micro-order-{token}")
        if scenario.command is Command.CREATE:
            candidate = aggregate.create(f"micro-create-{token}", AMOUNT)
            context = self._types_module.ValidationContext(
                actual_prev_event=None,
                actual_prev_version=0,
                actual_prev_status=order_status_module.OrderStatus.INIT,
            )
        else:
            created = aggregate.create(f"micro-seed-{token}", AMOUNT)
            aggregate.apply(created)
            candidate = aggregate.pay(f"micro-pay-{token}", AMOUNT)
            context = self._types_module.ValidationContext(
                actual_prev_event=created,
                actual_prev_version=aggregate.current_version,
                actual_prev_status=aggregate.status,
            )
        if scenario.terminal is Terminal.VALIDATION_BLOCKED:
            context = replace(
                context,
                actual_prev_version=context.actual_prev_version + 1,
            )
        return candidate, context

    def _micro_result(
        self,
        *,
        candidate: Any,
        context: Any,
        outcome_id: Any,
    ) -> tuple[dict[str, int | None], tuple[Any, Any]]:
        admission_module = importlib.import_module(
            "src.pipeline.transactional.admission"
        )
        idempotency_module = importlib.import_module(
            "src.storage.idempotency_store"
        )
        runtime = self._build_runtime()
        start_ns = time.perf_counter_ns()
        if self.surface is Surface.A:
            decision = runtime.decide(candidate, context)
            carrier = None
        else:
            carrier = runtime.decide_with_rule_evidence(candidate, context)
            decision = carrier.decision

        allowed = decision.action is self._types_module.EnforcementAction.ALLOW
        if allowed:
            outcome = self._writer_module.PostgresWriteSideOutcome.ACCEPTED
            stream_admission = admission_module.StreamAdmissionResult(
                verdict=admission_module.AdmissionVerdict.ADMITTED,
                reason="benchmark accepted stream preparation",
                order_id=candidate.order_id,
            )
            append_admission = admission_module.AdmissionResult(
                verdict=admission_module.AdmissionVerdict.ADMITTED,
                reason="benchmark accepted append admission",
                candidate_event_id=candidate.event_id,
                accepted_event_id=candidate.event_id,
            )
            accepted_event = candidate
        else:
            outcome = self._writer_module.PostgresWriteSideOutcome.VALIDATION_BLOCKED
            stream_admission = None
            append_admission = None
            accepted_event = None

        result_kwargs = {
            "outcome": outcome,
            "accepted_event": accepted_event,
            "idempotency_decision": idempotency_module.IdempotencyDecision(
                verdict=idempotency_module.IdempotencyVerdict.MISS,
                reason="benchmark idempotency miss",
            ),
            "stream_admission_result": stream_admission,
            "validation_decision": decision,
            "admission_result": append_admission,
        }
        if self.surface is not Surface.A:
            result_kwargs["validation_decision_evidence"] = carrier
        result = self._writer_module.PostgresWriteSideResult(**result_kwargs)
        producer_return_ns = time.perf_counter_ns()
        feedback = None
        if self.surface is Surface.C:
            feedback = self._map_feedback(outcome_id=outcome_id, result=result)
            stop_ns = time.perf_counter_ns()
            composition_elapsed_ns = stop_ns - producer_return_ns
        else:
            stop_ns = producer_return_ns
            composition_elapsed_ns = None
        timing = {
            "producer_elapsed_ns": producer_return_ns - start_ns,
            "composition_elapsed_ns": composition_elapsed_ns,
            "total_elapsed_ns": stop_ns - start_ns,
        }
        return timing, (result, feedback)

    def micro_batch(
        self,
        scenario_name: str,
        count: int,
        token_prefix: str,
    ) -> list[dict[str, Any]]:
        """Execute a micro batch with setup and verification outside each timer."""

        scenario = scenario_by_name(Layer.MICRO, scenario_name)
        observations: list[dict[str, Any]] = []
        for repetition in range(count):
            token = f"{token_prefix}-{repetition}"
            candidate, context = self._micro_inputs(scenario, token)
            outcome_id = uuid5(NAMESPACE_URL, f"stage4b5:{token}")
            timing, (result, feedback) = self._micro_result(
                candidate=candidate,
                context=context,
                outcome_id=outcome_id,
            )
            observations.append(
                self._verify_result(
                    scenario=scenario,
                    result=result,
                    feedback=feedback,
                    timing=timing,
                )
            )
        return observations

    def _verify_result(
        self,
        *,
        scenario: Scenario,
        result: Any,
        feedback: Any,
        timing: Mapping[str, Any],
    ) -> dict[str, Any]:
        expected_outcome = getattr(
            self._writer_module.PostgresWriteSideOutcome,
            scenario.terminal.value,
        )
        if result.outcome is not expected_outcome:
            raise RecordedRunError("producer outcome did not match scenario")

        rule_id = None
        if self.surface is Surface.A:
            if hasattr(result, "validation_decision_evidence") or hasattr(
                result, "observed_rule_violation"
            ):
                raise RecordedRunError("A unexpectedly exposed Stage 4B.5 evidence")
        else:
            carrier = result.validation_decision_evidence
            if carrier is None or result.validation_decision is not carrier.decision:
                raise RecordedRunError("B/C did not preserve the runtime carrier")
            violation = result.observed_rule_violation
            if scenario.terminal is Terminal.VALIDATION_BLOCKED:
                if violation is None or violation.rule_id.value != SEQUENCE_RULE_ID:
                    raise RecordedRunError("B/C did not expose exact sequence-rule evidence")
                rule_id = violation.rule_id.value
            elif violation is not None:
                raise RecordedRunError("accepted B/C result carried false rule evidence")

            if self.surface is Surface.C:
                if feedback is None:
                    raise RecordedRunError("C did not execute terminal composition")
                if scenario.terminal is Terminal.VALIDATION_BLOCKED:
                    if feedback.rule_refinement is not violation:
                        raise RecordedRunError("C did not preserve exact rule refinement")
                elif feedback.rule_refinement is not None:
                    raise RecordedRunError("C produced false terminal refinement")
            elif feedback is not None:
                raise RecordedRunError("B must end at PostgresWriteSideResult")

        producer_elapsed_ns = timing["producer_elapsed_ns"]
        composition_elapsed_ns = timing["composition_elapsed_ns"]
        total_elapsed_ns = timing["total_elapsed_ns"]
        if type(producer_elapsed_ns) is not int or producer_elapsed_ns <= 0:
            raise RecordedRunError("producer timer did not produce a positive int")
        if type(total_elapsed_ns) is not int or total_elapsed_ns <= 0:
            raise RecordedRunError("total timer did not produce a positive int")
        if self.surface is Surface.C:
            if (
                type(composition_elapsed_ns) is not int
                or composition_elapsed_ns < 0
            ):
                raise RecordedRunError("C composition lap is invalid")
            if total_elapsed_ns != producer_elapsed_ns + composition_elapsed_ns:
                raise RecordedRunError("C timing laps do not sum to total")
        elif composition_elapsed_ns is not None or total_elapsed_ns != producer_elapsed_ns:
            raise RecordedRunError("A/B timing shape is invalid")
        return {
            "producer_elapsed_ns": producer_elapsed_ns,
            "composition_elapsed_ns": composition_elapsed_ns,
            "total_elapsed_ns": total_elapsed_ns,
            "producer_outcome": result.outcome.value,
            "rule_id": rule_id,
        }

    def open_postgres(self) -> dict[str, Any]:
        """Open and guard the caller-provided test database connection."""

        if self._connection is not None:
            raise RecordedRunError("PostgreSQL connection already open")
        database_url = os.environ.get(TEST_DATABASE_URL_ENV)
        if not database_url:
            raise RecordedRunError("test database environment is missing")

        psycopg = importlib.import_module("psycopg")
        connection = psycopg.connect(database_url, connect_timeout=10)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT current_database(), oid FROM pg_database "
                    "WHERE datname = current_database()"
                )
                database_name, database_oid = cursor.fetchone()
                cursor.execute("SHOW server_version_num")
                postgres_version_num = cursor.fetchone()[0]
                cursor.execute("SHOW transaction_isolation")
                transaction_isolation = cursor.fetchone()[0]
                cursor.execute(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
                )
                tables = {row[0] for row in cursor.fetchall()}
            connection.rollback()
            require_test_database_name(database_name)
            missing = sorted(_REQUIRED_TABLES - tables)
            if missing:
                raise RecordedRunError(
                    "test database is below the required migration level: "
                    + ", ".join(missing)
                )
            if connection.autocommit:
                raise RecordedRunError("benchmark requires autocommit disabled")
            self._connection = connection
            self._writers = self._build_writers()
            return {
                "database_guard": "current_database suffix _test verified",
                "database_oid": database_oid,
                "postgres_version_num": postgres_version_num,
                "psycopg_version": psycopg.__version__,
                "transaction_isolation": transaction_isolation,
                "autocommit": connection.autocommit,
                "schema_level": SCHEMA_LEVEL,
                "required_tables_verified": sorted(_REQUIRED_TABLES),
            }
        except BaseException:
            connection.close()
            raise

    def _build_writers(self) -> dict[tuple[Placement, Terminal], Any]:
        config_module = importlib.import_module(
            "src.pipeline.transactional.postgres_write_side_config"
        )
        admission_module = importlib.import_module(
            "src.pipeline.transactional.postgres_admission"
        )
        base_writer = self._writer_module.PostgresTransactionalWriteSide

        class _SequenceMismatchWriteSide(base_writer):
            """Benchmark-only context perturbation common to A/B/C."""

            def _build_validation_context(inner_self, *, aggregate, actual_prev_event):
                context = super()._build_validation_context(
                    aggregate=aggregate,
                    actual_prev_event=actual_prev_event,
                )
                return replace(
                    context,
                    actual_prev_version=context.actual_prev_version + 1,
                )

        def pessimistic_gate_factory(uow):
            return admission_module.PostgresPessimisticAdmissionGate(
                connection=uow.connection,
                event_store=uow.event_store,
            )

        writers: dict[tuple[Placement, Terminal], Any] = {}
        for placement in Placement:
            production_placement = getattr(
                config_module.ValidationPlacement,
                placement.value,
            )
            factory = (
                pessimistic_gate_factory
                if placement is Placement.IN_TRANSACTION
                else None
            )
            for terminal in Terminal:
                writer_type = (
                    base_writer
                    if terminal is Terminal.ACCEPTED
                    else _SequenceMismatchWriteSide
                )
                writers[(placement, terminal)] = writer_type(
                    connection=self._connection,
                    validation_runtime=self._build_runtime(),
                    admission_gate_factory=factory,
                    config=config_module.PostgresWriteSideConfig(
                        validation_placement=production_placement,
                    ),
                )
        return writers

    def reset_postgres(self) -> None:
        """Reset the guarded test database outside every timing boundary."""

        connection = self._require_connection()
        self._require_idle(connection, "before reset")
        with connection.cursor() as cursor:
            cursor.execute(_RESET_TABLES_SQL)
        connection.commit()
        self._require_idle(connection, "after reset")

    def _require_connection(self) -> Any:
        if self._connection is None:
            raise RecordedRunError("PostgreSQL connection is not open")
        return self._connection

    @staticmethod
    def _require_idle(connection: Any, location: str) -> None:
        status = connection.info.transaction_status.name
        if status != "IDLE":
            raise RecordedRunError(f"connection not IDLE {location}")

    def _seed_pay(self, *, placement: Placement, token: str) -> str:
        writer = self._writers[(placement, Terminal.ACCEPTED)]
        order_id = f"stage4b5-order-{token}"
        result = writer.create_order(
            request_id=f"stage4b5-seed-{token}",
            order_id=order_id,
            amount=AMOUNT,
        )
        if result.outcome is not self._writer_module.PostgresWriteSideOutcome.ACCEPTED:
            raise RecordedRunError("PAY setup did not produce accepted history")
        self._require_idle(self._connection, "after PAY setup")
        return order_id

    def postgres_batch(
        self,
        scenario_name: str,
        count: int,
        token_prefix: str,
    ) -> list[dict[str, Any]]:
        """Execute normal production APIs under one external timing boundary."""

        scenario = scenario_by_name(Layer.POSTGRES, scenario_name)
        assert scenario.placement is not None
        connection = self._require_connection()
        writer = self._writers[(scenario.placement, scenario.terminal)]
        observations: list[dict[str, Any]] = []
        for repetition in range(count):
            token = f"{token_prefix}-{repetition}"
            if scenario.command is Command.PAY:
                order_id = self._seed_pay(
                    placement=scenario.placement,
                    token=token,
                )
                method = writer.pay_order
                request_id = f"stage4b5-pay-{token}"
            else:
                order_id = f"stage4b5-order-{token}"
                method = writer.create_order
                request_id = f"stage4b5-create-{token}"
            outcome_id = uuid5(NAMESPACE_URL, f"stage4b5:{token}")

            self._require_idle(connection, "before timed invocation")
            start_ns = time.perf_counter_ns()
            result = method(
                request_id=request_id,
                order_id=order_id,
                amount=AMOUNT,
            )
            producer_return_ns = time.perf_counter_ns()
            feedback = None
            if self.surface is Surface.C:
                feedback = self._map_feedback(
                    outcome_id=outcome_id,
                    result=result,
                )
                stop_ns = time.perf_counter_ns()
                composition_elapsed_ns = stop_ns - producer_return_ns
            else:
                stop_ns = producer_return_ns
                composition_elapsed_ns = None
            self._require_idle(connection, "after producer return")

            observation = self._verify_result(
                scenario=scenario,
                result=result,
                feedback=feedback,
                timing={
                    "producer_elapsed_ns": producer_return_ns - start_ns,
                    "composition_elapsed_ns": composition_elapsed_ns,
                    "total_elapsed_ns": stop_ns - start_ns,
                },
            )
            self._verify_history(scenario=scenario, order_id=order_id)
            observations.append(observation)
        return observations

    def _verify_history(self, *, scenario: Scenario, order_id: str) -> None:
        """Verify durable acceptance/blocking outside the timed region."""

        connection = self._require_connection()
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT event_type FROM order_events WHERE order_id = %s "
                "ORDER BY sequence",
                (order_id,),
            )
            event_types = [row[0] for row in cursor.fetchall()]
        connection.rollback()
        expected: list[str] = []
        if scenario.command is Command.PAY:
            expected.append("CREATED")
        if scenario.terminal is Terminal.ACCEPTED:
            expected.append(
                "CREATED" if scenario.command is Command.CREATE else "PAID"
            )
        if event_types != expected:
            raise RecordedRunError("durable history did not match scenario")
        self._require_idle(connection, "after durable verification")

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None
            self._writers = {}


def _worker_main(surface: Surface) -> int:
    """Serve a line-delimited JSON protocol without emitting secret values."""

    try:
        worker = _WorkerRuntime(surface)
    except BaseException as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error_type": type(exc).__name__,
                    "error": "worker initialization failed",
                }
            ),
            flush=True,
        )
        return 2

    for line in sys.stdin:
        try:
            request = json.loads(line)
            operation = request["operation"]
            if operation == "hello":
                payload = worker.hello()
            elif operation == "micro_batch":
                payload = worker.micro_batch(
                    request["scenario"],
                    request["count"],
                    request["token_prefix"],
                )
            elif operation == "postgres_open":
                payload = worker.open_postgres()
            elif operation == "postgres_reset":
                worker.reset_postgres()
                payload = {"reset": "complete"}
            elif operation == "postgres_batch":
                payload = worker.postgres_batch(
                    request["scenario"],
                    request["count"],
                    request["token_prefix"],
                )
            elif operation == "close":
                worker.close()
                print(
                    json.dumps({"ok": True, "payload": {"closed": True}}),
                    flush=True,
                )
                return 0
            else:
                raise RecordedRunError("unknown worker operation")
            response = {"ok": True, "payload": payload}
        except BaseException as exc:
            response = {
                "ok": False,
                "error_type": type(exc).__name__,
                "error": "worker operation failed without exposing exception text",
            }
        print(json.dumps(response, separators=(",", ":")), flush=True)
    worker.close()
    return 0


class _WorkerClient:
    """Parent-side client for one isolated source surface."""

    def __init__(self, surface: Surface) -> None:
        self.surface = surface
        self._process = subprocess.Popen(
            (
                sys.executable,
                str(Path(__file__).resolve()),
                "_worker",
                "--surface",
                surface.value,
            ),
            cwd=REPOSITORY_ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=os.environ.copy(),
        )

    def request(self, operation: str, **arguments: Any) -> Any:
        if self._process.stdin is None or self._process.stdout is None:
            raise RecordedRunError("worker pipes unavailable")
        self._process.stdin.write(
            json.dumps({"operation": operation, **arguments}, separators=(",", ":"))
            + "\n"
        )
        self._process.stdin.flush()
        line = self._process.stdout.readline()
        if not line:
            raise RecordedRunError(f"{self.surface.value} worker exited unexpectedly")
        response = json.loads(line)
        if not response.get("ok"):
            raise RecordedRunError(
                f"{self.surface.value} worker failed: {response.get('error_type', 'unknown')}"
            )
        return response["payload"]

    def close(self) -> None:
        if self._process.poll() is None:
            try:
                self.request("close")
            except RecordedRunError:
                self._process.terminate()
        try:
            self._process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self._process.terminate()
            self._process.wait(timeout=10)


def _open_workers() -> dict[Surface, _WorkerClient]:
    workers: dict[Surface, _WorkerClient] = {}
    try:
        for surface in Surface:
            workers[surface] = _WorkerClient(surface)
        return workers
    except BaseException:
        for worker in workers.values():
            worker.close()
        raise


def _close_workers(workers: Mapping[Surface, _WorkerClient]) -> None:
    for worker in workers.values():
        worker.close()


def _sample_from_observation(
    *,
    run_id: str,
    layer: Layer,
    scenario: Scenario,
    surface: Surface,
    block_index: int,
    permutation_index: int,
    repetition_index: int,
    observation: Mapping[str, Any],
) -> Sample:
    return Sample(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        layer=layer.value,
        scenario=scenario.name,
        surface=surface.value,
        block_index=block_index,
        permutation_index=permutation_index,
        repetition_index=repetition_index,
        producer_elapsed_ns=observation["producer_elapsed_ns"],
        composition_elapsed_ns=observation["composition_elapsed_ns"],
        total_elapsed_ns=observation["total_elapsed_ns"],
        producer_outcome=observation["producer_outcome"],
        rule_id=observation["rule_id"],
    )


def _invoke_batch(
    *,
    worker: _WorkerClient,
    layer: Layer,
    scenario: Scenario,
    count: int,
    token_prefix: str,
) -> Sequence[Mapping[str, Any]]:
    operation = "micro_batch" if layer is Layer.MICRO else "postgres_batch"
    observations = worker.request(
        operation,
        scenario=scenario.name,
        count=count,
        token_prefix=token_prefix,
    )
    if not isinstance(observations, list) or len(observations) != count:
        raise RecordedRunError("worker returned an incomplete batch")
    return observations


def _run_micro_schedule(
    *,
    workers: Mapping[Surface, _WorkerClient],
    run_id: str,
) -> list[Sample]:
    permutations = fixed_surface_permutations(MICRO_CONFIG.schedule_seed)
    for warmup in range(MICRO_CONFIG.warmups):
        for scenario in MICRO_SCENARIOS:
            for permutation_index, permutation in enumerate(permutations):
                for surface in permutation:
                    _invoke_batch(
                        worker=workers[surface],
                        layer=Layer.MICRO,
                        scenario=scenario,
                        count=MICRO_CONFIG.repetitions_per_permutation,
                        token_prefix=(
                            f"warmup-{warmup}-{scenario.name}-{permutation_index}-"
                            f"{surface.value}"
                        ),
                    )

    samples: list[Sample] = []
    for block in range(MICRO_CONFIG.recorded_blocks):
        for scenario in MICRO_SCENARIOS:
            for permutation_index, permutation in enumerate(permutations):
                for surface in permutation:
                    observations = _invoke_batch(
                        worker=workers[surface],
                        layer=Layer.MICRO,
                        scenario=scenario,
                        count=MICRO_CONFIG.repetitions_per_permutation,
                        token_prefix=(
                            f"recorded-{run_id}-{block}-{scenario.name}-"
                            f"{permutation_index}-{surface.value}"
                        ),
                    )
                    samples.extend(
                        _sample_from_observation(
                            run_id=run_id,
                            layer=Layer.MICRO,
                            scenario=scenario,
                            surface=surface,
                            block_index=block,
                            permutation_index=permutation_index,
                            repetition_index=repetition,
                            observation=observation,
                        )
                        for repetition, observation in enumerate(observations)
                    )
    return samples


def _run_postgres_schedule(
    *,
    workers: Mapping[Surface, _WorkerClient],
    run_id: str,
) -> tuple[list[Sample], dict[str, Any]]:
    database_facts = {
        surface.value: workers[surface].request("postgres_open")
        for surface in Surface
    }
    comparable_fields = (
        "database_oid",
        "postgres_version_num",
        "psycopg_version",
        "transaction_isolation",
        "autocommit",
        "schema_level",
    )
    first = database_facts[Surface.A.value]
    for facts in database_facts.values():
        for field in comparable_fields:
            if facts[field] != first[field]:
                raise RecordedRunError(f"A/B/C PostgreSQL fact mismatch: {field}")

    permutations = fixed_surface_permutations(POSTGRES_CONFIG.schedule_seed)
    samples: list[Sample] = []
    try:
        for warmup in range(POSTGRES_CONFIG.warmups):
            workers[Surface.A].request("postgres_reset")
            permutation = permutations[warmup % len(permutations)]
            for scenario in POSTGRES_SCENARIOS:
                for surface in permutation:
                    _invoke_batch(
                        worker=workers[surface],
                        layer=Layer.POSTGRES,
                        scenario=scenario,
                        count=1,
                        token_prefix=(
                            f"warmup-{warmup}-{scenario.name}-{surface.value}"
                        ),
                    )

        for block in range(POSTGRES_CONFIG.recorded_blocks):
            workers[Surface.A].request("postgres_reset")
            for scenario in POSTGRES_SCENARIOS:
                for permutation_index, permutation in enumerate(permutations):
                    for surface in permutation:
                        observations = _invoke_batch(
                            worker=workers[surface],
                            layer=Layer.POSTGRES,
                            scenario=scenario,
                            count=POSTGRES_CONFIG.repetitions_per_permutation,
                            token_prefix=(
                                f"recorded-{run_id}-{block}-{scenario.name}-"
                                f"{permutation_index}-{surface.value}"
                            ),
                        )
                        samples.extend(
                            _sample_from_observation(
                                run_id=run_id,
                                layer=Layer.POSTGRES,
                                scenario=scenario,
                                surface=surface,
                                block_index=block,
                                permutation_index=permutation_index,
                                repetition_index=repetition,
                                observation=observation,
                            )
                            for repetition, observation in enumerate(
                                observations
                            )
                        )
    except BaseException:
        try:
            workers[Surface.A].request("postgres_reset")
        except BaseException:
            pass
        raise
    workers[Surface.A].request("postgres_reset")
    return samples, database_facts


def _scenario_manifest(scenarios: Sequence[Scenario]) -> list[dict[str, Any]]:
    return [
        {
            "name": scenario.name,
            "command": scenario.command.value,
            "terminal": scenario.terminal.value,
            "placement": (
                None if scenario.placement is None else scenario.placement.value
            ),
            "blocked_perturbation": (
                "accepted-history ValidationContext.actual_prev_version + 1"
                if scenario.terminal is Terminal.VALIDATION_BLOCKED
                else None
            ),
        }
        for scenario in scenarios
    ]


def _schedule_manifest(config: Any) -> dict[str, Any]:
    permutation_count = len(fixed_surface_permutations(config.schedule_seed))
    return {
        "warmup_blocks_or_cycles": config.warmups,
        "recorded_blocks": config.recorded_blocks,
        "surface_permutations": [
            [surface.value for surface in permutation]
            for permutation in fixed_surface_permutations(config.schedule_seed)
        ],
        "repetitions_per_permutation": config.repetitions_per_permutation,
        "comparison_units_per_scenario": (
            config.recorded_blocks * permutation_count
        ),
        "schedule_seed": config.schedule_seed,
        "adaptive_extension": False,
    }


def _manifest(
    *,
    run_id: str,
    layer: Layer,
    worker_hello: Mapping[str, Any],
    database_facts: Mapping[str, Any] | None,
) -> dict[str, Any]:
    scenarios = MICRO_SCENARIOS if layer is Layer.MICRO else POSTGRES_SCENARIOS
    config = MICRO_CONFIG if layer is Layer.MICRO else POSTGRES_CONFIG
    return {
        "schema": "stage4b5-runtime-governance-overhead-run",
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "layer": layer.value,
        "source_identities": {
            "A": load_and_verify_a_source_provenance(),
            "B_C": current_source_identity(),
            "worker_processes": worker_hello,
            "shared_transitive_import_basis": (
                "source-diff audit found protected execution-closure changes only "
                "in the three A-pinned modules; normal APIs do not import the "
                "separately changed Stage 4B.2 measurement module"
            ),
        },
        "environment": environment_facts(),
        "postgresql": database_facts,
        "timer": TIMER,
        "schema_level": SCHEMA_LEVEL,
        "scenario_definitions": _scenario_manifest(scenarios),
        "schedule": _schedule_manifest(config),
        "statistics": {
            "percentiles": "empirical nearest-rank",
            "raw_micro_absolute_percentiles": [50, 95, 99],
            "raw_postgres_absolute_percentiles": [50, 95],
            "batch_comparison_percentiles": [50, 95],
            "postgres_p99": (
                "withheld because the fixed per-cell population does not meet "
                "the predeclared credibility threshold"
            ),
            "dispersion": ["IQR", "MAD", "per-block median variation"],
            "experimental_pairing_unit": (
                "recorded block/permutation batch median; repetition indexes "
                "across independently executed surfaces are not paired"
            ),
            "comparison_semantics": {
                "B-A_END_TO_END": (
                    "difference of matched A/B block-permutation batch medians"
                ),
                "C-B_COMPOSITION_LAP": (
                    "primary direct same-invocation C composition lap"
                ),
                "C-A_END_TO_END": (
                    "difference of matched A/C block-permutation batch medians"
                ),
                "C-B_TOTAL_SECONDARY": (
                    "secondary noise-sensitive difference of independent full-path "
                    "B/C batch medians"
                ),
            },
            "batch_comparison_p99": (
                "withheld because each scenario/comparison has 180 batch units"
            ),
            "bootstrap": {
                "method": "fixed-seed bootstrap of recorded-block medians",
                "repetitions": BOOTSTRAP_REPETITIONS,
            },
        },
        "timing_boundaries": {
            "A": (
                "historical ValidationRuntime/write invocation through historical "
                "PostgresWriteSideResult return"
            ),
            "B": (
                "current evidence-aware ValidationRuntime/write invocation through "
                "current PostgresWriteSideResult return"
            ),
            "C": (
                "start -> current normal producer -> producer_return lap -> "
                "map_postgres_write_side_result_to_semantic_rule_feedback -> stop"
            ),
            "C_fields": (
                "producer_elapsed_ns, composition_elapsed_ns, total_elapsed_ns; "
                "the first two sum exactly to total_elapsed_ns"
            ),
            "postgres_timer_location": (
                "external time.perf_counter_ns around normal unmeasured production API"
            ),
            "excluded": [
                "candidate/setup construction",
                "PAY accepted-history seeding",
                "database reset",
                "verification",
                "YAML parsing or projection",
            ],
        },
        "environment_limitations": [
            "historical committed Stage 4B.2 values are context only and are not subtracted",
            "A shares audited-unchanged transitive modules from the current checkout",
            "A/B/C run in separate processes, so process-level jitter remains measurement noise",
            "independent C-B full-path subtraction is secondary and not the "
            "primary composition estimate",
            "single-host PostgreSQL results remain specific to the recorded machine and database",
            "the deterministic blocked context perturbation is benchmark-owned "
            "and equal across A/B/C",
        ],
    }


def _require_canonical_preconditions(confirmation: str) -> dict[str, Any]:
    if confirmation != CANONICAL_CONFIRMATION:
        raise RecordedRunError(
            "canonical run requires the exact --confirm value documented by --help"
        )
    source = current_source_identity()
    if not source["working_tree_clean"]:
        raise RecordedRunError("canonical evidence requires a clean working tree")
    if not running_in_virtual_environment():
        raise RecordedRunError(
            "canonical run requires execution inside a Python virtual environment"
        )
    return source


def _run_canonical(*, layer: Layer, run_id: str, confirmation: str) -> Path:
    try:
        validate_run_id(run_id)
    except ValueError as exc:
        raise RecordedRunError(str(exc)) from exc
    _require_canonical_preconditions(confirmation)
    if layer is Layer.POSTGRES and not os.environ.get(TEST_DATABASE_URL_ENV):
        raise RecordedRunError("PostgreSQL run requires test database environment")

    output_root = (
        MICRO_EVIDENCE_ROOT if layer is Layer.MICRO else POSTGRES_EVIDENCE_ROOT
    )
    if (output_root / run_id).exists():
        raise RecordedRunError("evidence namespace already exists")

    workers = _open_workers()
    try:
        worker_hello = {
            surface.value: workers[surface].request("hello")
            for surface in Surface
        }
        expected_worker_facts = {
            "python_executable": sys.executable,
            "python_version": sys.version.split()[0],
            "python_implementation": platform.python_implementation(),
            "garbage_collection_enabled": gc.isenabled(),
        }
        for hello in worker_hello.values():
            for field, expected in expected_worker_facts.items():
                if hello[field] != expected:
                    raise RecordedRunError(
                        f"A/B/C worker environment mismatch: {field}"
                    )
        if layer is Layer.MICRO:
            samples = _run_micro_schedule(workers=workers, run_id=run_id)
            database_facts = None
            scenarios = MICRO_SCENARIOS
            config = MICRO_CONFIG
        else:
            samples, database_facts = _run_postgres_schedule(
                workers=workers,
                run_id=run_id,
            )
            scenarios = POSTGRES_SCENARIOS
            config = POSTGRES_CONFIG
    finally:
        _close_workers(workers)

    validate_recorded_population(
        samples=samples,
        scenarios=scenarios,
        config=config,
        run_id=run_id,
    )
    batch_summaries = compute_batch_summaries(samples, config=config)
    batch_comparisons = compute_batch_comparisons(batch_summaries)
    comparison_units = (
        len(scenarios)
        * config.recorded_blocks
        * len(fixed_surface_permutations(config.schedule_seed))
    )
    if len(batch_summaries) != comparison_units * len(Surface):
        raise RecordedRunError("batch-summary population mismatch")
    if len(batch_comparisons) != comparison_units * 4:
        raise RecordedRunError("batch-comparison population mismatch")
    aggregates = aggregate_evidence(
        samples,
        batch_summaries,
        batch_comparisons,
        layer=layer,
    )
    manifest = _manifest(
        run_id=run_id,
        layer=layer,
        worker_hello=worker_hello,
        database_facts=database_facts,
    )
    return write_immutable_evidence(
        output_root=output_root,
        run_id=run_id,
        manifest=manifest,
        samples=samples,
        batch_summaries=batch_summaries,
        batch_comparisons=batch_comparisons,
        aggregates=aggregates,
    )


def _run_micro_smoke() -> dict[str, Any]:
    """Exercise every semantic cell once without persisting timing results."""

    workers = _open_workers()
    try:
        verification: dict[str, Any] = {}
        for scenario in MICRO_SCENARIOS:
            verification[scenario.name] = {}
            for surface in Surface:
                observation = _invoke_batch(
                    worker=workers[surface],
                    layer=Layer.MICRO,
                    scenario=scenario,
                    count=1,
                    token_prefix=f"smoke-{scenario.name}-{surface.value}",
                )[0]
                verification[scenario.name][surface.value] = {
                    "producer_outcome": observation["producer_outcome"],
                    "rule_id": observation["rule_id"],
                }
        return {
            "status": "smoke-only; timings discarded; no benchmark result",
            "verification": verification,
        }
    finally:
        _close_workers(workers)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    smoke = subparsers.add_parser(
        "smoke-micro",
        help="run one untimed-for-reporting verification per micro cell",
    )
    smoke.set_defaults(handler="smoke")

    for name, layer in (("micro", Layer.MICRO), ("postgres", Layer.POSTGRES)):
        command = subparsers.add_parser(name, help=f"run canonical {name} schedule")
        command.add_argument("--run-id", required=True)
        command.add_argument(
            "--confirm",
            required=True,
            help=f"must equal {CANONICAL_CONFIRMATION}",
        )
        command.set_defaults(handler="canonical", layer=layer)

    worker = subparsers.add_parser("_worker")
    worker.add_argument(
        "--surface",
        choices=[surface.value for surface in Surface],
        required=True,
    )
    worker.set_defaults(handler="worker")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _build_parser().parse_args(argv)
    if arguments.handler == "worker":
        return _worker_main(Surface(arguments.surface))
    try:
        if arguments.handler == "smoke":
            print(json.dumps(_run_micro_smoke(), indent=2, sort_keys=True))
        else:
            destination = _run_canonical(
                layer=arguments.layer,
                run_id=arguments.run_id,
                confirmation=arguments.confirm,
            )
            print(f"validated evidence written to {destination}")
    except RecordedRunError as exc:
        print(f"recorded run refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
