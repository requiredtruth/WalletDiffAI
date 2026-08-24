"""Report validation and deterministic presentation."""

from __future__ import annotations

import re
from typing import Any

from .core import WalletDiffError, address, block_hash, quantity


def verify(report: Any) -> dict[str, Any]:
    """Validate core evidence and recompute every derived change."""
    from .capture import build_changes
    if not isinstance(report, dict) or report.get("schema_version") != 1:
        raise WalletDiffError("report schema_version must be 1")
    required = {"schema_version", "chain_id", "wallet", "from", "to", "changes"}
    if set(report) != required:
        raise WalletDiffError("report fields do not match schema version 1")
    address(report["wallet"], "wallet")
    quantity(report["chain_id"], "chain_id")
    for side in ("from", "to"):
        snap = report.get(side)
        if not isinstance(snap, dict):
            raise WalletDiffError(f"{side} snapshot must be an object")
        header = snap.get("block")
        if not isinstance(header, dict):
            raise WalletDiffError(f"{side}.block must be an object")
        quantity(header.get("number"), f"{side}.block.number")
        block_hash(header.get("hash"), f"{side}.block.hash")
        for name in ("native_balance", "nonce"):
            if not isinstance(snap.get(name), str) or not snap[name].isdigit():
                raise WalletDiffError(f"{side}.{name} must be a decimal string")
        code = snap.get("code")
        if not isinstance(code, dict) or not isinstance(code.get("bytes"), int) or code["bytes"] < 0:
            raise WalletDiffError(f"{side}.code is invalid")
        if not isinstance(code.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", code["sha256"]):
            raise WalletDiffError(f"{side}.code.sha256 is invalid")
        for collection in ("tokens", "allowances"):
            if not isinstance(snap.get(collection), list):
                raise WalletDiffError(f"{side}.{collection} must be a list")
            labels: set[str] = set()
            for item in snap[collection]:
                required_item = {"label", "value", "contract"} if collection == "tokens" else {"label", "value", "token", "spender"}
                if not isinstance(item, dict) or set(item) != required_item:
                    raise WalletDiffError(f"{side}.{collection} contains invalid fields")
                if not isinstance(item.get("label"), str) or item["label"] in labels:
                    raise WalletDiffError(f"{side}.{collection} contains an invalid or duplicate label")
                labels.add(item["label"])
                if not isinstance(item.get("value"), str) or not item["value"].isdigit():
                    raise WalletDiffError(f"{side}.{collection} contains an invalid value")
                if collection == "tokens":
                    address(item["contract"], f"{side}.{collection}.contract")
                else:
                    address(item["token"], f"{side}.{collection}.token")
                    address(item["spender"], f"{side}.{collection}.spender")
    if int(report["from"]["block"]["number"], 16) >= int(report["to"]["block"]["number"], 16):
        raise WalletDiffError("report block order is invalid")
    for collection in ("tokens", "allowances"):
        before_ids = [(item["label"], item.get("contract", item.get("token")), item.get("spender"))
                      for item in report["from"][collection]]
        after_ids = [(item["label"], item.get("contract", item.get("token")), item.get("spender"))
                     for item in report["to"][collection]]
        if before_ids != after_ids:
            raise WalletDiffError(f"{collection} identities differ between snapshots")
    expected = build_changes(report["from"], report["to"])
    if report["changes"] != expected:
        raise WalletDiffError("derived changes do not match snapshots")
    return report


def summary(report: Any) -> str:
    report = verify(report)
    changes = report["changes"]
    rows = [
        "WalletDiffAI deterministic summary",
        f"chain={report['chain_id']} blocks={report['from']['block']['number']}..{report['to']['block']['number']}",
        f"native delta={changes['native_balance']['delta']}",
        f"nonce delta={changes['nonce']['delta']}",
        f"code changed={'yes' if changes['code']['changed'] else 'no'}",
    ]
    rows.extend(f"token {item['label']} delta={item['delta']}" for item in changes["tokens"])
    rows.extend(f"allowance {item['label']} delta={item['delta']}" for item in changes["allowances"])
    return "\n".join(rows) + "\n"
