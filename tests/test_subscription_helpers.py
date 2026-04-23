from __future__ import annotations

import unittest

from src.commands.subscription_helpers import (
    build_subscription_json_body,
    format_subscription_status_embed,
    subscription_envelope_error_message,
    subscription_rules_suffix,
)
from src.commands.subscription_routes import SUB_ROUTE_DELETE, SUB_ROUTE_PUT, SUB_ROUTE_STATUS


class SubscriptionRoutesTests(unittest.TestCase):
    def test_route_ids_match_expected_api_shape(self) -> None:
        self.assertIn("subscriptions/discord/webhooks", SUB_ROUTE_PUT)
        self.assertIn("subscriptions/discord/webhooks", SUB_ROUTE_DELETE)
        self.assertIn("subscriptions/discord/webhooks", SUB_ROUTE_STATUS)


class BuildSubscriptionJsonBodyTests(unittest.TestCase):
    def test_empty_leaf_returns_empty_dict(self) -> None:
        self.assertEqual(build_subscription_json_body({}), {})

    def test_webhook_name_truncation_and_alias(self) -> None:
        long_name = "x" * 100
        body = build_subscription_json_body({"discord_webhook_name": long_name})
        self.assertEqual(body["name"], "x" * 80)

        body2 = build_subscription_json_body({"webhook_name": "short"})
        self.assertEqual(body2["name"], "short")

    def test_filters_and_targets(self) -> None:
        body = build_subscription_json_body(
            {
                "require_fresh": True,
                "require_completed": False,
                "players": "1, 2 3",
                "clans": "9",
            }
        )
        self.assertEqual(body["filters"]["requireFresh"], True)
        self.assertEqual(body["filters"]["requireCompleted"], False)
        self.assertEqual(body["targets"]["playerMembershipIds"], ["1", "2", "3"])
        self.assertEqual(body["targets"]["clanGroupIds"], ["9"])

    def test_ignores_non_digit_tokens_in_lists(self) -> None:
        body = build_subscription_json_body({"players": "1, abc, 2"})
        self.assertEqual(body["targets"]["playerMembershipIds"], ["1", "2"])


class SubscriptionEnvelopeErrorMessageTests(unittest.TestCase):
    def test_known_codes(self) -> None:
        msg = subscription_envelope_error_message(
            {"code": "InsufficientPermissionsError"}
        )
        self.assertIn("Manage Webhooks", msg)
        msg2 = subscription_envelope_error_message({"code": "BodyValidationError"})
        self.assertIn("digits only", msg2)

    def test_unknown_code_uses_generic_mapping(self) -> None:
        msg = subscription_envelope_error_message({"code": "RaidHubApiUnreachable"})
        self.assertIn("RAIDHUB_API_BASE_URL", msg)


class FormatSubscriptionStatusEmbedTests(unittest.TestCase):
    def test_unregistered_channel(self) -> None:
        out = format_subscription_status_embed({"registered": False})
        self.assertIn("embeds", out)
        self.assertEqual(out["embeds"][0]["title"], "Subscription Status")
        self.assertIn("No RaidHub subscription webhook", out["embeds"][0]["description"])

    def test_registered_minimal(self) -> None:
        out = format_subscription_status_embed(
            {
                "registered": True,
                "destinationActive": True,
                "webhookId": "123",
                "consecutiveDeliveryFailures": 0,
            }
        )
        fields = {f["name"]: f["value"] for f in out["embeds"][0]["fields"]}
        self.assertIn("Destination Active", fields)
        self.assertIn("`123`", fields["Webhook ID"])


class SubscriptionRulesSuffixTests(unittest.TestCase):
    def test_empty_rules(self) -> None:
        self.assertEqual(subscription_rules_suffix({}), "")

    def test_counts(self) -> None:
        s = subscription_rules_suffix(
            {"players": {"inserted": 1, "updated": 2}, "clans": {"inserted": 0, "updated": 1}}
        )
        self.assertIn("3 player", s)
        self.assertIn("1 clan", s)


if __name__ == "__main__":
    unittest.main()
