"""Role/lane inference para live game.

Dos responsabilidades:

1. **CHAMPION_DISPLAY_NAMES** — Mapa de internal-name (Riot/DDragon `id`,
   usado por las URLs de iconos) → friendly name (display). El caso famoso
   es Wukong: DDragon lo llama `MonkeyKing`, pero el user espera ver "Wukong"
   en la UI.

2. **assign_team_roles** — Dado 5 champions de un equipo + sus spells (para
   detectar Smite=JUNGLE), devuelve la asignación de roles más probable
   (TOP/JUNGLE/MIDDLE/BOTTOM/UTILITY) usando brute force sobre las 5! = 120
   permutaciones. Mejor que el orden del array porque a) el array de Riot a
   veces no respeta loading-screen order, y b) un campeón con rol clarísimo
   (Soraka → SUPPORT) gana sobre ambiguos (Pyke → mid/sup) de forma natural.

El scoring por champion → role NO es exhaustivo ni perfecto: refleja el
meta más común en SoloQ/Flex. Para campeones flex damos puntos a varios
roles. Un campeón ausente del mapa cae a un score uniforme (no influye),
así que la asignación funciona con champs nuevos hasta que actualicemos.
"""

# ---------------------------------------------------------------------------
# Display names (Riot internal → friendly)
# ---------------------------------------------------------------------------

CHAMPION_DISPLAY_NAMES = {
    "MonkeyKing": "Wukong",
    "Chogath": "Cho'Gath",
    "FiddleSticks": "Fiddlesticks",  # variante con S mayúscula
    "Fiddlesticks": "Fiddlesticks",
    "VelKoz": "Vel'Koz",
    "KhaZix": "Kha'Zix",
    "Khazix": "Kha'Zix",  # variante sin Z mayúscula
    "RekSai": "Rek'Sai",
    "KaiSa": "Kai'Sa",
    "KogMaw": "Kog'Maw",
    "BelVeth": "Bel'Veth",
    "Belveth": "Bel'Veth",
    "JarvanIV": "Jarvan IV",
    "MasterYi": "Master Yi",
    "MissFortune": "Miss Fortune",
    "Nunu": "Nunu y Willump",
    "NunuWillump": "Nunu y Willump",
    "TahmKench": "Tahm Kench",
    "TwistedFate": "Twisted Fate",
    "XinZhao": "Xin Zhao",
    "LeeSin": "Lee Sin",
    "AurelionSol": "Aurelion Sol",
    "DrMundo": "Dr. Mundo",
    "Renata": "Renata Glasc",
    "RenataGlasc": "Renata Glasc",
    "MalphiteSwain": "Malphite",  # paranoia por si Riot mezcla nombres
    "MasterYi": "Master Yi",
    "KSante": "K'Sante",
}


def champ_display_name(internal_name):
    """internal_name es el `id` de DDragon ('MonkeyKing', 'Yasuo'…).
    Devuelve el display name correcto ('Wukong', 'Yasuo'…)."""
    if not internal_name:
        return ""
    return CHAMPION_DISPLAY_NAMES.get(internal_name, internal_name)


# ---------------------------------------------------------------------------
# Role affinity per champion (scoring 0-100 per role)
# ---------------------------------------------------------------------------

# Rol IDs estándar que usa Riot Match v5.
_ROLES = ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY")

