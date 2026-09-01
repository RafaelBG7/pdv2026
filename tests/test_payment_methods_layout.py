from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PaymentMethodsLayoutTestCase(unittest.TestCase):
    def test_web_checkout_displays_payment_methods_in_operational_order(self):
        template = (ROOT / "app/templates/sales/form.html").read_text(encoding="utf-8")
        routes = (ROOT / "app/routes/main.py").read_text(encoding="utf-8")

        positions = [
            routes.index(f"'{method}':")
            for method in ("money", "debit", "credit", "pix")
        ]

        self.assertEqual(positions, sorted(positions))
        self.assertIn('class="payment-grid sale-payment-methods mt-3"', template)
        self.assertIn("{{ label|upper }}", template)

    def test_web_checkout_payment_methods_stack_on_small_screens(self):
        stylesheet = (ROOT / "app/static/css/style.css").read_text(encoding="utf-8")

        mobile_rule = stylesheet.index("@media (max-width: 640px)")
        responsive_payment_rule = stylesheet.index(
            ".sale-payment-step .payment-grid {", mobile_rule
        )
        one_column_rule = stylesheet.index(
            "grid-template-columns: 1fr;", responsive_payment_rule
        )

        self.assertGreater(one_column_rule, responsive_payment_rule)
