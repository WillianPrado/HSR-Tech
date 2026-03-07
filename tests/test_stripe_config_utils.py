import unittest

from core import config


class TestStripeConfigUtils(unittest.TestCase):
    def test_normalize_price_id_strips_comments(self) -> None:
        raw = 'price_123 # basic monthly'
        self.assertEqual(config.normalize_price_id(raw), "price_123")

    def test_normalize_price_id_strips_quotes(self) -> None:
        raw = '"price_abc"'
        self.assertEqual(config.normalize_price_id(raw), "price_abc")

    def test_stripe_price_id_by_plan_returns_none_for_placeholder(self) -> None:
        original = config.settings.STRIPE_START_PRICE_ID
        config.settings.STRIPE_START_PRICE_ID = "price_xxxx_placeholder"
        try:
            self.assertIsNone(config.stripe_price_id_by_plan("basic"))
        finally:
            config.settings.STRIPE_START_PRICE_ID = original


if __name__ == "__main__":
    unittest.main()
