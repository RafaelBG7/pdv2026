from decimal import Decimal
from types import SimpleNamespace
import unittest

from app.money import format_brl, money_decimal, money_json, parse_money_decimal, percent_decimal
from app.services.sale_service import SalePaymentInput, card_fee_total


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

    def test_import_style_decimal_separators_preserve_cents(self):
        cases = {
            '0,01': Decimal('0.01'),
            '0,10': Decimal('0.10'),
            '1,99': Decimal('1.99'),
            '10,90': Decimal('10.90'),
            '99,99': Decimal('99.99'),
            '100,00': Decimal('100.00'),
            '9999,99': Decimal('9999.99'),
            '10.90': Decimal('10.90'),
        }
        for raw_value, expected in cases.items():
            with self.subTest(raw_value=raw_value):
                self.assertEqual(parse_money_decimal(raw_value), expected)

    def test_money_output_accepts_legacy_values_above_transaction_limit(self):
        legacy_value = Decimal('7898630000000.00')

        with self.assertRaisesRegex(ValueError, 'money_out_of_range'):
            parse_money_decimal(legacy_value)

        self.assertEqual(money_json(legacy_value), '7898630000000.00')
        self.assertEqual(format_brl(legacy_value), 'R$ 7.898.630.000.000,00')

    def test_binary_float_artifacts_are_normalized_through_text(self):
        self.assertEqual(money_decimal(0.1 + 0.2), Decimal('0.30'))
        self.assertEqual(money_decimal(0.01 * 100), Decimal('1.00'))

    def test_round_half_up_is_explicit_for_money_and_percentages(self):
        self.assertEqual(money_decimal('10.125'), Decimal('10.13'))
        self.assertEqual(money_decimal('0.105'), Decimal('0.11'))
        self.assertEqual(percent_decimal('1.23456'), Decimal('1.2346'))

    def test_card_fee_keeps_four_decimal_percentage_precision(self):
        company = SimpleNamespace(
            pix_fee_enabled=True,
            debit_fee_enabled=False,
            credit_fee_enabled=False,
            pix_fee_percent=Decimal('1.2345'),
            debit_fee_percent=Decimal('0'),
            credit_fee_percent=Decimal('0'),
        )
        payments = [SalePaymentInput('pix', Decimal('1000.00'))]

        self.assertEqual(
            card_fee_total(company, payments, Decimal('1000.00'), Decimal('1000.00')),
            Decimal('12.35'),
        )
