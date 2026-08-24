"""Validation and canonical serialization primitives."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
HASH_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")
LABEL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
QUANTITY_RE = re.compile(r"^0x(?:0|[1-9a-fA-F][0-9a-fA-F]*)$")
MAX_TOKENS = 256
MAX_ALLOWANCES = 1024


class WalletDiffError(ValueError):
    """A safe, user-facing validation or protocol failure."""


def address(value: Any, field: str) -> str:
    """Return a normalized 20-byte EVM address or fail closed."""
    if not isinstance(value, str) or not ADDRESS_RE.fullmatch(value):
        raise WalletDiffError(f"{field} must be a 20-byte 0x-prefixed address")
    return value.lower()


def quantity(value: Any, field: str) -> str:
    """Return a normalized minimal JSON-RPC quantity."""
    if not isinstance(value, str) or not QUANTITY_RE.fullmatch(value):
        raise WalletDiffError(f"{field} must be a minimal hexadecimal quantity")
    return hex(int(value, 16))


def uint256(value: Any, field: str) -> int:
    """Parse an exactly 32-byte ABI uint256 result."""
    if not isinstance(value, str) or not re.fullmatch(r"0x[0-9a-fA-F]{64}", value):
        raise WalletDiffError(f"{field} returned non-canonical uint256 data")
    return int(value, 16)


def block_hash(value: Any, field: str) -> str:
    if not isinstance(value, str) or not HASH_RE.fullmatch(value):
        raise WalletDiffError(f"{field} returned an invalid block hash")
    return value.lower()


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def load_json(path: str | Path, max_bytes: int = 2_000_000) -> Any:
    source = Path(path)
    if source.stat().st_size > max_bytes:
        raise WalletDiffError(f"{source} exceeds the {max_bytes}-byte limit")
    try:
        return json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise WalletDiffError(f"cannot read JSON from {source}: {exc}") from exc


def atomic_json(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(canonical_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, target)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def validate_spec(raw: Any) -> dict[str, Any]:
    """Validate and normalize a capture specification."""
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise WalletDiffError("spec schema_version must be 1")
    allowed = {"schema_version", "wallet", "from_block", "to_block", "tokens", "allowances"}
    extra = set(raw) - allowed
    if extra:
        raise WalletDiffError(f"unknown spec fields: {', '.join(sorted(extra))}")
    wallet = address(raw.get("wallet"), "wallet")
    before = quantity(raw.get("from_block"), "from_block")
    after = quantity(raw.get("to_block"), "to_block")
    if int(before, 16) >= int(after, 16):
        raise WalletDiffError("from_block must be less than to_block")
    tokens = raw.get("tokens", [])
    allowances = raw.get("allowances", [])
    if not isinstance(tokens, list) or len(tokens) > MAX_TOKENS:
        raise WalletDiffError(f"tokens must be a list with at most {MAX_TOKENS} entries")
    if not isinstance(allowances, list) or len(allowances) > MAX_ALLOWANCES:
        raise WalletDiffError(f"allowances must be a list with at most {MAX_ALLOWANCES} entries")

    def label(value: Any, field: str) -> str:
        if not isinstance(value, str) or not LABEL_RE.fullmatch(value):
            raise WalletDiffError(f"{field} must match {LABEL_RE.pattern}")
        return value

    normalized_tokens = []
    seen_contracts: set[str] = set()
    seen_labels: set[str] = set()
    for index, item in enumerate(tokens):
        if not isinstance(item, dict) or set(item) != {"contract", "label"}:
            raise WalletDiffError(f"tokens[{index}] requires exactly contract and label")
        contract = address(item["contract"], f"tokens[{index}].contract")
        item_label = label(item["label"], f"tokens[{index}].label")
        if contract in seen_contracts or item_label in seen_labels:
            raise WalletDiffError("token contracts and labels must be unique")
        seen_contracts.add(contract)
        seen_labels.add(item_label)
        normalized_tokens.append({"contract": contract, "label": item_label})
    normalized_allowances = []
    seen_pairs: set[tuple[str, str]] = set()
    seen_allowance_labels: set[str] = set()
    for index, item in enumerate(allowances):
        if not isinstance(item, dict) or set(item) != {"token", "spender", "label"}:
            raise WalletDiffError(f"allowances[{index}] requires exactly token, spender, and label")
        token = address(item["token"], f"allowances[{index}].token")
        spender = address(item["spender"], f"allowances[{index}].spender")
        item_label = label(item["label"], f"allowances[{index}].label")
        pair = (token, spender)
        if pair in seen_pairs or item_label in seen_allowance_labels:
            raise WalletDiffError("allowance token/spender pairs and labels must be unique")
        seen_pairs.add(pair)
        seen_allowance_labels.add(item_label)
        normalized_allowances.append({"token": token, "spender": spender, "label": item_label})
    return {"schema_version": 1, "wallet": wallet, "from_block": before, "to_block": after,
            "tokens": normalized_tokens, "allowances": normalized_allowances}
