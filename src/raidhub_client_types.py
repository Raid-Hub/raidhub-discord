from enum import StrEnum


class RaidHubEnvelopeCode(StrEnum):
    RAIDHUB_API_UNREACHABLE = "RaidHubApiUnreachable"
    NON_JSON_RESPONSE = "NonJsonResponse"
    RAIDHUB_API_SERVER_ERROR = "RaidHubApiServerError"
    RAIDHUB_API_CLIENT_ERROR = "RaidHubApiClientError"
