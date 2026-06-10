"""Bravery engine.

Pulls Data Dragon (DDragon) data for champions + items, caches in memory with
24h TTL, and provides a randomizer + post-game compliance/payout calculator.

The user's flow:
  1. Calls /bravery/roll → backend rolls champion + optional lane + optional items
  2. Calls /bravery/lock with the roll → backend escrows stake, stores lock
  3. User plays their next ranked/normal in League with that setup
  4. Background poll or /bravery/resolve-mine detects the match, computes compliance
     and tumor performance, pays out TC

style_mult scaling by dimensions:
  - 1 dim (champion only)        → 1.00x  (basic randomize, no real bravery)
  - 2 dims (champion + 1 extra)  → 1.30x
  - 3 dims (champion + lane + items) → 1.70x

Payout:
  - if champion_match == False  → lock loses all stake (no TC back)
  - else                         → tumor_perf = clamp((100 - tumor)/60, 0, 1.5)
                                    effective_mult = style_mult * compliance_adjust
                                    payout = stake * tumor_perf * effective_mult
"""
import json
import random
import threading
import time

import requests


DDRAGON_VERSIONS_URL = "https://ddragon.leagueoflegends.com/api/versions.json"
DDRAGON_ITEM_URL_TMPL = "https://ddragon.leagueoflegends.com/cdn/{v}/data/en_US/item.json"
DDRAGON_CHAMP_URL_TMPL = "https://ddragon.leagueoflegends.com/cdn/{v}/data/en_US/champion.json"
DDRAGON_TTL_SECONDS = 24 * 3600

VALID_LANES = ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY")

# Cache global (proceso) + lock
_CACHE = {
    "version": None,
    "champions": None,    # list of {id (int), key, name}
    "items": None,        # list of {id (int), name, gold, tags}
    "fetched_at": 0.0,
}
_CACHE_LOCK = threading.Lock()


def _refresh_ddragon():
    """Pull la última versión + champions + items finales filtrados.
    No raise: en caso de fallo deja cache previa, sólo logea."""
    try:
        vres = requests.get(DDRAGON_VERSIONS_URL, timeout=10)
        if not vres.ok:
            return
        versions = vres.json()
        latest = versions[0] if versions else None
        if not latest:
            return

        cres = requests.get(DDRAGON_CHAMP_URL_TMPL.format(v=latest), timeout=10)
        ires = requests.get(DDRAGON_ITEM_URL_TMPL.format(v=latest), timeout=10)
        if not (cres.ok and ires.ok):
            return

        # Champions: data = { ChampName: {key: "266", id: "Aatrox", name: "Aatrox", ...} }
        champ_data = (cres.json() or {}).get("data", {}) or {}
        champions = []
        for entry in champ_data.values():
            try:
                champions.append({
                    "id": int(entry["key"]),    # numérico para Riot match v5
                    "key": entry["id"],          # string slug (e.g. "Aatrox")
                    "name": entry["name"],
                })
            except Exception:
                continue
        champions.sort(key=lambda c: c["name"].lower())

        # Items: data = { "1001": {name, gold:{total}, into:[...], maps:{}, tags:[...] } }
        item_data = (ires.json() or {}).get("data", {}) or {}
        items = []
        for iid, entry in item_data.items():
            try:
                iid_int = int(iid)
                gold = (entry.get("gold") or {}).get("total") or 0
                into = entry.get("into") or []
                tags = entry.get("tags") or []
                # Filtros para "items finales viables en ranked":
                #   - no upgradeable (into vacío)
                #   - precio total >= 2000g (descarta componentes y baratos)
                #   - no consumibles, no trinkets, no jungle items basic
                #   - inStore != false (algunos están en mode-specific maps)
                #   - mapa SR (11) activo
                if into:
                    continue
                if gold < 2000:
                    continue
                if any(t in tags for t in ("Consumable", "Trinket")):
                    continue
                if entry.get("inStore") is False:
                    continue
                maps = entry.get("maps") or {}
                if maps and not maps.get("11", True):
                    continue
                name = entry.get("name") or ""
                # Excluir items "Ornn upgrade" (requiredAlly) que no pueden buildearse libremente
                if entry.get("requiredAlly"):
                    continue
                # Excluir items con "Quick Charge" / "Origin" raros (mythics removidos, runas)
                if entry.get("requiredChampion"):
                    continue
                items.append({
                    "id": iid_int,
                    "name": name,
                    "gold": gold,
                    "tags": tags,
                })
            except Exception:
                continue
        items.sort(key=lambda i: i["name"].lower())

        if not champions or not items:
            return

        with _CACHE_LOCK:
            _CACHE["version"] = latest
            _CACHE["champions"] = champions
            _CACHE["items"] = items
            _CACHE["fetched_at"] = time.time()
    except Exception:
        return


def _ensure_cache():
    now = time.time()
    if _CACHE["champions"] and _CACHE["items"] and (now - _CACHE["fetched_at"]) < DDRAGON_TTL_SECONDS:
        return
    _refresh_ddragon()


def get_data():
    """Returns {version, champions, items}. May trigger a refresh.
    Si DDragon falla y no hay cache previa, devuelve None."""
    _ensure_cache()
    if not (_CACHE["champions"] and _CACHE["items"]):
        return None
    return {
        "version": _CACHE["version"],
        "champions": _CACHE["champions"],
        "items": _CACHE["items"],
        "fetched_at": _CACHE["fetched_at"],
    }


