import os
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from flask import Flask

from app.time_utils import business_date_range_utc, format_local_datetime, to_business_datetime, utc_isoformat


class TimeUtilsTests(unittest.TestCase):
    def test_utc_isoformat_marks_naive_database_value_as_utc(self):
        self.assertEqual(utc_isoformat(datetime(2026, 8, 18, 15, 30)), '2026-08-18T15:30:00Z')

    def test_utc_isoformat_converts_aware_value_to_utc(self):
        value = datetime.fromisoformat('2026-08-18T12:30:00-03:00')
        self.assertEqual(utc_isoformat(value), '2026-08-18T15:30:00Z')

    @patch.dict(os.environ, {'BUSINESS_TIMEZONE': 'America/Sao_Paulo'})
    def test_business_datetime_converts_utc_to_sao_paulo(self):
        value = to_business_datetime(datetime(2026, 8, 18, 15, 30, tzinfo=timezone.utc))
        self.assertEqual(value.isoformat(), '2026-08-18T12:30:00-03:00')

    @patch.dict(os.environ, {'BUSINESS_TIMEZONE': 'America/Sao_Paulo'})
    def test_business_day_bounds_are_naive_utc_for_database(self):
        start, end = business_date_range_utc(date(2026, 8, 18), date(2026, 8, 18))
        self.assertEqual(start, datetime(2026, 8, 18, 3, 0))
        self.assertEqual(end, datetime(2026, 8, 19, 3, 0))

    def test_request_timezone_controls_display_and_day_bounds(self):
        app = Flask(__name__)
        with app.test_request_context('/', headers={'X-SkyGest-Timezone': 'Asia/Tokyo'}):
            instant = datetime(2026, 8, 18, 22, 30)
            self.assertEqual(format_local_datetime(instant), '19/08/2026 07:30')
            start, end = business_date_range_utc(date(2026, 8, 19), date(2026, 8, 19))
            self.assertEqual(start, datetime(2026, 8, 18, 15, 0))
            self.assertEqual(end, datetime(2026, 8, 19, 15, 0))

    def test_browser_timezone_cookie_is_used_and_invalid_header_is_ignored(self):
        app = Flask(__name__)
        with app.test_request_context('/', headers={
            'Cookie': 'skygest_timezone=America%2FSao_Paulo',
            'X-SkyGest-Timezone': 'invalid/timezone',
        }):
            self.assertEqual(format_local_datetime(datetime(2026, 8, 19, 2, 30)), '18/08/2026 23:30')

    def test_day_bounds_follow_daylight_saving_transitions(self):
        app = Flask(__name__)
        with app.test_request_context('/', headers={'X-SkyGest-Timezone': 'America/New_York'}):
            start, end = business_date_range_utc(date(2026, 3, 8), date(2026, 3, 8))
            self.assertEqual(end - start, timedelta(hours=23))


if __name__ == '__main__':
    unittest.main()