# Champions con UN rol fuertemente preferido — score 100 en su lane natural,
# scores bajos en el resto. La estructura es dict[name → dict[role → score]].
#
# Para flex picks definimos varios roles con scores intermedios (Pyke 80
# SUPPORT + 40 MID + 30 JUNGLE) para que el solver pueda asignarlo a su
# segunda opción si su primera ya está ocupada por un candidato más rígido.
#
# La lista NO es exhaustiva: ~95% del meta SoloQ. Champs sin entry caen a
# scoring uniforme 20/20/20/20/20 — no influyen en la asignación.
CHAMPION_ROLE_AFFINITY = {
    # === TOP ===
    "Aatrox":       {"TOP": 95, "JUNGLE": 5, "MIDDLE": 15, "BOTTOM": 0, "UTILITY": 0},
    "Camille":      {"TOP": 95, "JUNGLE": 0, "MIDDLE": 5, "BOTTOM": 0, "UTILITY": 0},
    "Chogath":      {"TOP": 90, "JUNGLE": 5, "MIDDLE": 15, "BOTTOM": 0, "UTILITY": 0},
    "Darius":       {"TOP": 95, "JUNGLE": 5, "MIDDLE": 5, "BOTTOM": 0, "UTILITY": 0},
    "DrMundo":      {"TOP": 95, "JUNGLE": 10, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 0},
    "Fiora":        {"TOP": 95, "JUNGLE": 0, "MIDDLE": 5, "BOTTOM": 0, "UTILITY": 0},
    "Gangplank":    {"TOP": 90, "JUNGLE": 0, "MIDDLE": 20, "BOTTOM": 0, "UTILITY": 0},
    "Garen":        {"TOP": 95, "JUNGLE": 0, "MIDDLE": 5, "BOTTOM": 0, "UTILITY": 0},
    "Gnar":         {"TOP": 95, "JUNGLE": 0, "MIDDLE": 5, "BOTTOM": 0, "UTILITY": 0},
    "Gragas":       {"TOP": 40, "JUNGLE": 70, "MIDDLE": 30, "BOTTOM": 0, "UTILITY": 5},
    "Illaoi":       {"TOP": 95, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 0},
    "Irelia":       {"TOP": 75, "JUNGLE": 0, "MIDDLE": 60, "BOTTOM": 0, "UTILITY": 0},
    "Jax":          {"TOP": 85, "JUNGLE": 30, "MIDDLE": 5, "BOTTOM": 0, "UTILITY": 0},
    "Jayce":        {"TOP": 80, "JUNGLE": 0, "MIDDLE": 50, "BOTTOM": 0, "UTILITY": 0},
    "Kayle":        {"TOP": 75, "JUNGLE": 0, "MIDDLE": 35, "BOTTOM": 0, "UTILITY": 0},
    "Kennen":       {"TOP": 80, "JUNGLE": 0, "MIDDLE": 30, "BOTTOM": 5, "UTILITY": 0},
    "Kled":         {"TOP": 95, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 0},
    "KSante":       {"TOP": 95, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 0},
    "Malphite":     {"TOP": 80, "JUNGLE": 0, "MIDDLE": 30, "BOTTOM": 0, "UTILITY": 5},
    "Mordekaiser":  {"TOP": 90, "JUNGLE": 0, "MIDDLE": 10, "BOTTOM": 0, "UTILITY": 0},
    "Nasus":        {"TOP": 95, "JUNGLE": 5, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 0},
    "Olaf":         {"TOP": 50, "JUNGLE": 80, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 0},
    "Ornn":         {"TOP": 95, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 0},
    "Pantheon":     {"TOP": 50, "JUNGLE": 30, "MIDDLE": 50, "BOTTOM": 0, "UTILITY": 60},
    "Poppy":        {"TOP": 70, "JUNGLE": 50, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 60},
    "Quinn":        {"TOP": 75, "JUNGLE": 0, "MIDDLE": 30, "BOTTOM": 20, "UTILITY": 0},
    "Renekton":     {"TOP": 90, "JUNGLE": 0, "MIDDLE": 20, "BOTTOM": 0, "UTILITY": 0},
    "Riven":        {"TOP": 95, "JUNGLE": 0, "MIDDLE": 5, "BOTTOM": 0, "UTILITY": 0},
    "Rumble":       {"TOP": 75, "JUNGLE": 0, "MIDDLE": 30, "BOTTOM": 0, "UTILITY": 0},
    "Sett":         {"TOP": 85, "JUNGLE": 0, "MIDDLE": 5, "BOTTOM": 0, "UTILITY": 40},
    "Shen":         {"TOP": 90, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 20},
    "Singed":       {"TOP": 90, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 5},
    "Sion":         {"TOP": 90, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 5},
    "Teemo":        {"TOP": 90, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 5},
    "Trundle":      {"TOP": 70, "JUNGLE": 70, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 0},
    "Tryndamere":   {"TOP": 95, "JUNGLE": 0, "MIDDLE": 5, "BOTTOM": 0, "UTILITY": 0},
    "Urgot":        {"TOP": 95, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 0},
    "Volibear":     {"TOP": 70, "JUNGLE": 60, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 0},
    "MonkeyKing":   {"TOP": 70, "JUNGLE": 70, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 0},  # Wukong
    "Yorick":       {"TOP": 95, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 0},

    # === JUNGLE ===
    "Amumu":        {"TOP": 0, "JUNGLE": 90, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 30},
    "Belveth":      {"TOP": 0, "JUNGLE": 95, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 0},
    "BelVeth":      {"TOP": 0, "JUNGLE": 95, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 0},
    "Briar":        {"TOP": 0, "JUNGLE": 95, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 0},
    "Diana":        {"TOP": 0, "JUNGLE": 60, "MIDDLE": 75, "BOTTOM": 0, "UTILITY": 0},
    "Ekko":         {"TOP": 0, "JUNGLE": 60, "MIDDLE": 75, "BOTTOM": 0, "UTILITY": 0},
    "Elise":        {"TOP": 5, "JUNGLE": 90, "MIDDLE": 15, "BOTTOM": 0, "UTILITY": 5},
    "Evelynn":      {"TOP": 0, "JUNGLE": 95, "MIDDLE": 5, "BOTTOM": 0, "UTILITY": 0},
    "Fiddlesticks": {"TOP": 5, "JUNGLE": 90, "MIDDLE": 15, "BOTTOM": 0, "UTILITY": 20},
    "Graves":       {"TOP": 0, "JUNGLE": 90, "MIDDLE": 5, "BOTTOM": 5, "UTILITY": 0},
    "Hecarim":      {"TOP": 0, "JUNGLE": 95, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 0},
    "Ivern":        {"TOP": 0, "JUNGLE": 90, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 30},
    "JarvanIV":     {"TOP": 0, "JUNGLE": 90, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 0},
    "Karthus":      {"TOP": 0, "JUNGLE": 75, "MIDDLE": 60, "BOTTOM": 0, "UTILITY": 0},
    "Kayn":         {"TOP": 0, "JUNGLE": 95, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 0},
    "Khazix":       {"TOP": 0, "JUNGLE": 90, "MIDDLE": 30, "BOTTOM": 0, "UTILITY": 0},
    "KhaZix":       {"TOP": 0, "JUNGLE": 90, "MIDDLE": 30, "BOTTOM": 0, "UTILITY": 0},
    "Kindred":      {"TOP": 0, "JUNGLE": 95, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 0},
    "LeeSin":       {"TOP": 5, "JUNGLE": 90, "MIDDLE": 10, "BOTTOM": 0, "UTILITY": 5},
    "Lillia":       {"TOP": 0, "JUNGLE": 90, "MIDDLE": 5, "BOTTOM": 0, "UTILITY": 0},
    "MasterYi":     {"TOP": 0, "JUNGLE": 95, "MIDDLE": 5, "BOTTOM": 0, "UTILITY": 0},
    "Nidalee":      {"TOP": 0, "JUNGLE": 90, "MIDDLE": 30, "BOTTOM": 0, "UTILITY": 0},
    "Nocturne":     {"TOP": 0, "JUNGLE": 85, "MIDDLE": 30, "BOTTOM": 0, "UTILITY": 0},
    "Nunu":         {"TOP": 0, "JUNGLE": 95, "MIDDLE": 5, "BOTTOM": 0, "UTILITY": 0},
    "Rammus":       {"TOP": 0, "JUNGLE": 90, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 0},
    "RekSai":       {"TOP": 0, "JUNGLE": 95, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 0},
    "Sejuani":      {"TOP": 5, "JUNGLE": 90, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 0},
    "Shaco":        {"TOP": 0, "JUNGLE": 95, "MIDDLE": 5, "BOTTOM": 0, "UTILITY": 30},
    "Shyvana":      {"TOP": 30, "JUNGLE": 85, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 0},
    "Skarner":      {"TOP": 30, "JUNGLE": 80, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 0},
    "Taliyah":      {"TOP": 0, "JUNGLE": 80, "MIDDLE": 60, "BOTTOM": 0, "UTILITY": 0},
    "Udyr":         {"TOP": 30, "JUNGLE": 85, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 0},
    "Vi":           {"TOP": 0, "JUNGLE": 95, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 0},
    "Viego":        {"TOP": 5, "JUNGLE": 90, "MIDDLE": 20, "BOTTOM": 0, "UTILITY": 0},
    "Warwick":      {"TOP": 30, "JUNGLE": 90, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 0},
    "XinZhao":      {"TOP": 5, "JUNGLE": 95, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 0},
    "Zac":          {"TOP": 30, "JUNGLE": 90, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 0},

    # === MIDDLE ===
    "Ahri":         {"TOP": 0, "JUNGLE": 0, "MIDDLE": 95, "BOTTOM": 0, "UTILITY": 0},
    "Akali":        {"TOP": 30, "JUNGLE": 0, "MIDDLE": 80, "BOTTOM": 0, "UTILITY": 0},
    "Akshan":       {"TOP": 5, "JUNGLE": 0, "MIDDLE": 75, "BOTTOM": 20, "UTILITY": 0},
    "Anivia":       {"TOP": 0, "JUNGLE": 0, "MIDDLE": 90, "BOTTOM": 0, "UTILITY": 0},
    "Annie":        {"TOP": 5, "JUNGLE": 0, "MIDDLE": 80, "BOTTOM": 0, "UTILITY": 40},
    "AurelionSol":  {"TOP": 0, "JUNGLE": 0, "MIDDLE": 95, "BOTTOM": 0, "UTILITY": 0},
    "Azir":         {"TOP": 0, "JUNGLE": 0, "MIDDLE": 95, "BOTTOM": 0, "UTILITY": 0},
    "Cassiopeia":   {"TOP": 20, "JUNGLE": 0, "MIDDLE": 90, "BOTTOM": 0, "UTILITY": 0},
    "Corki":        {"TOP": 0, "JUNGLE": 0, "MIDDLE": 80, "BOTTOM": 20, "UTILITY": 0},
    "Fizz":         {"TOP": 0, "JUNGLE": 0, "MIDDLE": 95, "BOTTOM": 0, "UTILITY": 0},
    "Galio":        {"TOP": 20, "JUNGLE": 0, "MIDDLE": 85, "BOTTOM": 0, "UTILITY": 30},
    "Hwei":         {"TOP": 0, "JUNGLE": 0, "MIDDLE": 90, "BOTTOM": 0, "UTILITY": 30},
    "Kassadin":     {"TOP": 0, "JUNGLE": 0, "MIDDLE": 95, "BOTTOM": 0, "UTILITY": 0},
    "Katarina":     {"TOP": 0, "JUNGLE": 0, "MIDDLE": 95, "BOTTOM": 0, "UTILITY": 0},
    "Leblanc":      {"TOP": 0, "JUNGLE": 0, "MIDDLE": 95, "BOTTOM": 0, "UTILITY": 0},
    "Lissandra":    {"TOP": 0, "JUNGLE": 0, "MIDDLE": 90, "BOTTOM": 0, "UTILITY": 0},
    "Lux":          {"TOP": 0, "JUNGLE": 0, "MIDDLE": 60, "BOTTOM": 0, "UTILITY": 80},
    "Malzahar":     {"TOP": 0, "JUNGLE": 0, "MIDDLE": 90, "BOTTOM": 0, "UTILITY": 0},
    "Naafiri":      {"TOP": 0, "JUNGLE": 0, "MIDDLE": 90, "BOTTOM": 0, "UTILITY": 0},
    "Neeko":        {"TOP": 0, "JUNGLE": 0, "MIDDLE": 60, "BOTTOM": 0, "UTILITY": 60},
    "Orianna":      {"TOP": 0, "JUNGLE": 0, "MIDDLE": 90, "BOTTOM": 0, "UTILITY": 0},
    "Qiyana":       {"TOP": 0, "JUNGLE": 30, "MIDDLE": 85, "BOTTOM": 0, "UTILITY": 0},
    "Ryze":         {"TOP": 30, "JUNGLE": 0, "MIDDLE": 80, "BOTTOM": 0, "UTILITY": 0},
    "Sylas":        {"TOP": 20, "JUNGLE": 30, "MIDDLE": 80, "BOTTOM": 0, "UTILITY": 0},
    "Syndra":       {"TOP": 0, "JUNGLE": 0, "MIDDLE": 95, "BOTTOM": 0, "UTILITY": 0},
    "Talon":        {"TOP": 0, "JUNGLE": 30, "MIDDLE": 90, "BOTTOM": 0, "UTILITY": 0},
    "TwistedFate":  {"TOP": 0, "JUNGLE": 0, "MIDDLE": 95, "BOTTOM": 0, "UTILITY": 0},
    "Veigar":       {"TOP": 0, "JUNGLE": 0, "MIDDLE": 70, "BOTTOM": 50, "UTILITY": 30},
    "Vex":          {"TOP": 0, "JUNGLE": 0, "MIDDLE": 95, "BOTTOM": 0, "UTILITY": 0},
    "Viktor":       {"TOP": 0, "JUNGLE": 0, "MIDDLE": 95, "BOTTOM": 0, "UTILITY": 0},
    "Vladimir":     {"TOP": 30, "JUNGLE": 0, "MIDDLE": 85, "BOTTOM": 0, "UTILITY": 0},
    "Xerath":       {"TOP": 0, "JUNGLE": 0, "MIDDLE": 80, "BOTTOM": 0, "UTILITY": 50},
    "Yasuo":        {"TOP": 50, "JUNGLE": 0, "MIDDLE": 85, "BOTTOM": 30, "UTILITY": 0},
    "Yone":         {"TOP": 50, "JUNGLE": 0, "MIDDLE": 85, "BOTTOM": 0, "UTILITY": 0},
    "Zed":          {"TOP": 0, "JUNGLE": 0, "MIDDLE": 95, "BOTTOM": 0, "UTILITY": 0},
    "Ziggs":        {"TOP": 0, "JUNGLE": 0, "MIDDLE": 60, "BOTTOM": 75, "UTILITY": 0},
    "Zoe":          {"TOP": 0, "JUNGLE": 0, "MIDDLE": 90, "BOTTOM": 0, "UTILITY": 0},

    # === BOTTOM (ADC) ===
    "Aphelios":     {"TOP": 0, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 95, "UTILITY": 0},
    "Ashe":         {"TOP": 0, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 90, "UTILITY": 30},
    "Caitlyn":      {"TOP": 0, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 95, "UTILITY": 0},
    "Draven":       {"TOP": 0, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 95, "UTILITY": 0},
    "Ezreal":       {"TOP": 0, "JUNGLE": 0, "MIDDLE": 15, "BOTTOM": 90, "UTILITY": 0},
    "Jhin":         {"TOP": 0, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 95, "UTILITY": 0},
    "Jinx":         {"TOP": 0, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 95, "UTILITY": 0},
    "KaiSa":        {"TOP": 0, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 95, "UTILITY": 0},
    "Kalista":      {"TOP": 0, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 90, "UTILITY": 0},
    "KogMaw":       {"TOP": 0, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 95, "UTILITY": 0},
    "Lucian":       {"TOP": 0, "JUNGLE": 0, "MIDDLE": 30, "BOTTOM": 85, "UTILITY": 0},
    "MissFortune":  {"TOP": 0, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 90, "UTILITY": 30},
    "Nilah":        {"TOP": 0, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 90, "UTILITY": 0},
    "Samira":       {"TOP": 0, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 95, "UTILITY": 0},
    "Senna":        {"TOP": 0, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 50, "UTILITY": 70},
    "Sivir":        {"TOP": 0, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 95, "UTILITY": 0},
    "Smolder":      {"TOP": 0, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 90, "UTILITY": 0},
    "Tristana":     {"TOP": 0, "JUNGLE": 0, "MIDDLE": 30, "BOTTOM": 85, "UTILITY": 0},
    "Twitch":       {"TOP": 0, "JUNGLE": 30, "MIDDLE": 0, "BOTTOM": 85, "UTILITY": 0},
    "Varus":        {"TOP": 0, "JUNGLE": 0, "MIDDLE": 30, "BOTTOM": 85, "UTILITY": 0},
    "Vayne":        {"TOP": 30, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 85, "UTILITY": 0},
    "Xayah":        {"TOP": 0, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 95, "UTILITY": 0},
    "Zeri":         {"TOP": 0, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 95, "UTILITY": 0},

    # === UTILITY (SUPPORT) ===
    "Alistar":      {"TOP": 5, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 95},
    "Bard":         {"TOP": 0, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 95},
    "Blitzcrank":   {"TOP": 0, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 95},
    "Brand":        {"TOP": 0, "JUNGLE": 30, "MIDDLE": 30, "BOTTOM": 0, "UTILITY": 80},
    "Braum":        {"TOP": 0, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 95},
    "Janna":        {"TOP": 0, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 95},
    "Karma":        {"TOP": 5, "JUNGLE": 0, "MIDDLE": 20, "BOTTOM": 0, "UTILITY": 90},
    "Leona":        {"TOP": 0, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 95},
    "Lulu":         {"TOP": 30, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 90},
    "Maokai":       {"TOP": 50, "JUNGLE": 30, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 80},
    "Milio":        {"TOP": 0, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 95},
    "Morgana":      {"TOP": 0, "JUNGLE": 30, "MIDDLE": 30, "BOTTOM": 0, "UTILITY": 90},
    "Nami":         {"TOP": 0, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 95},
    "Nautilus":     {"TOP": 5, "JUNGLE": 30, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 90},
    "Pyke":         {"TOP": 0, "JUNGLE": 30, "MIDDLE": 40, "BOTTOM": 0, "UTILITY": 80},
    "Rakan":        {"TOP": 0, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 95},
    "Rell":         {"TOP": 0, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 95},
    "Renata":       {"TOP": 0, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 95},
    "RenataGlasc":  {"TOP": 0, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 95},
    "Seraphine":    {"TOP": 0, "JUNGLE": 0, "MIDDLE": 30, "BOTTOM": 30, "UTILITY": 80},
    "Sona":         {"TOP": 0, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 30, "UTILITY": 90},
    "Soraka":       {"TOP": 30, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 95},
    "Swain":        {"TOP": 50, "JUNGLE": 0, "MIDDLE": 60, "BOTTOM": 40, "UTILITY": 60},
    "TahmKench":    {"TOP": 70, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 70},
    "Taric":        {"TOP": 30, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 95},
    "Thresh":       {"TOP": 0, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 95},
    "VelKoz":       {"TOP": 0, "JUNGLE": 0, "MIDDLE": 60, "BOTTOM": 0, "UTILITY": 70},
    "Xerath":       {"TOP": 0, "JUNGLE": 0, "MIDDLE": 60, "BOTTOM": 0, "UTILITY": 60},
    "Yuumi":        {"TOP": 0, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 100},
    "Zilean":       {"TOP": 0, "JUNGLE": 0, "MIDDLE": 30, "BOTTOM": 0, "UTILITY": 80},
    "Zyra":         {"TOP": 0, "JUNGLE": 0, "MIDDLE": 0, "BOTTOM": 0, "UTILITY": 95},
}

