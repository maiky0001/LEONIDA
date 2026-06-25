"""
État global du jeu Leonida + persistance JSON.

GameState agrège districts + gangs et expose les sous-systèmes
(Economy, Territory). Sauvegarde/chargement sur disque pour survivre
aux redémarrages du bot.
"""

from __future__ import annotations

import json
import os
import time
from typing import Optional

from .models import (
    District, Gang, DistrictType, ResourceType,
    district_to_dict, district_from_dict, gang_to_dict, gang_from_dict,
)
from .economy import Economy
from .territory import Territory


class GameState:
    def __init__(self, save_path: str = "leonida_save.json"):
        self.save_path = save_path
        self.districts: dict[str, District] = {}
        self.gangs: dict[str, Gang] = {}
        self.last_tick: float = time.time()

    # -- Sous-systèmes (recréés à la volée pour rester sans état) ---------

    @property
    def economy(self) -> Economy:
        return Economy(self.districts, self.gangs)

    @property
    def territory(self) -> Territory:
        return Territory(self.districts, self.gangs)

    # -- Gangs ------------------------------------------------------------

    def create_gang(self, gang_id: str, name: str, leader_id: str,
                    color: str = "#FF2D95") -> tuple[bool, str]:
        if gang_id in self.gangs:
            return False, "Ce gang existe déjà."
        if any(g.name.lower() == name.lower() for g in self.gangs.values()):
            return False, "Un gang porte déjà ce nom."
        self.gangs[gang_id] = Gang(
            id=gang_id, name=name, leader_id=leader_id,
            color=color, member_ids=[leader_id],
        )
        return True, f"🏴 Gang « {name} » fondé."

    def join_gang(self, gang_id: str, member_id: str) -> tuple[bool, str]:
        gang = self.gangs.get(gang_id)
        if gang is None:
            return False, "Gang introuvable."
        if member_id in gang.member_ids:
            return False, "Tu es déjà membre."
        # Un joueur ne peut être que dans un gang
        for g in self.gangs.values():
            if member_id in g.member_ids:
                return False, f"Tu es déjà dans « {g.name} ». Quitte-le d'abord."
        gang.member_ids.append(member_id)
        return True, f"Bienvenue chez {gang.name}."

    def gang_of(self, member_id: str) -> Optional[Gang]:
        for g in self.gangs.values():
            if member_id in g.member_ids:
                return g
        return None

    # -- Districts --------------------------------------------------------

    def add_district(self, district: District) -> None:
        self.districts[district.id] = district

    # -- Tick périodique --------------------------------------------------

    def run_tick(self, now: float | None = None):
        now = now if now is not None else time.time()
        elapsed = now - self.last_tick
        self.last_tick = now
        return self.economy.tick(elapsed, now)

    # -- Persistance ------------------------------------------------------

    def save(self) -> None:
        data = {
            "last_tick": self.last_tick,
            "districts": {k: district_to_dict(v) for k, v in self.districts.items()},
            "gangs": {k: gang_to_dict(v) for k, v in self.gangs.items()},
        }
        tmp = self.save_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.save_path)   # écriture atomique

    def load(self) -> bool:
        if not os.path.exists(self.save_path):
            return False
        with open(self.save_path, encoding="utf-8") as f:
            data = json.load(f)
        self.last_tick = data.get("last_tick", time.time())
        self.districts = {k: district_from_dict(v)
                          for k, v in data.get("districts", {}).items()}
        self.gangs = {k: gang_from_dict(v)
                      for k, v in data.get("gangs", {}).items()}
        return True


# ---------------------------------------------------------------------------
# Map de départ : les districts de Leonida (seed)
# ---------------------------------------------------------------------------

def seed_default_map(state: GameState) -> None:
    """Crée la map de base de Leonida si elle est vide."""
    if state.districts:
        return

    defaults = [
        District("vice_beach", "Vice Beach", DistrictType.URBAIN,
                 base_income=1200, production=ResourceType.CASH,
                 production_rate=0, police_level=8, capture_minutes=20),
        District("downtown", "Downtown Leonida", DistrictType.URBAIN,
                 base_income=1500, production=ResourceType.CASH,
                 production_rate=0, police_level=9, capture_minutes=25),
        District("dock_77", "Docks 77", DistrictType.PORT,
                 base_income=900, production=ResourceType.ARMES,
                 production_rate=8, police_level=6, capture_minutes=15),
        District("steel_row", "Steel Row", DistrictType.INDUSTRIEL,
                 base_income=700, production=ResourceType.ARMES,
                 production_rate=12, police_level=5, capture_minutes=15),
        District("the_glades", "The Glades", DistrictType.MARECAGE,
                 base_income=500, production=ResourceType.DROGUE,
                 production_rate=20, police_level=2, capture_minutes=10),
        District("palm_hills", "Palm Hills", DistrictType.BANLIEUE,
                 base_income=1400, production=ResourceType.CASH,
                 production_rate=0, police_level=7, capture_minutes=20),
        District("backcountry", "Backcountry", DistrictType.RURAL,
                 base_income=400, production=ResourceType.DROGUE,
                 production_rate=10, police_level=1, capture_minutes=8),
    ]
    for d in defaults:
        state.add_district(d)
