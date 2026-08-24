from decimal import Decimal
import unittest

from app.money import format_brl, money_json, parse_money_decimal


class MoneyTestCase(unittest.TestCase):
    def test_parse_money_decimal_preserves_brazilian_values(self):
        cases = [
            ('65,99', Decimal('65.99')),
            ('2.480,35', Decimal('2480.35')),
            ('19', Decimal('19.00')),
            ('19,90', Decimal('19.90')),
            (65.99, Decimal('65.99')),
        ]
        for raw_value, expected in cases:
            with self.subTest(raw_value=raw_value):
                self.assertEqual(parse_money_decimal(raw_value, positive=True), expected)

    def test_parse_money_decimal_rejects_invalid_positive_values(self):
        for raw_value in [None, '', 'abc', '-1', 'NaN', 'Infinity', '0']:
            with self.subTest(raw_value=raw_value), self.assertRaises(ValueError):
                parse_money_decimal(raw_value, positive=True)

    def test_money_serialization_and_brazilian_format_are_stable(self):
        self.assertEqual(money_json(Decimal('2480.35')), '2480.35')
        self.assertEqual(format_brl(Decimal('2480.35')), 'R$ 2.480,35')

    def test_money_output_accepts_legacy_values_above_transaction_limit(self):
        legacy_value = Decimal('7898630000000.00')

        with self.assertRaisesRegex(ValueError, 'money_out_of_range'):
            parse_money_decimal(legacy_value)

        self.assertEqual(money_json(legacy_value), '7898630000000.00')
        self.assertEqual(format_brl(legacy_value), 'R$ 7.898.630.000.000,00')
