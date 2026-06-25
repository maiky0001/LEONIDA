"""
Système de territoires de Leonida.

Gère la capture de districts, les raids (surprise / économique) et le
classement par contrôle de map. La logique de "guerre permanente" vit ici.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass

from .models import District, Gang, ResourceType


# Cooldown anti-spam de raids (secondes) par gang attaquant
RAID_COOLDOWN = 30 * 60          # 30 min
# Coût d'entrée d'un raid (sink économique)
RAID_ENTRY_COST = 2_000


@dataclass
class CaptureResult:
    success: bool
    message: str
    district_id: str | None = None


@dataclass
class RaidResult:
    success: bool
    message: str
    attacker_id: str
    defender_id: str | None = None
    loot_cash: int = 0
    loot_resources: dict[str, int] | None = None


class Territory:
    """
    Couche territoires. Détient l'état des cooldowns de raid et arbitre
    les captures/raids selon le niveau de base et de police.
    """

    def __init__(self, districts: dict[str, District], gangs: dict[str, Gang]):
        self.districts = districts
        self.gangs = gangs
        self._last_raid: dict[str, float] = {}   # gang_id -> timestamp

    # -- Capture d'un quartier libre --------------------------------------

    def capture(self, gang_id: str, district_id: str,
                now: float | None = None) -> CaptureResult:
        now = now if now is not None else time.time()
        district = self.districts.get(district_id)
        gang = self.gangs.get(gang_id)

        if district is None:
            return CaptureResult(False, "District introuvable.")
        if gang is None:
            return CaptureResult(False, "Gang introuvable.")
        if not district.is_contested():
            return CaptureResult(False,
                f"{district.name} est déjà contrôlé. Lance un raid pour le prendre.")

        # La police complique la prise : il faut assez de membres présents.
        members_required = max(1, district.police_level // 2)
        if gang.member_count < members_required:
            return CaptureResult(False,
                f"Police niveau {district.police_level} : il faut au moins "
                f"{members_required} membres pour capturer {district.name}.")

        district.owner_gang_id = gang_id
        district.captured_at = now
        return CaptureResult(True,
            f"🏴 {gang.name} a capturé {district.name} !", district_id)

    # -- Raid : prendre un district à un autre gang -----------------------

    def raid(self, attacker_id: str, district_id: str,
             now: float | None = None) -> RaidResult:
        now = now if now is not None else time.time()
        attacker = self.gangs.get(attacker_id)
        district = self.districts.get(district_id)

        if attacker is None:
            return RaidResult(False, "Gang attaquant introuvable.", attacker_id)
        if district is None:
            return RaidResult(False, "District introuvable.", attacker_id)
        if district.owner_gang_id is None:
            return RaidResult(False,
                "District libre : utilise capture, pas raid.", attacker_id)
        if district.owner_gang_id == attacker_id:
            return RaidResult(False, "Tu contrôles déjà ce district.", attacker_id)

        # Cooldown
        last = self._last_raid.get(attacker_id, 0)
        if now - last < RAID_COOLDOWN:
            remaining = int((RAID_COOLDOWN - (now - last)) / 60)
            return RaidResult(False,
                f"Raid en cooldown : encore {remaining} min.", attacker_id)

        # Coût d'entrée (sink)
        if attacker.treasury < RAID_ENTRY_COST:
            return RaidResult(False,
                f"Coût d'entrée du raid : {RAID_ENTRY_COST:,}$ requis.", attacker_id)

        defender = self.gangs.get(district.owner_gang_id)
        attacker.treasury -= RAID_ENTRY_COST
        self._last_raid[attacker_id] = now

        # Résolution : force = membres + bonus base + aléa, le défenseur a
        # un avantage de terrain proportionnel à son niveau de base.
        atk_power = attacker.member_count + attacker.base_level + random.uniform(0, 5)
        def_power = (defender.member_count + defender.base_level * 1.5
                     + district.police_level * 0.5 + random.uniform(0, 5))

        if atk_power <= def_power:
            return RaidResult(False,
                f"⚔️ Raid repoussé ! {defender.name} a défendu {district.name}.",
                attacker_id, defender.id)

        # Victoire : transfert du district + butin partiel sur le défenseur
        loot_cash = int(defender.treasury * 0.15)
        defender.treasury -= loot_cash
        attacker.treasury += loot_cash

        loot_res: dict[str, int] = {}
        for rtype in ResourceType:
            stolen = int(defender.resource_qty(rtype) * 0.20)
            if stolen > 0:
                defender.resources[rtype.value] -= stolen
                attacker.add_resource(rtype, stolen)
                loot_res[rtype.value] = stolen

        district.owner_gang_id = attacker_id
        district.captured_at = now

        return RaidResult(True,
            f"💥 {attacker.name} a pris {district.name} à {defender.name} ! "
            f"Butin : {loot_cash:,}$.",
            attacker_id, defender.id, loot_cash, loot_res)

    # -- Classement par contrôle de map -----------------------------------

    def map_control(self) -> dict[str, float]:
        """Retourne {gang_id: % de la map contrôlée}."""
        total = len(self.districts)
        if total == 0:
            return {}
        counts: dict[str, int] = {}
        for d in self.districts.values():
            if d.owner_gang_id:
                counts[d.owner_gang_id] = counts.get(d.owner_gang_id, 0) + 1
        return {gid: round(100 * n / total, 1) for gid, n in counts.items()}

    def leaderboard(self) -> list[tuple[str, float]]:
        """Gangs triés par contrôle de map décroissant."""
        control = self.map_control()
        return sorted(control.items(), key=lambda kv: kv[1], reverse=True)

    def empire_leader(self, threshold: float = 60.0) -> str | None:
        """Endgame : un gang contrôle >= threshold% de la map."""
        for gid, pct in self.map_control().items():
            if pct >= threshold:
                return gid
        return None
