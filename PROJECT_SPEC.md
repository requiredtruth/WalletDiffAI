# Project specification

## Contract

WalletDiffAI 0.1.0 produces a deterministic JSON report for one declared wallet at two explicit EVM block numbers.

Inputs are schema-versioned JSON, a read-only HTTP(S) JSON-RPC endpoint, and optional output paths. `latest`, `safe`, `finalized`, decimal block numbers, non-minimal quantities, unknown fields, duplicate labels, and duplicate exposures are rejected.

The capture sequence is:

1. read chain ID;
2. read both block headers;
3. capture native balance, nonce, code, declared token balances, and declared allowances at each exact block;
4. read both block headers again;
5. reject changed hashes; otherwise derive decimal-string deltas and atomically write the report.

## Stable interfaces

- `walletdiffai capture SPEC OUTPUT --rpc-url URL`
- `walletdiffai verify REPORT`
- `walletdiffai summary REPORT`
- `walletdiffai prompt REPORT [OUTPUT]`
- `walletdiffai explain REPORT --api-url LOOPBACK_URL --model MODEL`
- `walletdiffai demo`

JSON integers representing on-chain quantities are decimal strings so consumers do not lose precision. Canonical JSON uses sorted keys, compact separators, ASCII output, and a trailing newline.

## Non-goals

Wallet connection, signing, submission, token discovery, pricing, portfolio accounting, profit prediction, behavioral labeling, hosted inference, and trading are outside the project contract.
