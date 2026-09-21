"""PR5 reconstruction, strict readback and frozen PR1/PR4 evidence semantics."""

from dataclasses import replace
from io import StringIO
import json

import pytest

from experiments.load_capacity_protection import evidence as pr1
from experiments.load_capacity_protection import pr4_evidence as pr4
from experiments.load_capacity_protection.pr5_evidence import (
    METHOD_VERSION, SCHEMA_VERSION, attempt_windows, descriptive_statistics,
    dumps_evidence, loads_evidence, read_evidence, write_evidence,
)
from experiments.load_capacity_protection.pr5_model import LogicalTerminal
from tests.experiments.load_capacity_protection.test_evidence import evidence as pr1_evidence
from tests.experiments.load_capacity_protection.test_model import accepted
from tests.experiments.load_capacity_protection.test_pr4_runner import execute as pr4_execute, plan as pr4_plan
from tests.experiments.load_capacity_protection.test_pr5_runner import execute, plan, FakeFactory


def test_roundtrip_retains_every_attempt_identity_timing_and_logical_effect():
    cells, _ = execute(plan(repetitions=1, k=2, concurrency_levels=(2,)), FakeFactory(eventual=True))
    cell = cells[1]
    text = dumps_evidence(cell)
    assert loads_evidence(text) == cell
    assert METHOD_VERSION == 'pr5-retry-refusal-amplification-v1' and SCHEMA_VERSION == 1
    assert 'PostgresWriteSideResult' not in text and 'ReinvocationAuthorization' not in text
    request = next(r for r in cell.cell.logical_requests if len(r.attempts) == 3)
    for a, b in zip(request.attempts, request.attempts[1:]):
        assert a.observation.capacity_refused_ns + a.scheduled_retry_delay_ns == a.next_retry_eligible_ns
        assert b.observation.dispatch_ns >= a.next_retry_eligible_ns
        assert a.observation.result is a.observation.measurement is None


def test_amplification_useful_completion_drain_and_explicit_rate_windows():
    cells, _ = execute(plan(repetitions=1))
    no_retry, retry = map(descriptive_statistics, cells)
    assert no_retry['total_attempts'] == no_retry['logical_requests'] == 7
    assert no_retry['attempt_amplification_factor'] == 1
    assert retry['logical_requests'] == 7
    assert retry['total_attempts'] == retry['capacity_attempts'] == retry['terminal_attempts'] == 25
    assert retry['capacity_refused_attempts'] == 24 and retry['admitted_attempts'] == 1
    assert retry['total_retries'] == 18
    assert retry['attempt_amplification_factor'] == 25 / 7
    assert retry['logical_completion_proportion'] == 1 / 7
    assert retry['logical_terminal_proportion'] == 1
    elapsed = retry['time_to_drain_logical_workload_ns']
    assert retry['accepted_writer_per_second'] == retry['logical_completion_per_second'] == 1e9 / elapsed
    assert retry['attempts_per_second'] == 25e9 / elapsed
    assert retry['logical_terminals_per_second'] == 7e9 / elapsed
    assert len(retry['attempt_dispatch_timestamps_ns']) == 25
    assert len(retry['retry_lateness_ns']) == 18
    assert retry['accepted_phase_samples']['business_uow'] == ()
    for width in (1, 10, 1000):
        windows = attempt_windows(cells[1], width_ns=width, origin_ns=0)
        assert sum(count for _, count in windows) == 25
        for index, count in windows:
            assert count == sum(index * width <= stamp < (index + 1) * width
                                for stamp in retry['capacity_attempt_timestamps_ns'])
    with pytest.raises(TypeError):
        attempt_windows(cells[1])
    for width in (0, -1, True):
        with pytest.raises(ValueError):
            attempt_windows(cells[1], width_ns=width, origin_ns=0)


def test_incomplete_preserves_counts_but_has_no_completed_throughput():
    cells, _ = execute(plan(concurrency_levels=(1,)), FakeFactory('native'))
    stats = descriptive_statistics(cells[0])
    assert stats['total_attempts'] == stats['native_writer_failures'] == 1
    assert stats['time_to_drain_logical_workload_ns'] is None
    assert stats['logical_completion_per_second'] is stats['attempts_per_second'] is None
    assert stats['acknowledged_accepted_logical_requests'] == 0


