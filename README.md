# WalletDiffAI

Deterministic, read-only EVM wallet exposure diffs between two exact block numbers. It answers searches such as **"historical ERC-20 allowance diff Python"**, **"compare wallet balance at two blocks"**, and **"eth_call historical state missing trie node"** without connecting a wallet or outsourcing the evidence to an indexer.

```console
$ ./install.sh
...
WalletDiffAI deterministic summary
chain=0x1 blocks=0x10..0x20
native delta=-25
nonce delta=2
code changed=no
token TOKEN_A delta=40
allowance TOKEN_A_TO_SPENDER_1 delta=-100
```

The command above is offline, deterministic, and has no runtime dependencies outside Python 3.10+. It compiles the package, runs every test, and verifies the bundled report.

## What is different

Broad ETL libraries such as [CheckTheChain](https://github.com/checkthechain/checkthechain) collect and analyze historical EVM data. Portfolio trackers and transaction-history tools commonly depend on hosted indexers. WalletDiffAI instead performs one narrow audit primitive directly against a user-selected JSON-RPC endpoint:

- compare a declared wallet at two explicit block numbers;
- record the block number and hash supporting each side;
- re-read both headers after capture and abort if either hash changed;
- query native balance, nonce, code fingerprint, declared ERC-20 balances, and declared allowances;
- recompute derived deltas during `verify`;
- optionally send only address-redacted facts to a local OpenAI-compatible server.

It does not discover tokens, value assets, infer owners, label behavior as malicious, or recommend trades. That is a smaller feature set than an indexer and a stronger provenance boundary for reproducible point-in-time comparisons.

## Capture a real diff

Create `spec.json`:

```json
{
  "schema_version": 1,
  "wallet": "0x0000000000000000000000000000000000000001",
  "from_block": "0x10",
  "to_block": "0x20",
  "tokens": [
    {"contract": "0x0000000000000000000000000000000000000002", "label": "TOKEN_A"}
  ],
  "allowances": [
    {
      "token": "0x0000000000000000000000000000000000000002",
      "spender": "0x0000000000000000000000000000000000000003",
      "label": "TOKEN_A_TO_SPENDER_1"
    }
  ]
}
```

Then run:

```bash
./run.sh capture spec.json report.json --rpc-url http://127.0.0.1:8545
./run.sh verify report.json
./run.sh summary report.json
```

The RPC client permits only `eth_chainId`, `eth_getBlockByNumber`, `eth_getBalance`, `eth_getTransactionCount`, `eth_getCode`, and `eth_call`. It has no transaction-submission method. See Ethereum's official [JSON-RPC API](https://ethereum.org/en/developers/apis/json-rpc/) and [EIP-1898 block identifiers](https://eips.ethereum.org/EIPS/eip-1898).

An archival RPC may be necessary. Errors such as `missing trie node`, `header not found`, `historical state unavailable`, or JSON-RPC error `-32000` mean the selected node cannot serve the requested historical state; WalletDiffAI fails closed and writes no partial report.

## Optional local model commentary

Generate the exact redacted prompt without running a model:

```bash
./run.sh prompt report.json prompt.json
```

Or use a server bound to loopback:

```bash
./run.sh explain report.json --api-url http://127.0.0.1:8080 --model local-model
```

Non-loopback model URLs are rejected. Raw wallet, token, and spender addresses are not placed in the prompt. Model text is labeled `untrusted_model_commentary`; the report remains the authority.

## Safety and limitations

- Read-only and non-custodial: no private keys, seed phrases, wallet connection, signing, approvals, transaction submission, trading, or custody.
- Labels and contract addresses are supplied by the user; there is no token discovery or contract identity claim.
- ERC-20 values are raw integer units. Metadata, decimals, prices, rebasing semantics, proxies, and nonstandard token behavior are not interpreted.
- A stable header check narrows reorganization risk during capture but does not prove finality or RPC honesty.
- Reports prove what the selected RPC returned, not legal ownership or intent.
- Optional model commentary is untrusted and is not financial, legal, or security advice.

## Support and funded direction

If this saves investigation time, [support continued production](SUPPORT.md). A confirmed public transaction hash may accompany a feature-direction issue; the first valid issue receives operational attribution for that transaction. It does not prove wallet ownership or buy ownership, returns, deadlines, priority, support, or prohibited work.

## License

Apache-2.0. See [LICENSE](LICENSE).


## Standard launcher

`./run.sh` is the normal entry point. It runs `./install.sh` automatically when setup is missing, then opens the PySide6 control panel with live output and actions for the demo, tests, repair, and stop. Use `./cli.sh` for CLI-only operation.
