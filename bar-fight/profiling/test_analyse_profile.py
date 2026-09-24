"""Diagnostic callbacks may continue after the capture's verified GameOver."""
import json
import unittest

from analyse_profile import analyse_profiler


def sample(shutdown=11425, ending=None, game_over=11414):
    rows = [dict(kind='meta', schema=2, options=151,
        diagnostic_not_timing_ab=True, command='debug 1 0')]
    for index, (phase, frame) in enumerate((('frame0', 0), ('game_over', game_over), ('shutdown', shutdown))):
        rows += [dict(kind='snapshot', phase=phase, frame=frame, names=1),
                 dict(kind='record', phase=phase, name='Sim', total_ms=index * 10.0)]
    rows.append(dict(kind='end', baseline_frame0=True, game_over_frame=game_over,
                     last_frame=shutdown if ending is None else ending))
    return '\n'.join(json.dumps(row) for row in rows)


class PhaseBoundaryTests(unittest.TestCase):
    def test_preserves_post_game_over_frames_separately(self):
        result = analyse_profiler(sample(), 11414, options=151)
        self.assertEqual(result['post_game_over_frames'], 11)
        self.assertEqual(result['rankings']['frame0_to_game_over'][0]['elapsed_ms'], 10)
        self.assertEqual(result['rankings']['game_over_to_shutdown'][0]['elapsed_ms'], 10)

    def test_rejects_changed_capture_game_over(self):
        with self.assertRaisesRegex(ValueError, 'GameOver mismatch'):
            analyse_profiler(sample(game_over=11415), 11414, options=151)

    def test_rejects_shutdown_before_game_over(self):
        with self.assertRaisesRegex(ValueError, 'Invalid profiler Shutdown frame'):
            analyse_profiler(sample(shutdown=11413), 11414, options=151)

    def test_rejects_inconsistent_shutdown_receipt(self):
        with self.assertRaisesRegex(ValueError, 'Wrong final phase frame'):
            analyse_profiler(sample(ending=11426), 11414, options=151)


if __name__ == '__main__':
    unittest.main()
