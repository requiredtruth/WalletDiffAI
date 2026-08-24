"""Minimal fixed ABI encoders for read-only ERC-20 queries."""

from .core import address

BALANCE_OF = "70a08231"
ALLOWANCE = "dd62ed3e"


def _word(value: str, field: str) -> str:
    return address(value, field)[2:].rjust(64, "0")


def balance_of(owner: str) -> str:
    return "0x" + BALANCE_OF + _word(owner, "owner")


def allowance(owner: str, spender: str) -> str:
    return "0x" + ALLOWANCE + _word(owner, "owner") + _word(spender, "spender")