@pytest.mark.parametrize('key,value', [
    ('schema_version', 2), ('schema_version', True), ('schema_version', 1.0),
    ('method_version', pr4.METHOD_VERSION), ('method_version', 'future'),
])
def test_unsupported_version_fails_closed(key, value):
    cells, _ = execute(plan(repetitions=1))
    document = json.loads(dumps_evidence(cells[0]))
    document[key] = value
    with pytest.raises(ValueError, match='unsupported'):
        loads_evidence(json.dumps(document))


@pytest.mark.parametrize('kind', [
    'unknown_record', 'extra_field', 'missing_field', 'wrong_type', 'summary', 'logical_summary',
    'order', 'attempt_index', 'signature', 'delay', 'eligibility', 'concurrent_retry', 'budget', 'refusal_result',
])
def test_corrupt_evidence_fails_closed(kind):
    cells, _ = execute(plan(repetitions=1))
    document = json.loads(dumps_evidence(cells[1]))
    outer = document['cell']['fields']
    cell = outer['cell']['fields']
    request = next(r['fields'] for r in cell['logical_requests']['tuple'] if len(r['fields']['attempts']['tuple']) > 1)
    attempts = request['attempts']['tuple']
    first, second = attempts[0]['fields'], attempts[1]['fields']
    if kind == 'unknown_record':
        document['cell']['pr5_record'] = 'DynamicImport'
    elif kind == 'extra_field':
        outer['authority'] = True
    elif kind == 'missing_field':
        del outer['execution_order']
    elif kind == 'wrong_type':
        outer['plan']['fields']['protection_bound'] = True
    elif kind == 'summary':
        document['summaries']['total_attempts'] = 0
    elif kind == 'logical_summary':
        document['logical_summaries'][0]['attempts'] = 999
    elif kind == 'order':
        outer['execution_order']['tuple'].reverse()
    elif kind == 'attempt_index':
        second['attempt_index'] = 1
    elif kind == 'signature':
        second['observation']['fields']['item']['fields']['signature']['fields']['request_id'] = 'new-intent'
    elif kind == 'delay':
        first['scheduled_retry_delay_ns'] = 12345
        first['next_retry_eligible_ns'] = first['observation']['fields']['capacity_refused_ns'] + 12345
    elif kind == 'eligibility':
        first['next_retry_eligible_ns'] = 0
    elif kind == 'concurrent_retry':
        second['observation']['fields']['dispatch_ns'] = first['observation']['fields']['dispatch_ns']
    elif kind == 'budget':
        cell['retry']['fields']['max_attempts_per_logical_request'] = 1
    elif kind == 'refusal_result':
        accepted_request = next(r['fields'] for r in cell['logical_requests']['tuple']
                                if r['fields']['terminal_state']['value'] == 'acknowledged_accepted')
        first['observation']['fields']['result'] = accepted_request['attempts']['tuple'][0]['fields']['observation']['fields']['result']
    with pytest.raises((ValueError, TypeError)):
        loads_evidence(json.dumps(document))


def test_duplicate_keys_and_frozen_previous_codecs():
    with pytest.raises(ValueError, match='duplicate'):
        loads_evidence('{"schema_version":1,"schema_version":1}')
    old1 = pr1_evidence(accepted())
    old4 = pr4_execute(pr4_plan(repetitions=1))[0][0]
    raw1, raw4 = pr1.dumps_evidence(old1), pr4.dumps_evidence(old4)
    registries = dict(pr1._RECORDS), dict(pr1._ENUMS), dict(pr4._RECORDS)
    cells, _ = execute(plan(repetitions=1))
    for reader in (pr1.loads_evidence, pr4.loads_evidence):
        with pytest.raises(ValueError):
            reader(dumps_evidence(cells[0]))
    for text in (raw1, raw4):
        with pytest.raises(ValueError):
            loads_evidence(text)
    assert pr1.loads_evidence(raw1) == old1 and pr4.loads_evidence(raw4) == old4
    assert pr1.dumps_evidence(old1) == raw1 and pr4.dumps_evidence(old4) == raw4
    assert registries == (pr1._RECORDS, pr1._ENUMS, pr4._RECORDS)


def test_exclusive_output_never_overwrites_evidence():
    cells, _ = execute(plan(repetitions=1))

    class PathDouble:
        text = None

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
