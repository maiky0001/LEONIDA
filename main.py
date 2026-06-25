"""
Bot Discord Leonida — interface joueur sur le moteur de jeu.

Slash-commands : créer/rejoindre un gang, capturer/raider des districts,
voir la map, le leaderboard, améliorer sa base. Un tick économique tourne
en tâche de fond et sauvegarde l'état.

Lancement :
    pip install -U "discord.py>=2.3"
    export DISCORD_TOKEN="ton_token"
    python -m leonida.bot.main
"""

from __future__ import annotations

import os
import time

import discord
from discord import app_commands
from discord.ext import tasks

from leonida.core import GameState, seed_default_map, ResourceType


SAVE_PATH = os.environ.get("LEONIDA_SAVE", "leonida_save.json")
TICK_MINUTES = 5          # fréquence du cycle économique
NEON = 0xFF2D95           # couleur des embeds


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class LeonidaBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.state = GameState(save_path=SAVE_PATH)

    async def setup_hook(self):
        if not self.state.load():
            seed_default_map(self.state)
            self.state.save()
        self.economic_tick.start()
        await self.tree.sync()

    @tasks.loop(minutes=TICK_MINUTES)
    async def economic_tick(self):
        self.state.run_tick()
        self.state.save()

    @economic_tick.before_loop
    async def before_tick(self):
        await self.wait_until_ready()


bot = LeonidaBot()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def embed(title: str, desc: str, color: int = NEON) -> discord.Embed:
    e = discord.Embed(title=title, description=desc, color=color)
    e.set_footer(text="LEONIDA: DISTRICT WARS — Survive. Control. Rule the City.")
    return e


def gang_color(hexstr: str) -> int:
    try:
        return int(hexstr.lstrip("#"), 16)
    except ValueError:
        return NEON


# ---------------------------------------------------------------------------
# Commandes — Gangs
# ---------------------------------------------------------------------------

@bot.tree.command(name="gang_create", description="Fonder un nouveau gang")
@app_commands.describe(nom="Nom du gang", couleur="Code hex, ex: #FF2D95")
async def gang_create(interaction: discord.Interaction, nom: str,
                      couleur: str = "#FF2D95"):
    uid = str(interaction.user.id)
    gid = f"g_{uid}"
    ok, msg = bot.state.create_gang(gid, nom, leader_id=uid, color=couleur)
    bot.state.save()
    await interaction.response.send_message(
        embed=embed("Fondation de gang", msg, gang_color(couleur)),
        ephemeral=not ok,
    )


@bot.tree.command(name="gang_join", description="Rejoindre un gang existant")
@app_commands.describe(nom="Nom exact du gang")
async def gang_join(interaction: discord.Interaction, nom: str):
    target = next((g for g in bot.state.gangs.values()
                   if g.name.lower() == nom.lower()), None)
    if target is None:
        await interaction.response.send_message(
            embed=embed("Gang introuvable", f"Aucun gang « {nom} »."),
            ephemeral=True)
        return
    ok, msg = bot.state.join_gang(target.id, str(interaction.user.id))
    bot.state.save()
    await interaction.response.send_message(
        embed=embed("Recrutement", msg, gang_color(target.color)),
        ephemeral=not ok)


@bot.tree.command(name="gang_info", description="Infos sur ton gang")
async def gang_info(interaction: discord.Interaction):
    gang = bot.state.gang_of(str(interaction.user.id))
    if gang is None:
        await interaction.response.send_message(
            embed=embed("Aucun gang", "Tu n'es dans aucun gang. /gang_create ou /gang_join."),
            ephemeral=True)
        return

    income = bot.state.economy.total_income_per_hour(gang.id)
    held = [d.name for d in bot.state.districts.values()
            if d.owner_gang_id == gang.id]
    res = ", ".join(f"{k}: {v}" for k, v in gang.resources.items()) or "aucune"
    desc = (
        f"**Leader :** <@{gang.leader_id}>\n"
        f"**Membres :** {gang.member_count}\n"
        f"**Trésorerie :** {gang.treasury:,}$\n"
        f"**Base :** niveau {gang.base_level}/10\n"
        f"**Revenu :** {income:,}$/h\n"
        f"**Districts :** {', '.join(held) or 'aucun'}\n"
        f"**Ressources :** {res}"
    )
    await interaction.response.send_message(
        embed=embed(f"🏴 {gang.name}", desc, gang_color(gang.color)))


# ---------------------------------------------------------------------------
# Commandes — Territoires
# ---------------------------------------------------------------------------

