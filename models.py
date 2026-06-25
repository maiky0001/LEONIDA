"""
Modèles de données du moteur Leonida.

Aucune dépendance à Discord ou au jeu : pur Python.
C'est la couche que tu rebrancheras sur GTA 6 le jour venu.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DistrictType(str, Enum):
    URBAIN = "urbain"          # Vice City — gros revenu, grosse police
    INDUSTRIEL = "industriel"  # production d'armes
    PORT = "port"              # import/export, trafic
    MARECAGE = "marecage"      # drogue, police faible
    BANLIEUE = "banlieue"      # revenu passif élevé
    RURAL = "rural"            # facile à tenir, peu rentable


class ResourceType(str, Enum):
    CASH = "cash"
    DROGUE = "drogue"
    ARMES = "armes"


# ---------------------------------------------------------------------------
# District
# ---------------------------------------------------------------------------

@dataclass
class District:
    """Un quartier contrôlable de Leonida."""
    id: str
    name: str
    dtype: DistrictType
    base_income: int          # cash/heure généré quand contrôlé
    production: ResourceType   # ressource produite
    production_rate: int       # unités/heure
    police_level: int          # 1 (faible) à 10 (forte) — difficulté de contrôle
    capture_minutes: int       # durée de capture nécessaire pour prendre le quartier

    # État dynamique
    owner_gang_id: Optional[str] = None
    captured_at: Optional[float] = None  # timestamp epoch de la prise

    def held_seconds(self, now: Optional[float] = None) -> float:
        if self.owner_gang_id is None or self.captured_at is None:
            return 0.0
        now = now if now is not None else time.time()
        return max(0.0, now - self.captured_at)

    def is_contested(self) -> bool:
        return self.owner_gang_id is None


# ---------------------------------------------------------------------------
# Gang
# ---------------------------------------------------------------------------

@dataclass
class Gang:
    """Un gang : faction joueur qui contrôle des districts."""
    id: str
    name: str
    leader_id: str                       # ID Discord du leader
    color: str = "#FF2D95"               # branding néon
    member_ids: list[str] = field(default_factory=list)
    treasury: int = 0                    # cash en banque
    resources: dict[str, int] = field(default_factory=dict)  # ResourceType -> qté
    base_level: int = 1                  # 1 squat → 10 mini-empire
    created_at: float = field(default_factory=time.time)

    def add_resource(self, rtype: ResourceType, qty: int) -> None:
        self.resources[rtype.value] = self.resources.get(rtype.value, 0) + qty

    def resource_qty(self, rtype: ResourceType) -> int:
        return self.resources.get(rtype.value, 0)

    @property
    def member_count(self) -> int:
        return len(self.member_ids)


# ---------------------------------------------------------------------------
# Sérialisation (pour la persistance JSON)
# ---------------------------------------------------------------------------

def district_to_dict(d: District) -> dict:
    raw = asdict(d)
    raw["dtype"] = d.dtype.value
    raw["production"] = d.production.value
    return raw


def district_from_dict(raw: dict) -> District:
    raw = dict(raw)
    raw["dtype"] = DistrictType(raw["dtype"])
    raw["production"] = ResourceType(raw["production"])
    return District(**raw)


def gang_to_dict(g: Gang) -> dict:
    return asdict(g)


def gang_from_dict(raw: dict) -> Gang:
    return Gang(**raw)
