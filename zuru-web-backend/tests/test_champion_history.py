"""Tests para el log persistente de viewer_match_history y el endpoint
/championHistory. Verifica:
- INSERT OR IGNORE es idempotente sobre (match_id, viewer_puuid)
- El endpoint agrega correctamente games/wins/avg_kda/avg_tumor
- Recent matches están ordenados por game_date DESC
- limit cap (1..200) se aplica

Run: pytest tests/test_champion_history.py -v
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))


@pytest.fixture
def isolated_app(tmp_path, monkeypatch):
    """Inicializa main.py contra un DATA_DIR aislado por test."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import importlib
    # Reload el módulo entero para que las conexiones DB se re-creen contra DATA_DIR.
    import users_db
    importlib.reload(users_db)
    import main as main_module
    importlib.reload(main_module)
    main_module.app.testing = True
    return main_module


def _add(main_module, **kw):
    """Atajo: invoca el helper con defaults sensatos para los args opcionales."""
    main_module.viewer_match_history_add(
        match_id=kw["match_id"],
        viewer_puuid=kw["viewer_puuid"],
        champion_name=kw["champion_name"],
        queue_id=kw.get("queue_id", 420),
        game_date=kw.get("game_date", 1718000000.0),
        game_duration=kw.get("game_duration", 1500),
        win=kw.get("win", False),
        kills=kw.get("kills", 0), deaths=kw.get("deaths", 0), assists=kw.get("assists", 0),
        kda_ratio=kw.get("kda_ratio", 0.0),
        cs=kw.get("cs", 0), damage=kw.get("damage", 0), vision_score=kw.get("vision_score", 0),
        tumor_score=kw.get("tumor_score"),
        lane=kw.get("lane"),
        tier=kw.get("tier", "GOLD"),
    )


def test_insert_or_ignore_idempotent(isolated_app):
    m = isolated_app
    _add(m, match_id="MATCH1", viewer_puuid="P", champion_name="Yasuo",
         win=True, kills=10, deaths=2, assists=5, kda_ratio=7.5)
    _add(m, match_id="MATCH1", viewer_puuid="P", champion_name="Yasuo",
         win=False, kills=0, deaths=99, assists=0, kda_ratio=0)  # mismo PK
    db = m._pred_db()
    rows = db.execute(
        "SELECT kills, deaths, win FROM viewer_match_history WHERE match_id='MATCH1'",
    ).fetchall()
    assert len(rows) == 1
    assert rows[0] == (10, 2, 1)  # primer insert ganó (IGNORE no sobreescribe)


def test_endpoint_aggregates(isolated_app):
    m = isolated_app
    # 3 partidas con Yasuo: 2 wins, 1 loss
    _add(m, match_id="A", viewer_puuid="P", champion_name="Yasuo",
         win=True, kills=8, deaths=2, assists=4, kda_ratio=6.0,
         cs=200, damage=20000, vision_score=10, tumor_score=20,
         game_date=1700000000.0)
    _add(m, match_id="B", viewer_puuid="P", champion_name="Yasuo",
         win=True, kills=5, deaths=3, assists=10, kda_ratio=5.0,
         cs=180, damage=18000, vision_score=12, tumor_score=30,
         game_date=1701000000.0)
    _add(m, match_id="C", viewer_puuid="P", champion_name="Yasuo",
         win=False, kills=1, deaths=8, assists=3, kda_ratio=0.5,
         cs=120, damage=10000, vision_score=8, tumor_score=70,
         game_date=1702000000.0)
    # 1 partida con Ahri (no debe afectar)
    _add(m, match_id="D", viewer_puuid="P", champion_name="Ahri",
         win=True, kills=10, deaths=0, assists=0, kda_ratio=10.0)

    client = m.app.test_client()
    r = client.get("/championHistory?viewer_puuid=P&champion=Yasuo")
    assert r.status_code == 200
    data = r.get_json()
    assert data["total_games"] == 3
    assert data["total_wins"] == 2
    assert data["lifetime_winrate"] == round(2 / 3 * 100, 1)
    assert data["avg_kda"] == round((6.0 + 5.0 + 0.5) / 3, 2)
    assert data["avg_tumor"] == round((20 + 30 + 70) / 3)
    assert len(data["recent_matches"]) == 3
    # Más reciente primero (game_date DESC)
    assert data["recent_matches"][0]["match_id"] == "C"
    assert data["recent_matches"][1]["match_id"] == "B"
    assert data["recent_matches"][2]["match_id"] == "A"


def test_endpoint_zero_games_for_unknown_champion(isolated_app):
    m = isolated_app
    _add(m, match_id="X", viewer_puuid="P", champion_name="Yasuo")
    client = m.app.test_client()
    r = client.get("/championHistory?viewer_puuid=P&champion=Lulu")
    assert r.status_code == 200
    data = r.get_json()
    assert data["total_games"] == 0
    assert data["lifetime_winrate"] is None
    assert data["recent_matches"] == []


def test_endpoint_requires_params(isolated_app):
    m = isolated_app
    client = m.app.test_client()
    r = client.get("/championHistory?viewer_puuid=P")
    assert r.status_code == 400
    r = client.get("/championHistory?champion=Yasuo")
    assert r.status_code == 400


def test_limit_caps(isolated_app):
    m = isolated_app
    # Insert 5 matches con timestamps crecientes para verificar orden.
    for i in range(5):
        _add(m, match_id=f"L{i}", viewer_puuid="P", champion_name="Yasuo",
             game_date=1700000000.0 + i * 10000)
    client = m.app.test_client()
    # Limit 3 → top 3 más recientes (L4, L3, L2)
    r = client.get("/championHistory?viewer_puuid=P&champion=Yasuo&limit=3")
    data = r.get_json()
    assert len(data["recent_matches"]) == 3
    assert data["recent_matches"][0]["match_id"] == "L4"
    assert data["recent_matches"][2]["match_id"] == "L2"
    # total_games sigue siendo el global (5) aunque el limit recorte recent
    assert data["total_games"] == 5
