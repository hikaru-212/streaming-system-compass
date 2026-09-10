"""PR4 serialization, accounting and descriptive metrics with frozen PR1 meaning."""

from dataclasses import replace
from io import StringIO
import json

import pytest

from experiments.load_capacity_protection import evidence as pr1
from experiments.load_capacity_protection.pr4_evidence import (
    METHOD_VERSION, SCHEMA_VERSION, descriptive_statistics, dumps_evidence,
    loads_evidence, read_evidence, write_evidence,
)
from experiments.load_capacity_protection.pr4_model import ProtectionMode
from tests.experiments.load_capacity_protection.test_evidence import evidence as pr1_evidence
from tests.experiments.load_capacity_protection.test_model import accepted
from tests.experiments.load_capacity_protection.test_pr4_runner import execute, plan


def test_roundtrip_retains_capacity_facts_modes_full_order_and_absence_witness():
    cells, _ = execute(plan(repetitions=1))
    for original in cells:
        text = dumps_evidence(original)
        decoded = loads_evidence(text)
        assert decoded == original and decoded is not original
        assert decoded.execution_order == original.execution_order
        assert decoded.scheduled.protection == original.scheduled.protection
        assert decoded.accounting == original.accounting
        assert 'PostgresWriteSideResult' not in text
        assert 'ReinvocationAuthorization' not in text
        for row in decoded.cell.observations:
            if row.capacity_refused_ns is not None:
                assert row.verification.identity_idempotency_count == 0
                assert row.result is row.failure is None


@pytest.mark.parametrize('key,value', [
    ('schema_version', 2), ('schema_version', True), ('schema_version', 1.0),
    ('method_version', pr1.METHOD_VERSION), ('method_version', 'future'),
])
def test_unsupported_pr4_version_fails_closed(key, value):
    cells, _ = execute(plan(repetitions=1, k=1, concurrency_levels=(1,)))
    document = json.loads(dumps_evidence(cells[0]))
    document[key] = value
    with pytest.raises(ValueError, match='unsupported'):
        loads_evidence(json.dumps(document))


@pytest.mark.parametrize('kind', ['unknown_record', 'extra_field', 'missing_field', 'wrong_type',
                                 'summary', 'summary_bool', 'order', 'fabricated_admission'])
def test_corrupted_evidence_fails_closed(kind):
    cells, _ = execute(plan(repetitions=1))
    document = json.loads(dumps_evidence(cells[0]))
    cell = document['cell']['fields']
    if kind == 'unknown_record':
        document['cell']['pr4_record'] = 'ImportArbitraryType'
    elif kind == 'extra_field':
        cell['retry_authority'] = True
    elif kind == 'missing_field':
        del cell['execution_order']
    elif kind == 'wrong_type':
        cell['plan']['fields']['protection_bound'] = True
    elif kind == 'summary':
        document['summaries']['accounting']['fields']['planned'] = 999
    elif kind == 'summary_bool':
        document['summaries']['harness_failures'] = False
    elif kind == 'order':
        cell['execution_order']['tuple'].reverse()
    elif kind == 'fabricated_admission':
        row = cell['cell']['fields']['observations']['tuple'][0]['fields']
        row['capacity_attempt_ns'] = row['public_call_entry_ns']
    with pytest.raises((ValueError, TypeError)):
        loads_evidence(json.dumps(document))


def test_duplicate_json_keys_rejected():
    with pytest.raises(ValueError, match='duplicate'):
        loads_evidence('{"schema_version": 1, "schema_version": 1}')


