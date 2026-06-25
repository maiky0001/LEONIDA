"""
Moteur économique de Leonida.

Gère les 3 sources de revenu (légal/illégal/passif), la production de
ressources, et les "sinks" qui retirent du cash de l'économie pour éviter
l'inflation. Pur calcul, aucune dépendance externe.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from .models import District, Gang, ResourceType


# Coûts d'amélioration de base : index = niveau cible (1→2 coûte UPGRADE_COSTS[2])
UPGRADE_COSTS = [0, 0, 5_000, 12_000, 25_000, 45_000,
                 75_000, 120_000, 180_000, 270_000, 400_000]
MAX_BASE_LEVEL = 10

# Le niveau de base multiplie légèrement les revenus de territoire
def base_income_multiplier(base_level: int) -> float:
    return 1.0 + 0.05 * (base_level - 1)   # +5% par niveau


@dataclass
class TickResult:
    """Résultat d'un cycle économique pour un gang."""
    gang_id: str
    cash_gained: int
    resources_gained: dict[str, int]


class Economy:
    """
    Applique les cycles économiques. Un 'tick' représente le passage du temps :
    chaque district contrôlé verse son revenu et sa production au prorata.
    """

    def __init__(self, districts: dict[str, District], gangs: dict[str, Gang]):
        self.districts = districts
        self.gangs = gangs

    # -- Revenus passifs + production -------------------------------------

    def tick(self, elapsed_seconds: float, now: float | None = None) -> list[TickResult]:
        """
        Verse les revenus pour `elapsed_seconds` écoulées.
        À appeler périodiquement (ex: toutes les 5 min via une task discord.py).
        """
        now = now if now is not None else time.time()
        hours = elapsed_seconds / 3600.0
        results: dict[str, TickResult] = {}

        for district in self.districts.values():
            gid = district.owner_gang_id
            if gid is None or gid not in self.gangs:
                continue

            gang = self.gangs[gid]
            mult = base_income_multiplier(gang.base_level)

            cash = int(district.base_income * hours * mult)
            prod = int(district.production_rate * hours)

            gang.treasury += cash
            gang.add_resource(district.production, prod)

            res = results.setdefault(gid, TickResult(gid, 0, {}))
            res.cash_gained += cash
            res.resources_gained[district.production.value] = (
                res.resources_gained.get(district.production.value, 0) + prod
            )

        return list(results.values())

    # -- Sinks : retirer du cash de l'économie ----------------------------

    def upgrade_base(self, gang_id: str) -> tuple[bool, str]:
        gang = self.gangs.get(gang_id)
        if gang is None:
            return False, "Gang introuvable."
        if gang.base_level >= MAX_BASE_LEVEL:
            return False, "Base déjà au niveau maximum (mini-empire)."

        target = gang.base_level + 1
        cost = UPGRADE_COSTS[target]
        if gang.treasury < cost:
            return False, f"Trésorerie insuffisante : {cost:,}$ requis, {gang.treasury:,}$ dispo."

        gang.treasury -= cost
        gang.base_level = target
        return True, f"Base améliorée au niveau {target}. (-{cost:,}$)"

    def sell_resource(self, gang_id: str, rtype: ResourceType,
                      qty: int, unit_price: int) -> tuple[bool, str]:
        """Conversion ressource → cash légal (jobs) ou illégal (trafic)."""
        gang = self.gangs.get(gang_id)
        if gang is None:
            return False, "Gang introuvable."
        if gang.resource_qty(rtype) < qty:
            return False, f"Stock insuffisant : {gang.resource_qty(rtype)} {rtype.value} dispo."

        gang.resources[rtype.value] -= qty
        gain = qty * unit_price
        gang.treasury += gain
        return True, f"Vendu {qty} {rtype.value} pour {gain:,}$."

    # -- Indicateurs ------------------------------------------------------

    def total_income_per_hour(self, gang_id: str) -> int:
        gang = self.gangs.get(gang_id)
        if gang is None:
            return 0
        mult = base_income_multiplier(gang.base_level)
        return int(sum(
            d.base_income for d in self.districts.values()
            if d.owner_gang_id == gang_id
        ) * mult)
