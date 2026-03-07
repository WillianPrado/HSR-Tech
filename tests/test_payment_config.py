import unittest

from fastapi.testclient import TestClient

from main import app


class TestPaymentConfigEndpoint(unittest.TestCase):
    def test_get_payment_public_config(self) -> None:
        client = TestClient(app)

        response = client.get("/api/v1/payment/config")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("stripe_public_key", payload)
        self.assertIn("payment_success_url", payload)
        self.assertIn("payment_cancel_url", payload)
        self.assertTrue(isinstance(payload["stripe_public_key"], str))


if __name__ == "__main__":
    unittest.main()
