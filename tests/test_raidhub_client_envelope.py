from __future__ import annotations

import unittest

from src.raidhub_client_envelope import normalize_envelope_response
from src.raidhub_client_types import RaidHubEnvelopeCode


class NormalizeEnvelopeResponseTests(unittest.TestCase):
    def test_success_returns_dict_unchanged(self) -> None:
        payload = {"success": True, "response": {}}
        out = normalize_envelope_response(
            base_url="http://api",
            method="GET",
            path="/x",
            status=200,
            response_text="",
            data=payload,
        )
        self.assertIs(out, payload)

    def test_success_non_dict_returns_non_json_envelope(self) -> None:
        out = normalize_envelope_response(
            base_url="http://api",
            method="GET",
            path="/x",
            status=200,
            response_text="<html>not json</html>",
            data=None,
        )
        self.assertFalse(out["success"])
        self.assertEqual(out["code"], RaidHubEnvelopeCode.NON_JSON_RESPONSE.value)

    def test_server_error(self) -> None:
        out = normalize_envelope_response(
            base_url="http://api",
            method="GET",
            path="/x",
            status=503,
            response_text="",
            data=None,
        )
        self.assertFalse(out["success"])
        self.assertEqual(out["code"], RaidHubEnvelopeCode.RAIDHUB_API_SERVER_ERROR.value)

    def test_client_error_plain(self) -> None:
        out = normalize_envelope_response(
            base_url="http://api",
            method="GET",
            path="/subscriptions/discord/webhooks",
            status=404,
            response_text="Cannot GET",
            data=None,
        )
        self.assertFalse(out["success"])
        self.assertEqual(out["code"], RaidHubEnvelopeCode.RAIDHUB_API_CLIENT_ERROR.value)

    def test_client_error_returns_api_envelope(self) -> None:
        api_body = {
            "success": False,
            "code": "InsufficientPermissionsError",
            "error": {"message": "no"},
        }
        out = normalize_envelope_response(
            base_url="http://api",
            method="GET",
            path="/x",
            status=403,
            response_text="",
            data=api_body,
        )
        self.assertIs(out, api_body)


if __name__ == "__main__":
    unittest.main()