def test_useful_work_metrics_never_hide_refusals_and_incomplete_throughput_is_absent():
    cells, _ = execute(plan(repetitions=1))
    unprotected, protected = map(descriptive_statistics, cells)
    assert unprotected['mode'] == 'unprotected' and unprotected['bound'] is None
    assert unprotected['admission_ratio_of_attempted'] is None
    assert unprotected['refusal_proportion_of_offered'] is None
    assert unprotected['protected_writer_overlap'] is None
    assert protected['accounting'].acknowledged_accepted == 1
    assert protected['accounting'].capacity_refused == 6
    assert protected['accepted_proportion_of_offered'] == 1 / 7
    assert protected['refusal_proportion_of_offered'] == 6 / 7
    assert protected['admission_ratio_of_attempted'] == 1 / 7
    assert protected['refusal_ratio_of_attempted'] == 6 / 7
    assert protected['acknowledged_accepted_per_second'] == 1e9 / protected['completed_cell_elapsed_ns']
    assert protected['sample_counts']['capacity_refused']['protected_writer_body_ns'] == 0
    assert protected['sample_counts']['capacity_refused']['outer_terminal_latency_ns'] == 6
    assert protected['sample_counts']['acknowledged_accepted']['protected_writer_body_ns'] == 1
    # Fake plain writers deliver no phase timings: absence must not become zero.
    assert protected['samples']['all']['phase.business_uow'] == ()
    partial_cell = replace(cells[1].cell, observations=cells[1].cell.observations[:1])
    partial = descriptive_statistics(replace(cells[1], cell=partial_cell, cleanup_completed=False))
    assert partial['acknowledged_accepted_per_second'] is None
    assert partial['completed_cell_elapsed_ns'] is None


def test_phase_samples_preserve_measured_zero_and_omit_unreached_states():
    cells, _ = execute(plan(repetitions=1, k=1, concurrency_levels=(1,)))
    from dataclasses import fields
    from src.pipeline.transactional.postgres_write_side_measurement import (
        PostgresWriteSideMeasurement, PostgresWriteSideMeasurementAvailability,
        PostgresWriteSidePhaseMeasurement, PostgresWriteSidePhaseMeasurementState,
    )
    measured = PostgresWriteSidePhaseMeasurement(PostgresWriteSidePhaseMeasurementState.MEASURED, 0)
    phases = {f.name: measured for f in fields(PostgresWriteSideMeasurement)}
    phases['rollback_finalization'] = PostgresWriteSidePhaseMeasurement(PostgresWriteSidePhaseMeasurementState.NOT_REACHED)
    row = replace(cells[0].cell.observations[0], measurement=PostgresWriteSideMeasurement(**phases),
                  measurement_availability=PostgresWriteSideMeasurementAvailability.AVAILABLE)
    cell = replace(cells[0], cell=replace(cells[0].cell, observations=(row,)))
    stats = descriptive_statistics(loads_evidence(dumps_evidence(cell)))
    for phase in ('business_uow', 'append_admission_call', 'commit_finalization'):
        assert stats['samples']['acknowledged_accepted'][f'phase.{phase}'] == (0,)
    assert stats['samples']['all']['phase.rollback_finalization'] == ()


def test_pr1_codec_registry_and_archival_meaning_unchanged_after_pr4_use():
    original = pr1_evidence(accepted())
    archived = pr1.dumps_evidence(original)
    records = dict(pr1._RECORDS)
    enums = dict(pr1._ENUMS)
    cells, _ = execute(plan(repetitions=1))
    for cell in cells:
        with pytest.raises(ValueError):
            pr1.loads_evidence(dumps_evidence(cell))
    assert pr1._RECORDS == records and pr1._ENUMS == enums
    assert pr1.loads_evidence(archived) == original
    assert pr1.dumps_evidence(original) == archived
    assert pr1.METHOD_VERSION == 'pr1-unprotected-finite-load-v1' and pr1.SCHEMA_VERSION == 1
    assert original.accounting.writer_entered == 1
    assert not hasattr(original.accounting, 'capacity_admitted')
    with pytest.raises(ValueError):
        loads_evidence(archived)


def test_exclusive_output_never_overwrites_existing_evidence():
    cells, _ = execute(plan(repetitions=1, k=1, concurrency_levels=(1,)))

    class PathDouble:
        def __init__(self):
            self.text = None

        def open(self, mode, *, encoding):
            assert mode == 'x' and encoding == 'utf-8'
            if self.text is not None:
                raise FileExistsError()
            owner = self

            class Output(StringIO):
                def close(self):
                    owner.text = self.getvalue()
                    super().close()
            return Output()

        def read_text(self, *, encoding):
            return self.text

    path = PathDouble()
    write_evidence(path, cells[0])
    original = path.text
    assert read_evidence(path) == cells[0]
    with pytest.raises(FileExistsError):
        write_evidence(path, cells[0])
    assert path.text == original
