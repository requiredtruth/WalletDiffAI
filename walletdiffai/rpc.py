"""Bounded standard-library Ethereum JSON-RPC client."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .core import WalletDiffError

ALLOWED_METHODS = frozenset({"eth_chainId", "eth_getBlockByNumber", "eth_getBalance",
                             "eth_getTransactionCount", "eth_getCode", "eth_call"})


class RpcClient:
    """Issue only the read methods required by WalletDiffAI."""

    def __init__(self, url: str, timeout: float = 20.0, max_response: int = 2_000_000):
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            raise WalletDiffError("RPC URL must use http or https")
        self._url = url
        self._timeout = timeout
        self._max_response = max_response
        self._request_id = 0

    def call(self, method: str, params: list[Any]) -> Any:
        if method not in ALLOWED_METHODS:
            raise WalletDiffError(f"RPC method is not allowed: {method}")
        self._request_id += 1
        payload = json.dumps({"jsonrpc": "2.0", "id": self._request_id, "method": method,
                              "params": params}, separators=(",", ":")).encode()
        request = urllib.request.Request(self._url, data=payload,
                                         headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                body = response.read(self._max_response + 1)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise WalletDiffError(f"JSON-RPC request failed for {method}: {exc}") from exc
        if len(body) > self._max_response:
            raise WalletDiffError("JSON-RPC response exceeded the size limit")
        try:
            decoded = json.loads(body)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise WalletDiffError("JSON-RPC returned invalid JSON") from exc
        if not isinstance(decoded, dict) or decoded.get("id") != self._request_id:
            raise WalletDiffError("JSON-RPC response id did not match the request")
        if "error" in decoded:
            error = decoded["error"]
            code = error.get("code") if isinstance(error, dict) else "unknown"
            raise WalletDiffError(f"JSON-RPC {method} failed with code {code}")
        if "result" not in decoded:
            raise WalletDiffError("JSON-RPC response omitted result")
        return decoded["result"]
