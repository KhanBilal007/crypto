"""Secret redaction and encrypted-reference contracts."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from abtp.observability import REDACTED_VALUE

SECRET_KEY_PARTS = ("secret", "api_key", "password", "passphrase", "token", "credential")


@dataclass(frozen=True, slots=True)
class SecretFingerprint:
    """Non-secret fingerprint for comparing secret presence without storing values."""

    algorithm: str
    fingerprint: str

    def __post_init__(self) -> None:
        if self.algorithm != "sha256":
            raise ValueError("only sha256 fingerprints are supported in Stage 031")
        if len(self.fingerprint) != 64:
            raise ValueError("sha256 fingerprint must be 64 hex characters")

    @classmethod
    def from_secret(cls, value: str) -> SecretFingerprint:
        """Create a fingerprint; callers must not persist the plaintext input."""

        if not value:
            raise ValueError("secret value is required for fingerprinting")
        return cls(algorithm="sha256", fingerprint=sha256(value.encode("utf-8")).hexdigest())

    @property
    def short(self) -> str:
        return self.fingerprint[:8]


@dataclass(frozen=True, slots=True)
class EncryptedSecretRef:
    """Reference to an encrypted secret stored outside ABTP runtime objects."""

    env_var: str
    key_id: str
    ciphertext_ref: str
    algorithm: str = "external-kms"
    fingerprint: SecretFingerprint | None = None

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.env_var, "env_var"),
            (self.key_id, "key_id"),
            (self.ciphertext_ref, "ciphertext_ref"),
            (self.algorithm, "algorithm"),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} is required")

    def as_dict(self) -> dict[str, str | None]:
        """Return metadata only; never return plaintext secret material."""

        return {
            "env_var": self.env_var,
            "key_id": self.key_id,
            "ciphertext_ref": self.ciphertext_ref,
            "algorithm": self.algorithm,
            "fingerprint": self.fingerprint.short if self.fingerprint else None,
        }


def mask_secret(value: str | None) -> str:
    """Return a display-safe secret mask."""

    return REDACTED_VALUE if value else "<missing>"


def is_secret_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in SECRET_KEY_PARTS)


def assert_no_plaintext_secret_keys(payload: dict[str, object]) -> None:
    """Reject payloads that would store secret-like keys."""

    for key, value in payload.items():
        if is_secret_key(key):
            raise ValueError(f"secret-like key is not allowed: {key}")
        if isinstance(value, dict):
            assert_no_plaintext_secret_keys(value)
