"""Command-line interface."""

from __future__ import annotations

import argparse
import json
import os
import sys
from importlib.resources import files

from .capture import capture
from .core import WalletDiffError, atomic_json, canonical_bytes, load_json
from .explain import explain_local, prompt
from .report import summary, verify
from .rpc import RpcClient


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="walletdiffai", description="Diff wallet exposure at two exact EVM blocks")
    sub = result.add_subparsers(dest="command", required=True)
    cap = sub.add_parser("capture", help="capture and diff exact blocks through read-only JSON-RPC")
    cap.add_argument("spec")
    cap.add_argument("output")
    cap.add_argument("--rpc-url", default=os.environ.get("WALLETDIFF_RPC_URL"))
    check = sub.add_parser("verify", help="validate evidence and recompute derived changes")
    check.add_argument("report")
    show = sub.add_parser("summary", help="print a deterministic text summary")
    show.add_argument("report")
    make_prompt = sub.add_parser("prompt", help="emit an address-redacted local-model prompt")
    make_prompt.add_argument("report")
    make_prompt.add_argument("output", nargs="?", default="-")
    explain = sub.add_parser("explain", help="ask a loopback OpenAI-compatible server for untrusted commentary")
    explain.add_argument("report")
    explain.add_argument("--api-url", required=True)
    explain.add_argument("--model", required=True)
    sub.add_parser("demo", help="run the bundled deterministic offline report")
    return result


def _emit(value: object, destination: str = "-") -> None:
    if destination == "-":
        sys.stdout.buffer.write(canonical_bytes(value))
    else:
        atomic_json(destination, value)


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "capture":
            if not args.rpc_url:
                raise WalletDiffError("provide --rpc-url or WALLETDIFF_RPC_URL")
            result = capture(RpcClient(args.rpc_url), load_json(args.spec))
            atomic_json(args.output, result)
            print(f"wrote verified report: {args.output}")
        elif args.command == "verify":
            verify(load_json(args.report))
            print("report verified")
        elif args.command == "summary":
            sys.stdout.write(summary(load_json(args.report)))
        elif args.command == "prompt":
            _emit(prompt(load_json(args.report)), args.output)
        elif args.command == "explain":
            _emit(explain_local(load_json(args.report), args.api_url, args.model))
        elif args.command == "demo":
            report = json.loads(files("walletdiffai.data").joinpath("demo_report.json").read_text())
            sys.stdout.write(summary(report))
        return 0
    except (WalletDiffError, OSError) as exc:
        print(f"walletdiffai: {exc}", file=sys.stderr)
        return 2