def warm_cache_async():
    """Inicia el fetch de DDragon en un thread separado para no bloquear el arranque
    de Flask. Idempotente: si ya hay cache válida, no hace nada."""
    if _CACHE["champions"] and _CACHE["items"]:
        return
    t = threading.Thread(target=_refresh_ddragon, daemon=True)
    t.start()


# Pre-warm en import (background)
warm_cache_async()


def style_mult_for_dims(dims):
    """dims = set/list de dimensiones activas; debe contener 'champion'."""
    s = set(dims or [])
    if "champion" not in s:
        return 1.0
    n = len(s & {"champion", "lane", "items"})
    if n <= 1:
        return 1.0
    if n == 2:
        return 1.30
    return 1.70


def roll(dimensions, lane_filter=None, item_count=5, seed=None):
    """Genera un roll de bravery.

    dimensions: lista que debe incluir 'champion'. Puede incluir 'lane' e 'items'.
    lane_filter: si dimensions incluye 'lane' y lane_filter es una lane válida,
                 forza esa lane. Si es None, lane se elige al azar.
    item_count: número de items aleatorios a sortear (default 5).

    Devuelve dict con: champion, lane (None si no es dimensión), items (None si no),
    dimensions (set como list), style_mult.
    """
    data = get_data()
    if not data:
        return None
    rng = random.Random(seed) if seed is not None else random
    dims = list({d for d in dimensions or [] if d in ("champion", "lane", "items")})
    if "champion" not in dims:
        dims.append("champion")
    champion = rng.choice(data["champions"])
    lane = None
    if "lane" in dims:
        if lane_filter and lane_filter.upper() in VALID_LANES:
            lane = lane_filter.upper()
        else:
            lane = rng.choice(VALID_LANES)
    items = None
    if "items" in dims:
        pool = data["items"]
        n = max(1, min(item_count, len(pool)))
        items = rng.sample(pool, n)
    return {
        "champion": champion,
        "lane": lane,
        "items": items,
        "dimensions": sorted(dims),
        "style_mult": style_mult_for_dims(dims),
    }


def compute_compliance(lock, participant):
    """Dada una bravery lock y el participant de Riot match v5, calcula:
      - champion_match (bool)
      - lane_match (bool|None) — None si la dimensión 'lane' no estaba activa
      - items_hit_rate (float [0..1]|None) — None si la dim 'items' no estaba activa
      - effective_mult (style_mult ajustado por compliance blanda)

    Reglas:
      - champion es obligatorio: si False, el lock LOSE total.
      - lane: si la dim estaba activa pero el user no jugó la lane,
              style_mult se reduce -0.30 (mínimo 1.0).
      - items: si la dim estaba activa, items_hit_rate = items_acertados / total
              effective_mult *= (0.5 + 0.5 * hit_rate). Hit_rate 0 → halving.
    """
    champion_match = (participant.get("championId") == lock["champion_id"])
    lane_match = None
    if lock.get("lane"):
        # Riot teamPosition: TOP, JUNGLE, MIDDLE, BOTTOM, UTILITY (or '' for arena/aram)
        team_pos = (participant.get("teamPosition") or "").upper()
        lane_match = (team_pos == lock["lane"])
    items_hit_rate = None
    if lock.get("items"):
        rolled_ids = {it["id"] for it in lock["items"] if isinstance(it, dict)}
        played = set()
        for k in ("item0", "item1", "item2", "item3", "item4", "item5", "item6"):
            v = participant.get(k)
            if v and int(v) > 0:
                played.add(int(v))
        hit = len(rolled_ids & played)
        items_hit_rate = (hit / len(rolled_ids)) if rolled_ids else 0.0

    style_mult = float(lock.get("style_mult") or 1.0)
    effective_mult = style_mult
    if lane_match is False:
        effective_mult = max(1.0, effective_mult - 0.30)
    if items_hit_rate is not None:
        effective_mult *= (0.5 + 0.5 * items_hit_rate)

    return {
        "champion_match": bool(champion_match),
        "lane_match": lane_match,
        "items_hit_rate": items_hit_rate,
        "effective_mult": round(effective_mult, 3),
    }


SUS_TUMOR_THRESHOLD = 60.0  # nivel "sus" del codebase — break-even para bravery


def compute_payout(stake, tumor_score, compliance):
    """payout = stake * tumor_perf * effective_mult, capado.

    Si champion_match es False → payout=0 (loss total).
    tumor_perf piecewise centrado en el nivel "sus" (60):
      - tumor 60 → 1.0  (break-even)
      - tumor 20 → 1.5  (cap superior)
      - tumor 100 → 0.0 (lose all)
    Formula: perf = clamp(1.0 + (60 - tumor)/40, 0, 1.5)
      - tumor 0   → 2.5  → capped 1.5
      - tumor 20  → 2.0  → capped 1.5
      - tumor 40  → 1.5
      - tumor 60  → 1.0  ← break-even (recibes tu stake)
      - tumor 80  → 0.5  (pierdes la mitad)
      - tumor 100 → 0.0  (pierdes todo)
    """
    if not compliance.get("champion_match"):
        return 0
    if tumor_score is None:
        return 0
    perf = max(0.0, min(1.5, 1.0 + (SUS_TUMOR_THRESHOLD - float(tumor_score)) / 40.0))
    return int(round(stake * perf * float(compliance["effective_mult"])))
