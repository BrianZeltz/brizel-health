"""Backup/recovery key hierarchy models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

KEY_FORMAT_VERSION = 1

PROTECTED_DATA_CLASS_PROFILE_CONTEXT = "profile_context"
PROTECTED_DATA_CLASS_HISTORY_PAYLOADS = "history_payloads"
PROTECTED_DATA_CLASS_SYNC_STATE = "sync_state"
PROTECTED_DATA_CLASS_KEY_METADATA = "key_metadata"
PROTECTED_DATA_CLASS_KEY_MATERIAL = "key_material"

NODE_KEY_ALGORITHM = "node_key_random_256_v1"
NODE_ENROLLMENT_ALGORITHM = "node_enrollment_x25519_hkdf_sha256_v1"
PROFILE_KEY_ALGORITHM = "profile_key_random_256_v1"
LOCAL_KEY_PROTECTION_CLASS = "home_assistant_store_local_v1"

ENVELOPE_RECIPIENT_NODE = "node"
ENVELOPE_RECIPIENT_RECOVERY = "recovery"

ENVELOPE_WRAP_MECHANISM_LOCAL_DIRECT = "local_direct_access_v1"
ENVELOPE_WRAP_MECHANISM_NODE_PREPARED = "node_profile_envelope_prep_v1"
ENVELOPE_WRAP_MECHANISM_NODE_WRAPPED = "node_profile_key_aead_wrap_v1"
ENVELOPE_WRAP_MECHANISM_NODE_ENROLLMENT_WRAPPED = (
    "node_enrollment_x25519_aead_wrap_v1"
)
ENVELOPE_WRAP_MECHANISM_RECOVERY_PREPARED = (
    "recovery_passphrase_envelope_prep_v1"
)
ENVELOPE_WRAP_MECHANISM_RECOVERY_KEY_WRAPPED = "recovery_key_aead_wrap_v1"
ENVELOPE_WRAP_MECHANISM_RECOVERY_PASSPHRASE_WRAPPED = (
    "recovery_passphrase_aead_wrap_v1"
)

ENVELOPE_MATERIAL_STATE_LOCAL_DIRECT = "local_direct_access"
ENVELOPE_MATERIAL_STATE_PENDING_WRAP = "pending_wrap"
ENVELOPE_MATERIAL_STATE_WRAPPED = "wrapped"

JOIN_REQUEST_STATUS_PENDING = "pending"
JOIN_REQUEST_STATUS_APPROVED = "approved"
JOIN_REQUEST_STATUS_COMPLETED = "completed"
JOIN_REQUEST_STATUS_INVALIDATED = "invalidated"
JOIN_REQUEST_STATUS_EXPIRED = "expired"

RECOVERY_METHOD_PASSPHRASE = "passphrase"
RECOVERY_METHOD_DIRECT_KEY = "recovery_key"
RECOVERY_KDF_NONE = "none"
RECOVERY_KDF_PBKDF2_SHA256 = "pbkdf2_hmac_sha256"
LOCAL_PAYLOAD_AEAD_ALGORITHM = "aes_gcm_256_v1"
LOCAL_PAYLOAD_FORMAT_VERSION = 1
LOCAL_WRAPPED_KEY_FORMAT_VERSION = 1

AUDIT_SEVERITY_ERROR = "error"
AUDIT_SEVERITY_WARNING = "warning"


@dataclass(frozen=True)
class ProtectedStorageClass:
    """One logical storage class for future at-rest protection planning."""

    data_class_id: str
    encrypt_at_rest: bool
    visible_metadata_fields: tuple[str, ...]
    sync_visible_fields: tuple[str, ...]
    description: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProtectedStorageClass":
        return cls(
            data_class_id=str(data.get("data_class_id") or "").strip(),
            encrypt_at_rest=data.get("encrypt_at_rest") is True,
            visible_metadata_fields=tuple(_string_list(data.get("visible_metadata_fields"))),
            sync_visible_fields=tuple(_string_list(data.get("sync_visible_fields"))),
            description=str(data.get("description") or "").strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "data_class_id": self.data_class_id,
            "encrypt_at_rest": self.encrypt_at_rest,
            "visible_metadata_fields": list(self.visible_metadata_fields),
            "sync_visible_fields": list(self.sync_visible_fields),
            "description": self.description,
        }


def default_storage_protection_plan() -> tuple[ProtectedStorageClass, ...]:
    """Return the shared logical storage plan for backup/recovery."""
    return (
        ProtectedStorageClass(
            data_class_id=PROTECTED_DATA_CLASS_PROFILE_CONTEXT,
            encrypt_at_rest=True,
            visible_metadata_fields=(
                "profile_id",
                "updated_at",
            ),
            sync_visible_fields=("profile_id", "updated_at"),
            description=(
                "Stable profile context should later live encrypted at rest, "
                "while link/routing metadata remains visible."
            ),
        ),
        ProtectedStorageClass(
            data_class_id=PROTECTED_DATA_CLASS_HISTORY_PAYLOADS,
            encrypt_at_rest=True,
            visible_metadata_fields=(
                "record_id",
                "record_type",
                "profile_id",
                "revision",
                "updated_at",
                "updated_by_node_id",
                "deleted_at",
                "source_type",
                "source_detail",
            ),
            sync_visible_fields=(
                "record_id",
                "record_type",
                "profile_id",
                "revision",
                "updated_at",
                "updated_by_node_id",
                "deleted_at",
            ),
            description=(
                "Core record payloads should later be encrypted, while "
                "cursor/tombstone metadata stays sync-visible."
            ),
        ),
        ProtectedStorageClass(
            data_class_id=PROTECTED_DATA_CLASS_SYNC_STATE,
            encrypt_at_rest=False,
            visible_metadata_fields=(
                "profile_id",
                "domain",
                "cursor",
                "updated_after",
                "outbox_updated_after",
            ),
            sync_visible_fields=(
                "domain",
                "cursor",
                "updated_after",
                "outbox_updated_after",
            ),
            description=(
                "Sync cursors and diagnostics remain plaintext control data, "
                "not encrypted payload truth."
            ),
        ),
        ProtectedStorageClass(
            data_class_id=PROTECTED_DATA_CLASS_KEY_METADATA,
            encrypt_at_rest=False,
            visible_metadata_fields=(
                "node_id",
                "node_key_id",
                "profile_key_id",
                "recipient_kind",
                "recipient_id",
                "wrap_mechanism",
                "material_state",
                "created_at",
                "updated_at",
            ),
            sync_visible_fields=(),
            description=(
                "Key hierarchy metadata and envelope headers remain separated "
                "from secret key material."
            ),
        ),
        ProtectedStorageClass(
            data_class_id=PROTECTED_DATA_CLASS_KEY_MATERIAL,
            encrypt_at_rest=True,
            visible_metadata_fields=(),
            sync_visible_fields=(),
            description=(
                "Node keys, profile keys, and future wrapped-key blobs belong "
                "to the secret material layer."
            ),
        ),
    )


@dataclass(frozen=True)
class ServerNodeKeyContext:
    """Server-side trust-node key context."""

    node_id: str
    node_key_id: str
    key_version: int
    algorithm: str
    protection_class: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ServerNodeKeyContext":
        created_at = _parse_datetime(data.get("created_at")) or datetime.fromtimestamp(
            0,
            UTC,
        )
        return cls(
            node_id=str(data.get("node_id") or "").strip(),
            node_key_id=str(data.get("node_key_id") or "").strip(),
            key_version=int(data.get("key_version") or 1),
            algorithm=str(data.get("algorithm") or NODE_KEY_ALGORITHM).strip(),
            protection_class=str(
                data.get("protection_class") or LOCAL_KEY_PROTECTION_CLASS
            ).strip(),
            created_at=created_at,
            updated_at=_parse_datetime(data.get("updated_at")) or created_at,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_key_id": self.node_key_id,
            "key_version": self.key_version,
            "algorithm": self.algorithm,
            "protection_class": self.protection_class,
            "created_at": _format_datetime(self.created_at),
            "updated_at": _format_datetime(self.updated_at),
        }


@dataclass(frozen=True)
class NodeEnrollmentContext:
    """Join-/Enrollment recipient context for a node."""

    node_id: str
    recipient_key_id: str
    key_version: int
    algorithm: str
    public_key_b64: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NodeEnrollmentContext":
        created_at = _parse_datetime(data.get("created_at")) or datetime.fromtimestamp(
            0,
            UTC,
        )
        return cls(
            node_id=str(data.get("node_id") or "").strip(),
            recipient_key_id=str(data.get("recipient_key_id") or "").strip(),
            key_version=int(data.get("key_version") or 1),
            algorithm=str(data.get("algorithm") or NODE_ENROLLMENT_ALGORITHM).strip(),
            public_key_b64=str(data.get("public_key_b64") or "").strip(),
            created_at=created_at,
            updated_at=_parse_datetime(data.get("updated_at")) or created_at,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "recipient_key_id": self.recipient_key_id,
            "key_version": self.key_version,
            "algorithm": self.algorithm,
            "public_key_b64": self.public_key_b64,
            "created_at": _format_datetime(self.created_at),
            "updated_at": _format_datetime(self.updated_at),
        }

    def to_descriptor(self) -> "NodeEnrollmentDescriptor":
        return NodeEnrollmentDescriptor(
            node_id=self.node_id,
            recipient_key_id=self.recipient_key_id,
            key_version=self.key_version,
            algorithm=self.algorithm,
            public_key_b64=self.public_key_b64,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


@dataclass(frozen=True)
class NodeEnrollmentDescriptor:
    """Shareable public recipient metadata for node join."""

    node_id: str
    recipient_key_id: str
    key_version: int
    algorithm: str
    public_key_b64: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NodeEnrollmentDescriptor":
        created_at = _parse_datetime(data.get("created_at")) or datetime.fromtimestamp(
            0,
            UTC,
        )
        return cls(
            node_id=str(data.get("node_id") or "").strip(),
            recipient_key_id=str(data.get("recipient_key_id") or "").strip(),
            key_version=int(data.get("key_version") or 1),
            algorithm=str(data.get("algorithm") or NODE_ENROLLMENT_ALGORITHM).strip(),
            public_key_b64=str(data.get("public_key_b64") or "").strip(),
            created_at=created_at,
            updated_at=_parse_datetime(data.get("updated_at")) or created_at,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "recipient_key_id": self.recipient_key_id,
            "key_version": self.key_version,
            "algorithm": self.algorithm,
            "public_key_b64": self.public_key_b64,
            "created_at": _format_datetime(self.created_at),
            "updated_at": _format_datetime(self.updated_at),
        }


@dataclass(frozen=True)
class JoinEnrollmentRequest:
    """One request-bound enrollment/re-enrollment intent for a target node."""

    request_id: str
    profile_id: str
    requesting_node_id: str
    recipient: NodeEnrollmentDescriptor
    requested_at: datetime
    expires_at: datetime
    status: str
    approval_id: str | None = None
    approval_envelope_id: str | None = None
    approved_by_node_id: str | None = None
    approved_by_node_key_id: str | None = None
    approved_at: datetime | None = None
    completed_at: datetime | None = None
    invalidated_at: datetime | None = None
    invalidation_reason: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JoinEnrollmentRequest":
        requested_at = _parse_datetime(data.get("requested_at")) or datetime.fromtimestamp(
            0,
            UTC,
        )
        recipient_raw = data.get("recipient")
        return cls(
            request_id=str(data.get("request_id") or "").strip(),
            profile_id=str(data.get("profile_id") or "").strip(),
            requesting_node_id=str(data.get("requesting_node_id") or "").strip(),
            recipient=NodeEnrollmentDescriptor.from_dict(
                dict(recipient_raw) if isinstance(recipient_raw, dict) else {}
            ),
            requested_at=requested_at,
            expires_at=_parse_datetime(data.get("expires_at")) or requested_at,
            status=str(data.get("status") or JOIN_REQUEST_STATUS_PENDING).strip(),
            approval_id=_optional_text(data.get("approval_id")),
            approval_envelope_id=_optional_text(data.get("approval_envelope_id")),
            approved_by_node_id=_optional_text(data.get("approved_by_node_id")),
            approved_by_node_key_id=_optional_text(
                data.get("approved_by_node_key_id")
            ),
            approved_at=_parse_datetime(data.get("approved_at")),
            completed_at=_parse_datetime(data.get("completed_at")),
            invalidated_at=_parse_datetime(data.get("invalidated_at")),
            invalidation_reason=_optional_text(data.get("invalidation_reason")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "profile_id": self.profile_id,
            "requesting_node_id": self.requesting_node_id,
            "recipient": self.recipient.to_dict(),
            "requested_at": _format_datetime(self.requested_at),
            "expires_at": _format_datetime(self.expires_at),
            "status": self.status,
            "approval_id": self.approval_id,
            "approval_envelope_id": self.approval_envelope_id,
            "approved_by_node_id": self.approved_by_node_id,
            "approved_by_node_key_id": self.approved_by_node_key_id,
            "approved_at": (
                _format_datetime(self.approved_at) if self.approved_at else None
            ),
            "completed_at": (
                _format_datetime(self.completed_at) if self.completed_at else None
            ),
            "invalidated_at": (
                _format_datetime(self.invalidated_at)
                if self.invalidated_at
                else None
            ),
            "invalidation_reason": self.invalidation_reason,
        }


@dataclass(frozen=True)
class ProfileKeyContext:
    """One shared logical profile key tracked on HA."""

    profile_id: str
    profile_key_id: str
    key_version: int
    algorithm: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProfileKeyContext":
        created_at = _parse_datetime(data.get("created_at")) or datetime.fromtimestamp(
            0,
            UTC,
        )
        return cls(
            profile_id=str(data.get("profile_id") or "").strip(),
            profile_key_id=str(data.get("profile_key_id") or "").strip(),
            key_version=int(data.get("key_version") or 1),
            algorithm=str(data.get("algorithm") or PROFILE_KEY_ALGORITHM).strip(),
            created_at=created_at,
            updated_at=_parse_datetime(data.get("updated_at")) or created_at,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "profile_key_id": self.profile_key_id,
            "key_version": self.key_version,
            "algorithm": self.algorithm,
            "created_at": _format_datetime(self.created_at),
            "updated_at": _format_datetime(self.updated_at),
        }


@dataclass(frozen=True)
class WrappedProfileKeyEnvelope:
    """Metadata describing one node/recovery recipient slot."""

    envelope_id: str
    profile_key_id: str
    profile_key_version: int
    recipient_kind: str
    recipient_id: str
    wrap_mechanism: str
    material_state: str
    wrapped_key_material_id: str | None
    wrapped_key_material: str | None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WrappedProfileKeyEnvelope":
        created_at = _parse_datetime(data.get("created_at")) or datetime.fromtimestamp(
            0,
            UTC,
        )
        raw_metadata = data.get("metadata")
        return cls(
            envelope_id=str(data.get("envelope_id") or "").strip(),
            profile_key_id=str(data.get("profile_key_id") or "").strip(),
            profile_key_version=int(data.get("profile_key_version") or 1),
            recipient_kind=str(
                data.get("recipient_kind") or ENVELOPE_RECIPIENT_NODE
            ).strip(),
            recipient_id=str(data.get("recipient_id") or "").strip(),
            wrap_mechanism=str(
                data.get("wrap_mechanism") or ENVELOPE_WRAP_MECHANISM_LOCAL_DIRECT
            ).strip(),
            material_state=str(
                data.get("material_state") or ENVELOPE_MATERIAL_STATE_PENDING_WRAP
            ).strip(),
            wrapped_key_material_id=_optional_text(
                data.get("wrapped_key_material_id")
            ),
            wrapped_key_material=_optional_text(data.get("wrapped_key_material")),
            metadata=dict(raw_metadata) if isinstance(raw_metadata, dict) else {},
            created_at=created_at,
            updated_at=_parse_datetime(data.get("updated_at")) or created_at,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "envelope_id": self.envelope_id,
            "profile_key_id": self.profile_key_id,
            "profile_key_version": self.profile_key_version,
            "recipient_kind": self.recipient_kind,
            "recipient_id": self.recipient_id,
            "wrap_mechanism": self.wrap_mechanism,
            "material_state": self.material_state,
            "wrapped_key_material_id": self.wrapped_key_material_id,
            "wrapped_key_material": self.wrapped_key_material,
            "metadata": self.metadata,
            "created_at": _format_datetime(self.created_at),
            "updated_at": _format_datetime(self.updated_at),
        }


@dataclass(frozen=True)
class RecoveryKeyMetadata:
    """Portable recovery descriptor, currently passphrase-prep only."""

    recovery_id: str
    kind: str
    kdf_algorithm: str
    iterations: int
    salt_b64: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RecoveryKeyMetadata":
        created_at = _parse_datetime(data.get("created_at")) or datetime.fromtimestamp(
            0,
            UTC,
        )
        return cls(
            recovery_id=str(data.get("recovery_id") or "").strip(),
            kind=str(data.get("kind") or RECOVERY_METHOD_PASSPHRASE).strip(),
            kdf_algorithm=str(
                data.get("kdf_algorithm") or RECOVERY_KDF_PBKDF2_SHA256
            ).strip(),
            iterations=int(data.get("iterations") or 0),
            salt_b64=str(data.get("salt_b64") or "").strip(),
            created_at=created_at,
            updated_at=_parse_datetime(data.get("updated_at")) or created_at,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "recovery_id": self.recovery_id,
            "kind": self.kind,
            "kdf_algorithm": self.kdf_algorithm,
            "iterations": self.iterations,
            "salt_b64": self.salt_b64,
            "created_at": _format_datetime(self.created_at),
            "updated_at": _format_datetime(self.updated_at),
        }


@dataclass(frozen=True)
class WrappedKeyMaterialBlob:
    """AES-GCM wrapped profile-key material for one local direct-access slot."""

    format_version: int
    algorithm: str
    nonce_b64: str
    cipher_text_b64: str
    mac_b64: str
    aad_context: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WrappedKeyMaterialBlob":
        raw_aad = data.get("aad_context")
        return cls(
            format_version=int(data.get("format_version") or LOCAL_WRAPPED_KEY_FORMAT_VERSION),
            algorithm=str(data.get("algorithm") or LOCAL_PAYLOAD_AEAD_ALGORITHM).strip(),
            nonce_b64=str(data.get("nonce_b64") or "").strip(),
            cipher_text_b64=str(data.get("cipher_text_b64") or "").strip(),
            mac_b64=str(data.get("mac_b64") or "").strip(),
            aad_context=dict(raw_aad) if isinstance(raw_aad, dict) else {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "format_version": self.format_version,
            "algorithm": self.algorithm,
            "nonce_b64": self.nonce_b64,
            "cipher_text_b64": self.cipher_text_b64,
            "mac_b64": self.mac_b64,
            "aad_context": self.aad_context,
        }


@dataclass(frozen=True)
class EncryptedPayloadEnvelope:
    """One encrypted at-rest payload plus visible envelope metadata."""

    format_version: int
    algorithm: str
    data_class_id: str
    profile_key_id: str
    profile_key_version: int
    nonce_b64: str
    cipher_text_b64: str
    mac_b64: str
    aad_context: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EncryptedPayloadEnvelope":
        raw_aad = data.get("aad_context")
        return cls(
            format_version=int(data.get("format_version") or LOCAL_PAYLOAD_FORMAT_VERSION),
            algorithm=str(data.get("algorithm") or LOCAL_PAYLOAD_AEAD_ALGORITHM).strip(),
            data_class_id=str(data.get("data_class_id") or "").strip(),
            profile_key_id=str(data.get("profile_key_id") or "").strip(),
            profile_key_version=int(data.get("profile_key_version") or 1),
            nonce_b64=str(data.get("nonce_b64") or "").strip(),
            cipher_text_b64=str(data.get("cipher_text_b64") or "").strip(),
            mac_b64=str(data.get("mac_b64") or "").strip(),
            aad_context=dict(raw_aad) if isinstance(raw_aad, dict) else {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "format_version": self.format_version,
            "algorithm": self.algorithm,
            "data_class_id": self.data_class_id,
            "profile_key_id": self.profile_key_id,
            "profile_key_version": self.profile_key_version,
            "nonce_b64": self.nonce_b64,
            "cipher_text_b64": self.cipher_text_b64,
            "mac_b64": self.mac_b64,
            "aad_context": self.aad_context,
        }


@dataclass(frozen=True)
class KeyHierarchyAuditFinding:
    """One machine-readable key hierarchy audit finding."""

    severity: str
    kind: str
    code: str
    description: str
    profile_key_id: str | None = None
    envelope_id: str | None = None
    recovery_id: str | None = None
    request_id: str | None = None
    wrapped_key_material_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "kind": self.kind,
            "code": self.code,
            "description": self.description,
            "profile_key_id": self.profile_key_id,
            "envelope_id": self.envelope_id,
            "recovery_id": self.recovery_id,
            "request_id": self.request_id,
            "wrapped_key_material_id": self.wrapped_key_material_id,
            "details": self.details,
        }


@dataclass(frozen=True)
class KeyHierarchyAuditReport:
    """Structured audit report for one key hierarchy snapshot."""

    findings: tuple[KeyHierarchyAuditFinding, ...] = ()

    @property
    def has_errors(self) -> bool:
        return any(
            finding.severity == AUDIT_SEVERITY_ERROR for finding in self.findings
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "findings": [finding.to_dict() for finding in self.findings],
            "has_errors": self.has_errors,
        }


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        normalized = _optional_text(item)
        if normalized is not None:
            result.append(normalized)
    return result


def _optional_text(value: Any) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _parse_datetime(value: Any) -> datetime | None:
    text = _optional_text(value)
    if text is None:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _format_datetime(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
