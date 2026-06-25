# LEONIDA: DISTRICT WARS — moteur + bot Discord

Méta-jeu de guerre de gangs jouable **sur Discord dès maintenant**, avant la
sortie de GTA 6. La logique de jeu est volontairement séparée de Discord :
le jour où un framework RP pour GTA 6 existera, tu rebranches `leonida/core`
dessus sans réécrire la logique.

## Architecture (couches)

```
leonida/
├── core/                  ← MOTEUR (pur Python, 0 dépendance)
│   ├── models.py          District, Gang, enums
│   ├── economy.py         revenus passifs, production, sinks anti-inflation
│   ├── territory.py       capture, raids, leaderboard, endgame
│   └── state.py           état global + persistance JSON + map de départ
└── bot/
    └── main.py            interface Discord (slash-commands) sur le moteur
```

Le **core ne sait pas que Discord existe**. C'est ce qui rend le projet
réutilisable : un futur module `leonida/gta/` pourra appeler exactement les
mêmes fonctions (`capture`, `raid`, `tick`...) que le bot appelle aujourd'hui.

## Lancer le bot

1. Crée une application + bot sur https://discord.com/developers/applications
2. Active "MESSAGE CONTENT INTENT" n'est PAS requis (on n'utilise que des slash-commands).
3. Installe et lance :

```bash
pip install -U "discord.py>=2.3"
export DISCORD_TOKEN="ton_token_ici"
cd leonida   # le dossier qui contient le package leonida/
python -m leonida.bot.main
```

## Commandes

| Commande | Effet |
|---|---|
| `/gang_create nom couleur` | Fonder un gang |
| `/gang_join nom` | Rejoindre un gang |
| `/gang_info` | Trésorerie, base, districts, revenus |
| `/map` | État de tous les districts |
| `/capture district_id` | Prendre un district libre |
| `/raid district_id` | Attaquer un district ennemi (cooldown 30 min) |
| `/leaderboard` | Classement par % de map + Empire Leader |
| `/upgrade` | Améliorer la base (sink économique) |
| `/sell ressource quantité` | Vendre drogue/armes contre cash |

## Boucle de jeu

- Un **tick économique** tourne toutes les 5 min : chaque district contrôlé
  verse cash + production à son gang.
- Les **sinks** (upgrade base, coût d'entrée raid) retirent du cash de
  l'économie pour éviter l'inflation.
- **Endgame** : contrôler 60% de la map → Empire Leader.

## Prochaines briques (faciles à ajouter sur cette base)

- Saisons (reset partiel des `owner_gang_id` + archivage du leaderboard)
- Police jouable (rôle qui réduit les revenus illégaux d'un district)
- Alliances / trahisons entre gangs
- Cosmétiques (branding stocké sur `Gang.color` + champs à ajouter)
- Notifications de raid en temps réel dans `#wars-live`
