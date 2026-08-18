import os
import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch

from app.time_utils import business_date_range_utc, to_business_datetime, utc_isoformat


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


if __name__ == '__main__':
    unittest.main()
