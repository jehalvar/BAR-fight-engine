"""Recheck completed diagnostic evidence locally without executing an engine."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from audit_retained_startup import (ENGINE_SHA256, REPLAY_SHA256, STREAMS,
                                    checksum_rows, exact, finite_json, require)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(root):
    run = root / 'optimized151-profile'
    benchmark = finite_json((run / 'benchmark.json').read_bytes())
    require(benchmark['engine']['executable_sha256'] == ENGINE_SHA256
            and benchmark['replay_sha256'] == REPLAY_SHA256, 'Wrong executable/replay identity')
    require(benchmark['valid_capture'] is True and benchmark['equivalent'] is True
            and benchmark['exit_code'] == 0 and benchmark['errors'] == []
            and benchmark['end']['frame'] == 11414 and benchmark['options'] == 151
            and benchmark['production_validation_unchanged'] is True, 'Original harness failed')
    source = root / 'source'
    for name, expected in benchmark['collector_sources'].items():
        require(Path(name).name == name and digest(source / name) == expected,
                'Frozen source hash mismatch: ' + name)
    diagnostic = finite_json((run / 'profile-diagnostic.json').read_bytes())
    require(digest(root / 'frozen_run_one.py') == diagnostic['runner_sha256'], 'Runner hash changed')
    require(digest(root / 'harness' / 'run_profile.py') == diagnostic['adapter_sha256'], 'Adapter hash changed')
    require(digest(root / 'harness' / 'profiler_widget.lua') == diagnostic['profiler_widget_sha256'], 'Widget hash changed')
    require(digest(root / 'source-replay.sdfz') == REPLAY_SHA256, 'Copied replay hash changed')
    cache = finite_json((run / 'profile-cache-observation.json').read_bytes())
    require(len(cache['cache_before']) == len(cache['cache_after']) == 1, 'Unexpected archive cache inventory')
    cache_before, cache_after = cache['cache_before'][0], cache['cache_after'][0]
    require(cache_before['name'] == cache_after['name'] == 'ArchiveCache22.lua'
            and cache_before['size'] == cache_after['size'] == 4242221
            and cache_before['sha256'] == cache_after['sha256'] == digest(run / 'cache' / 'ArchiveCache22.lua'),
            'Archive cache content changed')
    require(cache_before['inode'] == cache_after['inode']
            and cache_before['mtime_ns'] != cache_after['mtime_ns']
            and cache_before['ctime_ns'] != cache_after['ctime_ns'], 'Cache rewrite metadata absent')

    stream_rows = {}
    for name in STREAMS:
        left = [finite_json(line) for line in (root / 'official75' / 'LuaUI' / name).read_bytes().splitlines()]
        right = [finite_json(line) for line in (run / 'LuaUI' / name).read_bytes().splitlines()]
        require(exact(left, right), 'Exact ordered stream mismatch: ' + name)
        stream_rows[name] = len(right)
    candidate_checksums = checksum_rows((run / 'LuaUI' / 'benchmark-sync-checksums.jsonl').read_bytes())
    official_checksums = checksum_rows((root / 'official75' / 'LuaUI' / 'benchmark-sync-checksums.jsonl').read_bytes())
    require(candidate_checksums == official_checksums, 'Every-frame checksum mismatch')

    # These modules are the byte-pinned original source; this calls only parsers
    # and validators. No engine launcher or publication entry point is invoked.
    sys.path.insert(0, str(source.resolve()))
    import parser as replay_parser
    import server_engine
    replay = replay_parser.read_replay(root / 'source-replay.sdfz')
    recorded = finite_json((run / 'replay.json').read_bytes())
    # The local retained file has a deliberately different basename. Everything
    # used by the footer/capture/context checks must match the original parse.
    comparable_replay = lambda value: {key: item for key, item in value.items() if key != 'source'}
    require(exact(comparable_replay(replay), comparable_replay(recorded)), 'Fresh source replay parse differs')
    original_audit = finite_json((run / 'validation.json').read_bytes())
    report, checked = server_engine.validate_capture(run, exit_code=0,
        elapsed_seconds=original_audit['elapsed_seconds'])
    require(checked['valid_capture'] and not checked['errors'], 'Unchanged production validator failed')
    saved = finite_json((run / 'team-statistics.json').read_bytes())
    require(exact(report, saved), 'Fresh production report differs from retained report')
    footer = checked['footer_corroboration']
    require(footer['status'] == 'matched' and footer['teams_compared'] == 16
            and footer['metrics_compared'] == 112 and footer['mismatches'] == [], 'Fresh footer guard failed')

    control = root / 'controller'
    receipt = finite_json((control / 'controller-result.json').read_bytes())
    require(digest(control / 'diagnostic-config.json') == receipt['config_sha256']
            == 'f68058ffab45b3b1eeb809abe9ff342e76318138a76f0938f8f891cf80b3bd14', 'Controller config pin differs')
    require(receipt['returncode'] == 0 and receipt['error'] is None and receipt['cleanup_errors'] == []
            and receipt['diagnostic_state'] == 'inactive' and receipt['all_affinities_restored'] is True
            and receipt['worker_pids_unchanged'] is True and receipt['worker_restart_counts_unchanged'] is True,
            'Controller restoration receipt failed')
    before = finite_json((control / 'production-before.json').read_bytes())
    after = finite_json((control / 'production-after.json').read_bytes())
    require(exact(before, after), 'Before/after production worker identities changed')
    require(len(before) == 20 and all(worker['ActiveState'] == 'active'
            and worker['AllowedCPUs'] == '' and int(worker['MainPID']) > 0
            and int(worker['NRestarts']) >= 0 for worker in before.values()), 'Invalid worker baseline')
    restored = finite_json((control / 'cpu-restored.json').read_bytes())
    require(restored['all_twenty_restored'] is True and len(restored['after']) == 20
            and all(value == '' for value in restored['after'].values()), 'Affinities not fully restored')
    inventory = {str(path.relative_to(root)).replace('\\', '/'): dict(bytes=path.stat().st_size, sha256=digest(path))
                 for path in sorted(root.rglob('*')) if path.is_file()
                 and '__pycache__' not in path.parts and path.suffix != '.pyc'
                 and path.name not in ('independent-proof.json', 'diagnostic-summary.json')}
    return dict(kind='independent_optimized_profile_raw_proof', engine_executed=False,
        reference='Original official75 capture streams and every-frame checksums',
        exact_stream_rows=stream_rows, exact_checksum_rows=len(candidate_checksums),
        fresh_source_parse_equal=True, fresh_unchanged_capture_validator=True,
        fresh_capture_report_exactly_equal=True, footer=footer,
        unchanged_cache_content_with_changed_mtime_ctime=True,
        controller=receipt, exact_production_before_after=True, restored_workers=20,
        provenance='Raw copied evidence is hashed locally; source/runner/widget/replay pins checked against original receipts.',
        inventory=inventory)


def main():
    arguments = argparse.ArgumentParser(description=__doc__)
    arguments.add_argument('evidence_directory', type=Path)
    args = arguments.parse_args()
    result = audit(args.evidence_directory)
    (args.evidence_directory / 'independent-proof.json').write_text(
        json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in result.items() if key != 'inventory'}, indent=2))


if __name__ == '__main__':
    main()
