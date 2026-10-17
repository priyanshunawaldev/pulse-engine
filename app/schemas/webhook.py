import ipaddress
import uuid
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

RESTRICTED_IP_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local and AWS/cloud metadata (169.254.169.254)
    ipaddress.ip_network("100.64.0.0/10"),  # Carrier-grade NAT / Alibaba Cloud metadata (100.100.100.200)
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("255.255.255.255/32"),
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("::ffff:0:0/96"),  # IPv4-mapped IPv6
]

TEST_DOMAINS = (".internal", ".test", ".example", ".invalid")


def mask_webhook_secret(secret: str) -> str:
    """Mask webhook HMAC secret so plaintext secrets are never exposed on list endpoints."""
    return "whsec_***"


def is_ip_private_or_restricted(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an IP address belongs to RFC 1918 private, loopback, link-local, or cloud metadata ranges."""
    if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        return True
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        if is_ip_private_or_restricted(ip.ipv4_mapped):
            return True
    return any(ip in net for net in RESTRICTED_IP_NETWORKS)


def validate_target_url(url: str) -> str:
    """
    SSRF Guard (Vibe Block 26):
    Validates webhook target URL to reject private, loopback, and cloud metadata addresses.
    Enforces http/https scheme. Preserves test domains (.internal, .test, testserver) for mocking/testing.
    """
    if not url or not isinstance(url, str):
        raise ValueError("Webhook target URL must be a non-empty string.")

    parsed = urlsplit(url.strip())
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise ValueError(f"Invalid URL scheme '{scheme}'. Webhooks only support 'http' and 'https'.")

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise ValueError("Invalid target URL: hostname is required.")

    # Reject localhost explicitly
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise ValueError(f"Webhook target URL '{hostname}' is not permitted (loopback address rejected).")

    # Reject mDNS / local domain names
    if hostname == "local" or hostname.endswith(".local"):
        raise ValueError(f"Webhook target URL '{hostname}' is forbidden (local/mDNS address rejected).")

    # Reject cloud metadata hostnames
    if hostname in ("instance-data", "metadata.google.internal") or hostname.endswith(".metadata.google.internal"):
        raise ValueError(f"Webhook target URL '{hostname}' is forbidden (cloud metadata host).")

    # Allow test environments and reserved testing TLDs
    if hostname == "testserver" or any(hostname.endswith(tld) for tld in TEST_DOMAINS):
        return url

    # Validate raw IP addresses
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        ip = None

    if ip is not None:
        if is_ip_private_or_restricted(ip):
            raise ValueError(f"Webhook target URL IP '{hostname}' is forbidden (private/cloud metadata address).")
        return url

    return url


class WebhookSubscriptionCreateSchema(BaseModel):
    account_id: uuid.UUID
    target_url: str = Field(..., max_length=512, json_schema_extra={"example": "https://api.example.com/webhooks/pulseengine"})
    event_types: list[str] = Field(
        default=["transaction.completed", "transaction.reversed"],
        min_length=1,
        json_schema_extra={"example": ["transaction.completed"]},
    )

    @field_validator("target_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return validate_target_url(v)


class WebhookSubscriptionResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    target_url: str
    event_types: list[str]
    secret: str
    is_active: bool
    created_at: datetime


class WebhookSubscriptionListResponseSchema(BaseModel):
    items: list[WebhookSubscriptionResponseSchema]
    next_cursor: str | None = None
    has_more: bool = False


class WebhookDeliveryResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subscription_id: uuid.UUID
    transaction_id: uuid.UUID
    event_type: str
    payload: dict[str, Any]
    attempt_count: int
    last_attempt_at: datetime | None
    next_retry_at: datetime | None
    status: str
    response_status_code: int | None
    error_detail: str | None
    created_at: datetime


class WebhookDeliveryListResponseSchema(BaseModel):
    items: list[WebhookDeliveryResponseSchema]
    next_cursor: str | None = None
    has_more: bool = False
