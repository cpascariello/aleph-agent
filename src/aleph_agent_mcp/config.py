"""Configuration via environment variables and optional JSON file."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All ALEPH_AGENT_* env vars are read automatically."""

    model_config = {"env_prefix": "ALEPH_AGENT_"}

    # Account
    human_address: str | None = None
    private_key_path: Path = Path("~/.aleph-im/private-keys/ethereum.key")
    ssh_pubkey_path: Path = Path("~/.ssh/id_ed25519.pub")

    # Inventory
    inventory_path: Path = Path("~/.aleph-agent-inventory.json")

    # Safety defaults
    max_concurrent_vms: int = 3
    default_ttl_hours: float = 4.0
    max_ttl_hours: float = 24.0
    balance_guard_percent: float = 20.0
    cost_threshold: float = 10.0
    max_session_spend: float | None = None

    # OS image default
    default_os_image: str = "ubuntu22"

    def resolve_paths(self) -> None:
        """Expand ~ in all Path fields."""
        self.private_key_path = self.private_key_path.expanduser()
        self.ssh_pubkey_path = self.ssh_pubkey_path.expanduser()
        self.inventory_path = self.inventory_path.expanduser()


# Singleton — importable everywhere
settings = Settings()
settings.resolve_paths()
