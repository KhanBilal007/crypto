from __future__ import annotations

import pytest

from abtp.observability import REDACTED_VALUE
from abtp.security import (
    EncryptedSecretRef,
    SecretFingerprint,
    assert_no_plaintext_secret_keys,
    is_secret_key,
    mask_secret,
)


def test_secret_masking_and_fingerprints_do_not_expose_plaintext() -> None:
    secret = "do-not-leak"
    fingerprint = SecretFingerprint.from_secret(secret)
    ref = EncryptedSecretRef(
        env_var="ABTP_LIVE_EXCHANGE_API_SECRET",
        key_id="local-kms",
        ciphertext_ref="env:ABTP_LIVE_EXCHANGE_API_SECRET",
        fingerprint=fingerprint,
    )

    payload = ref.as_dict()

    assert mask_secret(secret) == REDACTED_VALUE
    assert payload["fingerprint"] == fingerprint.short
    assert secret not in str(payload)
    assert secret not in repr(ref)


def test_secret_like_payload_keys_are_rejected_without_value_leakage() -> None:
    with pytest.raises(ValueError) as exc_info:
        assert_no_plaintext_secret_keys({"nested": {"api_key": "do-not-leak"}})

    assert "api_key" in str(exc_info.value)
    assert "do-not-leak" not in str(exc_info.value)


def test_secret_key_detection_matches_security_terms() -> None:
    assert is_secret_key("exchange_passphrase")
    assert is_secret_key("refresh_token")
    assert not is_secret_key("exchange_name")