@bot.tree.command(name="map", description="État de la map de Leonida")
async def show_map(interaction: discord.Interaction):
    lines = []
    for d in bot.state.districts.values():
        if d.owner_gang_id and d.owner_gang_id in bot.state.gangs:
            owner = bot.state.gangs[d.owner_gang_id].name
        else:
            owner = "🟢 libre"
        lines.append(f"**{d.name}** ({d.dtype.value}) — police {d.police_level} — {owner}")
    await interaction.response.send_message(
        embed=embed("🗺️ Map de Leonida", "\n".join(lines)))


@bot.tree.command(name="capture", description="Capturer un district libre")
@app_commands.describe(district_id="ID du district (voir /map)")
async def capture(interaction: discord.Interaction, district_id: str):
    gang = bot.state.gang_of(str(interaction.user.id))
    if gang is None:
        await interaction.response.send_message(
            embed=embed("Erreur", "Rejoins un gang d'abord."), ephemeral=True)
        return
    res = bot.state.territory.capture(gang.id, district_id)
    bot.state.save()
    await interaction.response.send_message(
        embed=embed("Capture", res.message, gang_color(gang.color)),
        ephemeral=not res.success)


@bot.tree.command(name="raid", description="Raider un district ennemi")
@app_commands.describe(district_id="ID du district à attaquer")
async def raid(interaction: discord.Interaction, district_id: str):
    gang = bot.state.gang_of(str(interaction.user.id))
    if gang is None:
        await interaction.response.send_message(
            embed=embed("Erreur", "Rejoins un gang d'abord."), ephemeral=True)
        return
    res = bot.state.territory.raid(gang.id, district_id)
    bot.state.save()
    color = gang_color(gang.color) if res.success else 0xED4245
    await interaction.response.send_message(
        embed=embed("⚔️ Raid", res.message, color))


@bot.tree.command(name="leaderboard", description="Classement par contrôle de map")
async def leaderboard(interaction: discord.Interaction):
    lb = bot.state.territory.leaderboard()
    if not lb:
        await interaction.response.send_message(
            embed=embed("🏆 Leaderboard", "Aucun territoire contrôlé pour l'instant."))
        return
    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, (gid, pct) in enumerate(lb):
        prefix = medals[i] if i < 3 else f"{i+1}."
        lines.append(f"{prefix} **{bot.state.gangs[gid].name}** — {pct}%")
    leader = bot.state.territory.empire_leader()
    if leader:
        lines.append(f"\n👑 **EMPIRE LEADER :** {bot.state.gangs[leader].name}")
    await interaction.response.send_message(
        embed=embed("🏆 Leaderboard — Contrôle de Leonida", "\n".join(lines)))


# ---------------------------------------------------------------------------
# Commandes — Économie
# ---------------------------------------------------------------------------

@bot.tree.command(name="upgrade", description="Améliorer la base de ton gang")
async def upgrade(interaction: discord.Interaction):
    gang = bot.state.gang_of(str(interaction.user.id))
    if gang is None:
        await interaction.response.send_message(
            embed=embed("Erreur", "Rejoins un gang d'abord."), ephemeral=True)
        return
    ok, msg = bot.state.economy.upgrade_base(gang.id)
    bot.state.save()
    await interaction.response.send_message(
        embed=embed("🧱 Upgrade base", msg, gang_color(gang.color)),
        ephemeral=not ok)


@bot.tree.command(name="sell", description="Vendre des ressources contre du cash")
@app_commands.describe(ressource="cash / drogue / armes", quantite="Quantité")
async def sell(interaction: discord.Interaction, ressource: str, quantite: int):
    gang = bot.state.gang_of(str(interaction.user.id))
    if gang is None:
        await interaction.response.send_message(
            embed=embed("Erreur", "Rejoins un gang d'abord."), ephemeral=True)
        return
    try:
        rtype = ResourceType(ressource.lower())
    except ValueError:
        await interaction.response.send_message(
            embed=embed("Erreur", "Ressource invalide : cash, drogue ou armes."),
            ephemeral=True)
        return
    prices = {ResourceType.DROGUE: 80, ResourceType.ARMES: 150, ResourceType.CASH: 1}
    ok, msg = bot.state.economy.sell_resource(
        gang.id, rtype, quantite, prices[rtype])
    bot.state.save()
    await interaction.response.send_message(
        embed=embed("💰 Marché noir", msg, gang_color(gang.color)),
        ephemeral=not ok)


# ---------------------------------------------------------------------------
# Entrée
# ---------------------------------------------------------------------------

def main():
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise SystemExit("Définis la variable d'environnement DISCORD_TOKEN.")
    bot.run(token)


if __name__ == "__main__":
    main()
