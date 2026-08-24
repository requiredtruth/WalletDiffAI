"""Address-redacted prompts and optional loopback-only model commentary."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .core import WalletDiffError, sha256
from .report import verify

SYSTEM = ("Explain only the supplied deterministic wallet-diff facts. Do not infer identities, "
          "malice, returns, intent, token prices, or trading advice. State that values are raw units.")


def prompt(report: Any) -> dict[str, Any]:
    """Create messages containing labels and facts but no on-chain addresses."""
    report = verify(report)
    changes = report["changes"]
    facts = {"chain_id": report["chain_id"],
             "from_block": report["from"]["block"]["number"],
             "to_block": report["to"]["block"]["number"],
             "native_balance": changes["native_balance"], "nonce": changes["nonce"],
             "code_changed": changes["code"]["changed"], "tokens": changes["tokens"],
             "allowances": changes["allowances"]}
    return {"facts_sha256": sha256(facts), "messages": [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": json.dumps(facts, sort_keys=True, separators=(",", ":"))},
    ]}


def explain_local(report: Any, api_url: str, model: str, timeout: float = 60.0) -> dict[str, str]:
    """Request untrusted commentary from a loopback OpenAI-compatible server."""
    parsed = urllib.parse.urlparse(api_url)
    if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise WalletDiffError("model API must be an http loopback URL")
    if parsed.username or parsed.password or not parsed.port or parsed.query or parsed.fragment:
        raise WalletDiffError("model API URL must be a plain loopback origin")
    material = prompt(report)
    endpoint = api_url.rstrip("/") + "/v1/chat/completions"
    payload = json.dumps({"model": model, "messages": material["messages"], "temperature": 0,
                          "max_tokens": 512}).encode()
    request = urllib.request.Request(endpoint, data=payload,
                                     headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(256_001)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise WalletDiffError(f"local model request failed: {exc}") from exc
    if len(body) > 256_000:
        raise WalletDiffError("local model response exceeded the size limit")
    try:
        decoded = json.loads(body)
        text = decoded["choices"][0]["message"]["content"]
    except (UnicodeError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
        raise WalletDiffError("local model returned an invalid chat-completions response") from exc
    if not isinstance(text, str) or not text.strip() or len(text) > 16_000:
        raise WalletDiffError("local model commentary is empty or too large")
    return {"facts_sha256": material["facts_sha256"], "trust": "untrusted_model_commentary",
            "commentary": text.strip()}
