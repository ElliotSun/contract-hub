"""Contract content helpers for the Streamlit UI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ContractService:
    """Load local sample contract content for the Streamlit UI."""

    repository_root: Path = Path(__file__).resolve().parents[4]

    def load_sample_contract_yaml(self) -> str:
        """Return the repository sample ODCS YAML."""
        sample_path = self.repository_root / "sample_odcs.yaml"
        return sample_path.read_text(encoding="utf-8")


def load_sample_contract_yaml() -> str:
    """Convenience wrapper for loading the repository sample ODCS YAML."""
    return ContractService().load_sample_contract_yaml()
