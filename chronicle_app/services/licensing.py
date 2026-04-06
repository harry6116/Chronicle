from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


LICENSE_FILENAME = "chronicle-license.json"
PUBLIC_KEY_FILENAME = "chronicle_license_public_key.pem"
PUBLIC_KEY_ENV = "CHRONICLE_LICENSE_PUBLIC_KEY"
PUBLIC_KEY_FILE_ENV = "CHRONICLE_LICENSE_PUBLIC_KEY_FILE"
REQUIRED_LICENSE_FIELDS = (
    "product",
    "license_version",
    "license_id",
    "issued_to",
    "email",
    "organization",
    "tier",
    "seats",
    "issued_at",
    "valid_for_major_version",
    "notes",
)


class LicenseError(ValueError):
    pass


@dataclass(frozen=True)
class LicenseValidationResult:
    valid: bool
    reason: str
    license_data: dict[str, Any] | None = None


def format_license_status(
    validation_result: LicenseValidationResult | None,
    *,
    public_key_available: bool,
    public_key_error: str = "",
) -> str:
    if public_key_error:
        return (
            "License system error\n\n"
            f"{public_key_error.strip()}"
        )

    if not public_key_available:
        return (
            "License verification key not configured\n\n"
            "Chronicle cannot verify or import signed licenses on this machine until a public verification key is available."
        )

    if validation_result is None:
        return "License status unavailable"

    if not validation_result.valid or not validation_result.license_data:
        if validation_result.reason == "No installed license found.":
            return "No license installed\n\nChronicle is currently unlicensed on this machine."
        return f"License not valid\n\n{validation_result.reason}"

    data = validation_result.license_data
    lines = [
        "License installed and valid",
        "",
        f"Licensed to: {data.get('issued_to', '')}",
        f"Email: {data.get('email', '')}",
    ]
    organization = str(data.get("organization", "") or "").strip()
    if organization:
        lines.append(f"Organization: {organization}")
    lines.extend(
        [
            f"Tier: {data.get('tier', '')}",
            f"Seats: {data.get('seats', '')}",
            f"Major version: {data.get('valid_for_major_version', '')}",
            f"License ID: {data.get('license_id', '')}",
            f"Issued: {data.get('issued_at', '')}",
        ]
    )
    notes = str(data.get("notes", "") or "").strip()
    if notes:
        lines.append(f"Notes: {notes}")
    return "\n".join(lines)


def generate_keypair() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    private_key = Ed25519PrivateKey.generate()
    return private_key, private_key.public_key()


