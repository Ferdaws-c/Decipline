"""Review cases for course Pomodoros, cycle selection and period evaluation."""
import os
from datetime import date, datetime, timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from app import settings, stats
from app.analytics import evaluate
from app.pomodoro import PomodoroTimer, PomodoroState as State


class CoursePomodoroReview(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        for module, key, value in ((stats, 'STATS_PATH', str(self.base / 'stats.json')),
                                   (stats, '_stats', None), (stats, '_dirty', False),
                                   (settings, 'SETTINGS_PATH', str(self.base / 'settings.json'))):
            context = patch.object(module, key, value)
            context.start()
            self.addCleanup(context.stop)
        self.cid = stats.create_course('Biology')

    def timer(self):
        timer = PomodoroTimer()
        timer._wake_worker = Mock()
        timer.set_context(self.cid)
        self.addCleanup(timer.shutdown)
        return timer

    def drain(self, timer):
        timer.shutdown()
        timer._run()

    def test_selected_fourth_cycle_finishes_once_and_uses_long_break(self):
        timer = self.timer()
        timer.select_cycle(3)
        timer.start(60, track_tasks=False)
        with timer._condition:
            timer._update(timer._deadline)
            timer._update(timer._deadline or 0)
        self.assertEqual(timer.state, State.WAITING_FOR_BREAK)
        self.assertEqual(timer.selected_cycle, 3)
        timer.begin_break()
        self.assertEqual(timer.state, State.LONG_BREAK)
        self.assertEqual(timer.total, 1800)
        with timer._condition:
            timer._update(timer._deadline)
        self.assertEqual(timer.selected_cycle, 0)
        self.assertEqual(timer.state, State.WAITING_FOR_WORK)
        self.drain(timer)
        result = evaluate(stats.get_stats_summary(), 1, self.cid)
        self.assertEqual(result['study_seconds'], 60)
        self.assertEqual(result['break_seconds'], 1800)
        self.assertEqual(result['pomodoros'], 1)

    def test_switching_cycle_saves_partial_work_without_completion(self):
        timer = self.timer()
        timer.start(60)
        with timer._condition:
            timer._deadline -= 12
            timer.select_cycle(2)
        timer.start(60)
        with timer._condition:
            timer._deadline -= 8
            timer.reset()
        self.drain(timer)
        data = stats.get_stats_summary()
        self.assertEqual(data['study_seconds'], 20)
        self.assertEqual(len(data['lecture_sessions']), 2)
        self.assertEqual(evaluate(data, 1)['pomodoros'], 0)
        self.assertEqual(stats.course_totals(data['courses'][self.cid])['study_seconds'], 20)

    def test_early_break_resumes_same_remaining_focus_and_counts_once(self):
        timer = self.timer()
        with patch('app.pomodoro.time.monotonic', return_value=100):
            timer.start(60)
        sid = timer.session_id
        with patch('app.pomodoro.time.monotonic', return_value=110.5):
            timer.take_break()
        with patch('app.pomodoro.time.monotonic', return_value=115.5):
            timer.end_break()
        self.assertEqual(timer.state, State.PAUSED)
        self.assertEqual(timer.remaining, 50)
        self.assertEqual(timer.session_id, sid)
        with patch('app.pomodoro.time.monotonic', return_value=1000):
            timer.start()
        self.assertAlmostEqual(timer._deadline, 1049.5)
        with timer._condition:
            timer._update(timer._deadline)
        self.drain(timer)
        result = evaluate(stats.get_stats_summary(), 1, self.cid)
        self.assertEqual(result['study_seconds'], 60)
        self.assertEqual(result['break_seconds'], 5)
        self.assertEqual(result['pomodoros'], 1)

    def test_ending_break_at_natural_boundary_preserves_unfinished_focus(self):
        timer = self.timer()
        with patch('app.pomodoro.time.monotonic', return_value=100):
            timer.start(60)
        with patch('app.pomodoro.time.monotonic', return_value=110):
            timer.take_break()
        with patch('app.pomodoro.time.monotonic', return_value=410):
            timer.end_break()
        self.assertEqual(timer.state, State.PAUSED)
        self.assertEqual(timer.remaining, 50)
        self.assertIsNotNone(timer.session_id)
        self.drain(timer)
        self.assertEqual(evaluate(stats.get_stats_summary(), 1)['pomodoros'], 0)

    def test_quitting_during_break_saves_study_and_break_to_selected_course(self):
        timer = self.timer()
        timer.start(60)
        with timer._condition:
            timer._deadline -= 15
            timer.take_break()
            timer._deadline -= 7
        self.drain(timer)
        stats._stats = None
        data = stats.get_stats_summary()
        self.assertEqual(data['study_seconds'], 15)
        self.assertEqual(data['break_seconds'], 7)
        self.assertEqual(stats.course_totals(data['courses'][self.cid])['study_seconds'], 15)
        self.assertIsNotNone(next(iter(data['lecture_sessions'].values()))['ended_at'])

    def test_context_change_is_rejected_until_partial_session_is_saved(self):
        timer = self.timer()
        timer.start(60)
        timer.pause()
        with self.assertRaises(ValueError):
            timer.set_context(None)
        timer.reset()
        timer.set_context(None)
        self.drain(timer)

    def test_shutdown_never_counts_time_spent_waiting_for_writer_to_finish(self):
        timer = self.timer()
        timer.set_context(None)
        with patch('app.pomodoro.time.monotonic', return_value=100):
            timer.start(60)
        with patch('app.pomodoro.time.monotonic', return_value=110):
            timer.shutdown()
        with patch('app.pomodoro.time.monotonic', return_value=1000):
            timer._run()
        self.assertFalse(timer.is_running)
        self.assertEqual(stats.get_stats_summary()['study_seconds'], 10)

    def test_general_and_course_sessions_do_not_double_count_global_study(self):
        timer = self.timer()
        timer.start(60)
        with timer._condition:
            timer._deadline -= 10
            timer.reset()
            timer.set_context(None)
            timer.start(60)
            timer._deadline -= 20
        self.drain(timer)
        data = stats.get_stats_summary()
        result = evaluate(data, 1)
        self.assertEqual(data['study_seconds'], 30)
        self.assertEqual(sum(s['study_seconds'] for s in data['lecture_sessions'].values()), 30)
        self.assertEqual(sum(c['study_seconds'] for _, c in result['courses']), 30)

    def test_existing_lecture_totals_and_course_only_time_are_both_preserved(self):
        lid = stats.create_lecture(self.cid, 'Cells')
        sid = stats.start_lecture_session(self.cid, lid)
        stats.add_lecture_time(sid, 120, 30)
        stats.finish_lecture_session(sid)
        timer = self.timer()
        timer.start(60)
        with timer._condition:
            timer._deadline -= 20
        self.drain(timer)
        data = stats.get_stats_summary()
        self.assertEqual(stats.course_totals(data['courses'][self.cid])['study_seconds'], 140)
        self.assertEqual(data['courses'][self.cid]['lectures'][lid]['study_seconds'], 120)
        self.assertEqual(evaluate(data, None, self.cid)['study_seconds'], 140)


class EvaluationReview(unittest.TestCase):
    def sample(self):
        today = date(2026, 10, 17)
        def session(cid, stamp, seconds, rest, completed=None, days=None):
            row = {'course_id': cid, 'started_at': stamp, 'study_seconds': seconds,
                   'break_seconds': rest, 'completed_at': completed}
            if days is not None:
                row['days'] = days
            return row
        data = {'study_seconds': 9000, 'break_seconds': 900, 'courses': {
                    'a': {'name': 'Biology', 'study_seconds': 5400, 'break_seconds': 600, 'lectures': {}},
                    'b': {'name': 'Physics', 'study_seconds': 1800, 'break_seconds': 300, 'lectures': {}}},
                'history': {'2026-10-01': {'study_seconds': 3600, 'break_seconds': 300, 'pomodoros': 1},
                            '2026-10-17': {'study_seconds': 5400, 'break_seconds': 600, 'pomodoros': 2}},
                'lecture_sessions': {'one': session('a', '2026-10-01T10:00:00', 3600, 300, '2026-10-01T11:00:00'),
                                     'two': session('a', '2026-10-17T10:00:00', 1800, 300, '2026-10-17T10:30:00'),
                                     'three': session('b', '2026-10-17T11:00:00', 1800, 300, '2026-10-17T11:30:00')}}
        return data, today

    def test_period_metrics_and_course_rows_use_same_filter(self):
        data, today = self.sample()
        result = evaluate(data, 7, today=today)
        self.assertEqual(result['study_seconds'], 5400)
        self.assertEqual(result['break_seconds'], 600)
        self.assertEqual(result['pomodoros'], 2)
        self.assertEqual(sum(s for _, s in result['series']), 5400)
        self.assertEqual(sum(c['study_seconds'] for _, c in result['courses']), 5400)
        result = evaluate(data, 7, 'a', today)
        self.assertEqual(result['study_seconds'], 1800)
        self.assertEqual(result['pomodoros'], 1)
        self.assertEqual(result['active_days'], 1)
        self.assertEqual(len(result['courses']), 1)

    def test_all_time_preserves_legacy_totals_but_never_infers_completions(self):
        data, today = self.sample()
        data['lecture_sessions']['one'].pop('completed_at')
        result = evaluate(data, None, 'a', today)
        self.assertEqual(result['study_seconds'], 5400)
        self.assertEqual(result['pomodoros'], 1)

    def test_cross_midnight_session_is_split_by_recorded_day(self):
        data, today = self.sample()
        data['lecture_sessions'] = {'cross': {'course_id': 'a', 'started_at': '2026-10-16T23:50:00',
            'study_seconds': 1200, 'break_seconds': 60, 'completed_at': '2026-10-17T00:10:00',
            'days': {'2026-10-16': {'study_seconds': 600, 'break_seconds': 0},
                     '2026-10-17': {'study_seconds': 600, 'break_seconds': 60}}}}
        result = evaluate(data, 1, 'a', today)
        self.assertEqual(result['study_seconds'], 600)
        self.assertEqual(result['break_seconds'], 60)
        self.assertEqual(result['pomodoros'], 1)

    def test_empty_period_has_zero_metrics_and_correct_days(self):
        result = evaluate({}, 7, today=date(2026, 10, 17))
        self.assertEqual(result['study_seconds'], 0)
        self.assertEqual(result['active_days'], 0)
        self.assertEqual(result['average'], 0)
        self.assertEqual(len(result['series']), 7)
        self.assertEqual(result['courses'], [])

    def test_many_months_are_grouped_into_readable_calendar_buckets(self):
        data, today = self.sample()
        data['history']['2020-01-01'] = {'study_seconds': 60}
        result = evaluate(data, None, today=today)
        self.assertEqual(result['bucket'], 'year')
        self.assertLessEqual(len(result['series']), 7)

    def test_break_only_day_does_not_improve_days_studied_or_average(self):
        data, today = self.sample()
        data['history']['2026-10-16'] = {'study_seconds': 0, 'break_seconds': 600}
        result = evaluate(data, 7, today=today)
        self.assertEqual(result['active_days'], 1)
        self.assertEqual(result['average'], 5400)
        self.assertEqual(result['study_seconds'], 5400)
        self.assertEqual(result['break_seconds'], 1200)

    def test_undated_legacy_time_is_preserved_without_inflating_daily_average(self):
        data, today = self.sample()
        data['study_seconds'] += 36000
        result = evaluate(data, None, today=today)
        self.assertEqual(result['study_seconds'], 45000)
        self.assertEqual(result['undated_study'], 36000)
        self.assertEqual(result['average'], 4500)

    def test_course_filter_provides_lecture_and_whole_course_breakdown(self):
        data, today = self.sample()
        data['courses']['a']['lectures'] = {'cells': {'name': 'Cells', 'study_seconds': 1800, 'break_seconds': 300}}
        data['courses']['a']['study_seconds'] = 3600
        data['courses']['a']['break_seconds'] = 300
        data['lecture_sessions']['two']['lecture_id'] = 'cells'
        result = evaluate(data, 7, 'a', today)
        self.assertEqual(result['lectures'][0][1]['name'], 'Cells')
        self.assertEqual(result['lectures'][0][1]['study_seconds'], 1800)
        result = evaluate(data, None, 'a', today)
        self.assertEqual(sum(row['study_seconds'] for _, row in result['lectures']), 5400)
        self.assertEqual(result['study_seconds'], 5400)


if __name__ == '__main__':
    unittest.main()
