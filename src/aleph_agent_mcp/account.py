"""Account loading and delegated mode resolution."""

from __future__ import annotations

from pathlib import Path

from aleph.sdk.account import _load_account


def load_account(private_key_path: Path):
    """Load an Aleph account from a private key file.

    Returns an ETHAccount instance.
    """
    return _load_account(private_key_path=private_key_path)


def resolve_sender_address(account, human_address: str | None) -> str:
    """Return the address used for queries.

    For delegated mode, instances are listed under the *signer* (agent),
    not the payer (human).
    """
    return account.get_address()


def resolve_payer_address(human_address: str | None) -> str | None:
    """Return the address passed as `address=` to create_instance for delegation.

    None means the agent pays directly from its own balance.
    """
    return human_address