# Default uniforme cuando un champion no está en el mapa (champ nuevo, typo).
# 20 en todos para que no influya en la asignación pero tampoco la sabotee.
_DEFAULT_AFFINITY = {r: 20 for r in _ROLES}

# Smite spell id en Riot's spectator-v5.
_SMITE_SPELL_ID = 11
# Boost que aplicamos al score JUNGLE cuando el champion tiene Smite. 200 es
# más que cualquier otro score posible, así que Smite gana siempre.
_SMITE_BOOST = 200


def _affinity_for(champion_name):
    return CHAMPION_ROLE_AFFINITY.get(champion_name, _DEFAULT_AFFINITY)


def assign_team_roles(team):
    """Asigna roles TOP/JUNGLE/MIDDLE/BOTTOM/UTILITY a los 5 jugadores de un
    equipo. Brute force sobre las 120 permutaciones — instantáneo y siempre
    encuentra el óptimo global.

    `team` es una lista de dicts con al menos:
      - 'champion_name': internal id (e.g. 'MonkeyKing', 'Yasuo')
      - 'spell1_id', 'spell2_id': ints de summoner spells

    Devuelve list[str] de roles en el mismo orden que la entrada. Si el
    equipo no tiene exactamente 5 jugadores, devuelve [] (caller debe usar
    su fallback)."""
    import itertools

    if len(team) != 5:
        return []

    # Pre-compute scoring matrix: rows = players, cols = roles
    matrix = []
    for p in team:
        champ = p.get("champion_name") or ""
        aff = dict(_affinity_for(champ))  # copia
        # Smite boost: si tiene Smite, JUNGLE pasa a ganar siempre.
        if p.get("spell1_id") == _SMITE_SPELL_ID or p.get("spell2_id") == _SMITE_SPELL_ID:
            aff["JUNGLE"] = aff.get("JUNGLE", 0) + _SMITE_BOOST
        matrix.append(aff)

    best_score = -1
    best_perm = None
    for perm in itertools.permutations(_ROLES):
        score = sum(matrix[i][perm[i]] for i in range(5))
        if score > best_score:
            best_score = score
            best_perm = perm

    return list(best_perm) if best_perm else []
