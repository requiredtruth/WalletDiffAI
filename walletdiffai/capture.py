"""Exact-block capture with before/after header consistency checks."""

from __future__ import annotations

import hashlib
from typing import Any

from .abi import allowance, balance_of
from .core import WalletDiffError, block_hash, quantity, uint256, validate_spec


def _header(rpc: Any, number: str) -> dict[str, str]:
    result = rpc.call("eth_getBlockByNumber", [number, False])
    if not isinstance(result, dict):
        raise WalletDiffError(f"block {number} is unavailable")
    returned = quantity(result.get("number"), "block.number")
    if returned != number:
        raise WalletDiffError(f"RPC returned block {returned} for requested block {number}")
    return {"number": returned, "hash": block_hash(result.get("hash"), "block.hash")}


def _snapshot(rpc: Any, spec: dict[str, Any], block: dict[str, str]) -> dict[str, Any]:
    wallet = spec["wallet"]
    tag = block["number"]
    native = int(quantity(rpc.call("eth_getBalance", [wallet, tag]), "eth_getBalance"), 16)
    nonce = int(quantity(rpc.call("eth_getTransactionCount", [wallet, tag]), "eth_getTransactionCount"), 16)
    code = rpc.call("eth_getCode", [wallet, tag])
    if not isinstance(code, str) or not code.startswith("0x") or len(code) % 2 or any(c not in "0123456789abcdefABCDEF" for c in code[2:]):
        raise WalletDiffError("eth_getCode returned invalid byte data")
    code_bytes = bytes.fromhex(code[2:])
    tokens = []
    for item in spec["tokens"]:
        result = rpc.call("eth_call", [{"to": item["contract"], "data": balance_of(wallet)}, tag])
        tokens.append({"label": item["label"], "contract": item["contract"],
                       "value": str(uint256(result, f"token {item['label']}"))})
    allowances = []
    for item in spec["allowances"]:
        result = rpc.call("eth_call", [{"to": item["token"],
                                         "data": allowance(wallet, item["spender"])}, tag])
        allowances.append({"label": item["label"], "token": item["token"],
                           "spender": item["spender"],
                           "value": str(uint256(result, f"allowance {item['label']}"))})
    return {"block": block, "native_balance": str(native), "nonce": str(nonce),
            "code": {"bytes": len(code_bytes), "sha256": hashlib.sha256(code_bytes).hexdigest()},
            "tokens": tokens, "allowances": allowances}


def _value_changes(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> list[dict[str, str]]:
    before_by_label = {item["label"]: item for item in before}
    changes = []
    for item in after:
        old = before_by_label[item["label"]]
        a, b = int(old["value"]), int(item["value"])
        changes.append({"label": item["label"], "before": str(a), "after": str(b), "delta": str(b - a)})
    return changes


def build_changes(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Build overflow-safe decimal-string deltas."""
    native_a, native_b = int(before["native_balance"]), int(after["native_balance"])
    nonce_a, nonce_b = int(before["nonce"]), int(after["nonce"])
    return {
        "native_balance": {"before": str(native_a), "after": str(native_b), "delta": str(native_b - native_a)},
        "nonce": {"before": str(nonce_a), "after": str(nonce_b), "delta": str(nonce_b - nonce_a)},
        "code": {"changed": before["code"] != after["code"], "before": before["code"], "after": after["code"]},
        "tokens": _value_changes(before["tokens"], after["tokens"]),
        "allowances": _value_changes(before["allowances"], after["allowances"]),
    }


def capture(rpc: Any, raw_spec: Any) -> dict[str, Any]:
    """Capture two explicit blocks and reject evidence that changes mid-read."""
    spec = validate_spec(raw_spec)
    chain_id = quantity(rpc.call("eth_chainId", []), "eth_chainId")
    first_headers = [_header(rpc, spec["from_block"]), _header(rpc, spec["to_block"])]
    before = _snapshot(rpc, spec, first_headers[0])
    after = _snapshot(rpc, spec, first_headers[1])
    final_headers = [_header(rpc, spec["from_block"]), _header(rpc, spec["to_block"])]
    if first_headers != final_headers:
        raise WalletDiffError("block hash changed during capture; no report was written")
    return {"schema_version": 1, "chain_id": chain_id, "wallet": spec["wallet"],
            "from": before, "to": after, "changes": build_changes(before, after)}
