import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))


@pytest.fixture(autouse=True)
def _sem_mapa_de_fundo(monkeypatch):
    """Os testes não baixam tiles do OpenStreetMap; o teste do mapa de fundo liga de propósito, com tiles falsos."""
    monkeypatch.setenv("SISEGC_MAPA_DE_FUNDO", "0")
