import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import login
import runtime
import server


class LoginTests(unittest.TestCase):
    def test_home_initializes_dashboard(self):
        page = MagicMock()
        page.url = 'https://lms.ssu.ac.kr/'
        page.locator.return_value.count.return_value = 1
        login.open_dashboard(page)
        page.goto.assert_called_once_with('https://lms.ssu.ac.kr/mypage',
                                         wait_until='domcontentloaded', timeout=30000)

    def test_no_navigation_on_sso_or_dashboard(self):
        for url in ('https://smartid.ssu.ac.kr/login', 'https://lms.ssu.ac.kr/mypage',
                    'https://lms.ssu.ac.kr.evil.test/'):
            page = MagicMock()
            page.url = url
            login.open_dashboard(page)
            page.goto.assert_not_called()

    def test_status_roundtrip_and_missing(self):
        with TemporaryDirectory() as directory, patch.object(runtime, 'LOGIN_STATUS', Path(directory) / 'status.json'):
            self.assertEqual(runtime.login_status()['status'], 'not_started')
            runtime.login_status('driver_starting')
            self.assertEqual(runtime.login_status()['status'], 'driver_starting')

    def test_dead_worker_is_not_reported_as_waiting(self):
        with TemporaryDirectory() as directory, patch.object(server, 'APP_DIR', Path(directory)), \
                patch.object(server, 'LOGIN_PID', Path(directory) / 'login.pid'), \
                patch.object(server, 'LOGIN_STATUS', Path(directory) / 'status.json'), \
                patch.object(server, 'login_status', return_value={'status': 'browser_failed'}), \
                patch.object(server.subprocess, 'Popen') as launch:
            launch.return_value.poll.return_value = 1
            result = server.start_login('browser')
            self.assertEqual(result['status'], 'login_start_failed')
            self.assertEqual(result['reason'], 'browser_failed')

    def test_live_verification_still_required(self):
        with patch.object(server, 'list_courses', side_effect=RuntimeError('expired')), \
                patch.object(server, 'login_status', return_value={'status': 'authenticated'}):
            self.assertFalse(server.auth_status()['authenticated'])

    def test_stuck_startup_is_bounded_and_child_is_stopped(self):
        with TemporaryDirectory() as directory, patch.object(server, 'APP_DIR', Path(directory)), \
                patch.object(server, 'LOGIN_PID', Path(directory) / 'login.pid'), \
                patch.object(server, 'LOGIN_STATUS', Path(directory) / 'status.json'), \
                patch.object(server, 'login_status', return_value={'status': 'driver_starting'}), \
                patch.object(server.time, 'monotonic', side_effect=[0, 0, 41]), \
                patch.object(server.time, 'sleep'), patch.object(server.subprocess, 'Popen') as launch:
            launch.return_value.poll.return_value = None
            result = server.start_login('browser')
            self.assertEqual(result['reason'], 'startup_timeout')
            launch.return_value.terminate.assert_called_once()
            launch.return_value.wait.assert_called_once_with(timeout=5)

    def test_existing_worker_does_not_invent_open_window(self):
        with TemporaryDirectory() as directory, patch.object(server, 'APP_DIR', Path(directory)), \
                patch.object(server, 'LOGIN_PID', Path(directory) / 'login.pid'), \
                patch.object(server, 'process_running', return_value=True), \
                patch.object(server, 'login_status', return_value={'status': 'driver_starting'}):
            server.LOGIN_PID.write_text('123', encoding='utf-8')
            self.assertEqual(server.start_login('browser')['status'], 'driver_starting')


if __name__ == '__main__':
    unittest.main()
