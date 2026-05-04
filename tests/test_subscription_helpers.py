from __future__ import annotations

import asyncio
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
        self.assertIn("internal/subscriptions/discord/webhooks", SUB_ROUTE_PUT)
        self.assertIn("internal/subscriptions/discord/webhooks", SUB_ROUTE_DELETE)
        self.assertIn("internal/subscriptions/discord/webhooks", SUB_ROUTE_STATUS)


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
        self.assertEqual(
            body["targets"]["players"],
            [
                {"membershipId": "1", "requireFresh": True, "requireCompleted": False},
                {"membershipId": "2", "requireFresh": True, "requireCompleted": False},
                {"membershipId": "3", "requireFresh": True, "requireCompleted": False},
            ],
        )
        self.assertEqual(
            body["targets"]["clans"],
            [{"groupId": "9", "requireFresh": True, "requireCompleted": False}],
        )

    def test_ignores_non_digit_tokens_in_lists(self) -> None:
        body = build_subscription_json_body({"players": "1, abc, 2"})
        self.assertEqual(
            body["targets"]["players"],
            [
                {"membershipId": "1", "requireFresh": False, "requireCompleted": False},
                {"membershipId": "2", "requireFresh": False, "requireCompleted": False},
            ],
        )


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
        out = asyncio.run(format_subscription_status_embed(None, {"registered": False}))
        self.assertIn("embeds", out)
        self.assertEqual(out["embeds"][0]["title"], "Subscription Status")
        self.assertIn("RaidHub alerts are currently turned off", out["embeds"][0]["description"])
        self.assertEqual(out["embeds"][0]["color"], 0x747F8D)

    def test_registered_minimal(self) -> None:
        out = asyncio.run(
            format_subscription_status_embed(
                None,
                {
                    "registered": True,
                    "destinationActive": True,
                    "webhookId": "123",
                    "consecutiveDeliveryFailures": 0,
                },
            )
        )
        fields = {f["name"]: f["value"] for f in out["embeds"][0]["fields"]}
        self.assertIn("Destination Active", fields)
        self.assertIn("Delivery Failures", fields)
        self.assertNotIn("Rule Filters", fields)
        self.assertEqual(out["embeds"][0]["color"], 0x57_F287)

    def test_registered_destination_inactive_embed_is_red(self) -> None:
        out = asyncio.run(
            format_subscription_status_embed(
                None,
                {
                    "registered": True,
                    "destinationActive": False,
                    "consecutiveDeliveryFailures": 0,
                },
            )
        )
        self.assertEqual(out["embeds"][0]["color"], 0xED42_45)

    def test_registered_uses_clan_group_id_key(self) -> None:
        out = asyncio.run(
            format_subscription_status_embed(
                None,
                {
                    "registered": True,
                    "destinationActive": True,
                    "consecutiveDeliveryFailures": 0,
                    "clans": [{"clanGroupId": "4927161"}],
                },
            )
        )
        fields = {f["name"]: f["value"] for f in out["embeds"][0]["fields"]}
        self.assertIn("• `4927161`", fields["Clan Rules (1)"])
        self.assertIn("`raids:all`", fields["Clan Rules (1)"])

    def test_registered_player_rules_show_per_rule_filters(self) -> None:
        out = asyncio.run(
            format_subscription_status_embed(
                None,
                {
                    "registered": True,
                    "destinationActive": True,
                    "consecutiveDeliveryFailures": 0,
                    "players": [
                        {
                            "membershipId": "4611686018488107374",
                            "requireFresh": True,
                            "requireCompleted": False,
                        }
                    ],
                    "clans": [{"groupId": "4927161", "requireFresh": True, "requireCompleted": False}],
                },
            )
        )
        fields = {f["name"]: f["value"] for f in out["embeds"][0]["fields"]}
        self.assertNotIn("Rule Filters", fields)
        self.assertIn("`require:fresh`", fields["Player Rules (1)"])
        self.assertNotIn("`require:completed`", fields["Player Rules (1)"])


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