def serialize_private_key_pem(private_key: Ed25519PrivateKey) -> bytes:
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def serialize_public_key_pem(public_key: Ed25519PublicKey) -> bytes:
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def load_private_key_pem(pem_bytes: bytes) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(pem_bytes, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise LicenseError("Expected an Ed25519 private key.")
    return key


def load_public_key_pem(pem_bytes: bytes) -> Ed25519PublicKey:
    key = serialization.load_pem_public_key(pem_bytes)
    if not isinstance(key, Ed25519PublicKey):
        raise LicenseError("Expected an Ed25519 public key.")
    return key


def _normalize_license_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = {}
    for field in REQUIRED_LICENSE_FIELDS:
        if field not in payload:
            raise LicenseError(f"Missing required license field: {field}")
        value = payload[field]
        if field == "seats":
            try:
                value = int(value)
            except (TypeError, ValueError) as exc:
                raise LicenseError("License field 'seats' must be an integer.") from exc
            if value < 1:
                raise LicenseError("License field 'seats' must be at least 1.")
        else:
            value = "" if value is None else str(value)
            if field not in {"organization", "notes"} and not value.strip():
                raise LicenseError(f"License field '{field}' cannot be empty.")
            value = value.strip()
        normalized[field] = value
    return normalized


def canonicalize_license_payload(payload: dict[str, Any]) -> bytes:
    normalized = _normalize_license_payload(payload)
    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def sign_license_payload(payload: dict[str, Any], private_key: Ed25519PrivateKey) -> dict[str, Any]:
    normalized = _normalize_license_payload(payload)
    signature = private_key.sign(canonicalize_license_payload(normalized))
    signed = dict(normalized)
    signed["signature"] = base64.b64encode(signature).decode("ascii")
    return signed


def verify_license_data(license_data: dict[str, Any], public_key: Ed25519PublicKey) -> LicenseValidationResult:
    if not isinstance(license_data, dict):
        return LicenseValidationResult(valid=False, reason="License data must be a JSON object.")

    signature_text = str(license_data.get("signature", "")).strip()
    if not signature_text:
        return LicenseValidationResult(valid=False, reason="License signature is missing.")

    payload = {key: value for key, value in license_data.items() if key != "signature"}
    try:
        normalized = _normalize_license_payload(payload)
    except LicenseError as exc:
        return LicenseValidationResult(valid=False, reason=str(exc))

    try:
        signature = base64.b64decode(signature_text, validate=True)
    except Exception:
        return LicenseValidationResult(valid=False, reason="License signature is not valid base64.")

    try:
        public_key.verify(signature, canonicalize_license_payload(normalized))
    except InvalidSignature:
        return LicenseValidationResult(valid=False, reason="License signature verification failed.")

    verified = dict(normalized)
    verified["signature"] = signature_text
    return LicenseValidationResult(valid=True, reason="ok", license_data=verified)


def load_license_file(path: os.PathLike[str] | str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise LicenseError("License file must contain a JSON object.")
    return data


def write_license_file(path: os.PathLike[str] | str, license_data: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(license_data, fh, indent=2, sort_keys=True)
        fh.write("\n")


def resolve_public_key_path(*, app_data_dir: str | None = None, script_dir: str | None = None) -> str | None:
    env_path = os.environ.get(PUBLIC_KEY_FILE_ENV, "").strip()
    if env_path:
        return env_path

    candidate_dirs = []
    if app_data_dir:
        candidate_dirs.append(app_data_dir)
    if script_dir:
        candidate_dirs.append(script_dir)
        candidate_dirs.append(os.path.join(script_dir, "assets"))

    for root in candidate_dirs:
        candidate = os.path.join(root, PUBLIC_KEY_FILENAME)
        if os.path.exists(candidate):
            return candidate
    return None


def resolve_public_key(*, app_data_dir: str | None = None, script_dir: str | None = None) -> Ed25519PublicKey | None:
    env_pem = os.environ.get(PUBLIC_KEY_ENV, "").strip()
    if env_pem:
        return load_public_key_pem(env_pem.encode("utf-8"))

    public_key_path = resolve_public_key_path(app_data_dir=app_data_dir, script_dir=script_dir)
    if public_key_path:
        with open(public_key_path, "rb") as fh:
            return load_public_key_pem(fh.read())
    return None


def resolve_license_store_path(*, app_data_dir: str) -> str:
    return os.path.join(app_data_dir, LICENSE_FILENAME)


def install_license_file(
    source_path: os.PathLike[str] | str,
    *,
    app_data_dir: str,
    public_key: Ed25519PublicKey,
) -> LicenseValidationResult:
    license_data = load_license_file(source_path)
    result = verify_license_data(license_data, public_key)
    if not result.valid or result.license_data is None:
        return result

    os.makedirs(app_data_dir, exist_ok=True)
    destination = resolve_license_store_path(app_data_dir=app_data_dir)
    write_license_file(destination, result.license_data)
    return result


def load_installed_license(
    *,
    app_data_dir: str,
    public_key: Ed25519PublicKey,
) -> LicenseValidationResult:
    license_path = resolve_license_store_path(app_data_dir=app_data_dir)
    if not os.path.exists(license_path):
        return LicenseValidationResult(valid=False, reason="No installed license found.")
    return verify_license_data(load_license_file(license_path), public_key)


def build_license_payload(
    *,
    license_id: str,
    issued_to: str,
    email: str,
    organization: str = "",
    tier: str,
    seats: int = 1,
    issued_at: str | None = None,
    valid_for_major_version: str = "1",
    notes: str = "",
    product: str = "Chronicle",
    license_version: int = 1,
) -> dict[str, Any]:
    return {
        "product": product,
        "license_version": license_version,
        "license_id": license_id,
        "issued_to": issued_to,
        "email": email,
        "organization": organization,
        "tier": tier,
        "seats": seats,
        "issued_at": issued_at or date.today().isoformat(),
        "valid_for_major_version": valid_for_major_version,
        "notes": notes,
    }


def save_keypair(
    *,
    private_key_path: os.PathLike[str] | str,
    public_key_path: os.PathLike[str] | str,
) -> tuple[str, str]:
    private_key, public_key = generate_keypair()
    private_path = Path(private_key_path)
    public_path = Path(public_key_path)
    private_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.parent.mkdir(parents=True, exist_ok=True)
    private_path.write_bytes(serialize_private_key_pem(private_key))
    public_path.write_bytes(serialize_public_key_pem(public_key))
    return str(private_path), str(public_path)
