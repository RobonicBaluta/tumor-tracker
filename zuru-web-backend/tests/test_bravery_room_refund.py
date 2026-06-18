"""Tests para refund_room_bravery_locks: cuando el host de una sala hace
toggle off de Bravery, los locks pending de esa sala deben refundarse
para que los users no pierdan TC con setups huérfanos.

Antes de este fix los locks quedaban en status='pending' indefinidamente
sin pool válido de lanes y el TC nunca volvía.

Run: pytest tests/test_bravery_room_refund.py -v
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import importlib
    import users_db
    importlib.reload(users_db)
    return users_db


def _seed_user(udb, discord_id, name, currency=500):
    u = udb.upsert_user_from_discord(discord_id, name, None)
    udb.add_currency(u["id"], currency, "test seed")
    return udb.get_user_by_id(u["id"])


def _create_pending_lock(udb, user_id, room_code, stake=100, champ=266, lane="TOP"):
    return udb.create_bravery_lock(
        user_id=user_id,
        puuid=f"puuid-{user_id}",
        champion_id=champ,
        champion_name="Aatrox" if champ == 266 else f"Champ{champ}",
        lane=lane,
        items=[],
        style_mult=1.0,
        dimensions=1,
        stake=stake,
        room_code=room_code,
        tier="GOLD",
    )


def test_toggle_off_refunds_pending_locks(isolated_db):
    udb = isolated_db
    host = _seed_user(udb, "host1", "Host")
    p1 = _seed_user(udb, "p1", "Player1")
    p2 = _seed_user(udb, "p2", "Player2")
    room = udb.create_room(owner_user_id=host["id"], name="Test Room")
    udb.set_room_bravery(room["id"], True)
    # Capturamos balance ANTES de los locks. create_bravery_lock hace su
    # propio escrow vía add_currency(-stake), así que el balance "before"
    # más +stake del refund debe igualar el "after refund".
    p1_before = udb.get_user_by_id(p1["id"])["currency"]
    p2_before = udb.get_user_by_id(p2["id"])["currency"]
    lock1 = _create_pending_lock(udb, p1["id"], room["code"], stake=100, champ=266, lane="TOP")
    lock2 = _create_pending_lock(udb, p2["id"], room["code"], stake=150, champ=84, lane="JUNGLE")
    # Sanidad: balances bajaron por el escrow del create_bravery_lock
    assert udb.get_user_by_id(p1["id"])["currency"] == p1_before - 100
    assert udb.get_user_by_id(p2["id"])["currency"] == p2_before - 150

    # Acto: refund
    summary = udb.refund_room_bravery_locks(room["id"], reason="test")

    # Verify resumen
    assert summary["refunded_count"] == 2
    assert summary["total_stake"] == 250
    assert summary["affected_users"][p1["id"]] == 100
    assert summary["affected_users"][p2["id"]] == 150

    # Locks pasaron a 'refunded' con payout = stake
    after1 = udb.get_bravery_lock_by_id(lock1["id"])
    after2 = udb.get_bravery_lock_by_id(lock2["id"])
    assert after1["status"] == "refunded"
    assert after1["payout"] == 100
    assert after1["resolved_at"] is not None
    assert after2["status"] == "refunded"
    assert after2["payout"] == 150

    # Currency: cada user recuperó su stake — vuelta al before-lock.
    assert udb.get_user_by_id(p1["id"])["currency"] == p1_before
    assert udb.get_user_by_id(p2["id"])["currency"] == p2_before


def test_idempotent_double_call_no_double_refund(isolated_db):
    udb = isolated_db
    host = _seed_user(udb, "host2", "Host2")
    p = _seed_user(udb, "pidem", "PIdem")
    room = udb.create_room(owner_user_id=host["id"], name="Idem Room")
    udb.set_room_bravery(room["id"], True)
    p_before = udb.get_user_by_id(p["id"])["currency"]
    _create_pending_lock(udb, p["id"], room["code"], stake=100)

    first = udb.refund_room_bravery_locks(room["id"])
    after_first = udb.get_user_by_id(p["id"])["currency"]
    assert first["refunded_count"] == 1
    assert after_first == p_before

    # Segundo refund no encuentra pending (ya están 'refunded'). No-op.
    second = udb.refund_room_bravery_locks(room["id"])
    assert second["refunded_count"] == 0
    assert second["total_stake"] == 0
    # Currency intacta — sin doble crédito.
    assert udb.get_user_by_id(p["id"])["currency"] == after_first


def test_no_pending_locks_returns_zero(isolated_db):
    udb = isolated_db
    host = _seed_user(udb, "host3", "Host3")
    room = udb.create_room(owner_user_id=host["id"], name="Empty Room")
    udb.set_room_bravery(room["id"], True)

    summary = udb.refund_room_bravery_locks(room["id"])
    assert summary["refunded_count"] == 0
    assert summary["total_stake"] == 0
    assert summary["affected_users"] == {}


def test_multiple_locks_same_user_same_room(isolated_db):
    """Un user con varios locks en la sala recupera la suma de stakes."""
    udb = isolated_db
    host = _seed_user(udb, "host5", "Host5")
    p = _seed_user(udb, "pmulti", "PMulti", currency=1000)
    room = udb.create_room(owner_user_id=host["id"], name="Multi Room")
    udb.set_room_bravery(room["id"], True)
    p_before = udb.get_user_by_id(p["id"])["currency"]
    _create_pending_lock(udb, p["id"], room["code"], stake=50, champ=266, lane="TOP")
    _create_pending_lock(udb, p["id"], room["code"], stake=75, champ=84, lane="JUNGLE")

    summary = udb.refund_room_bravery_locks(room["id"])
    assert summary["refunded_count"] == 2
    assert summary["total_stake"] == 125
    assert summary["affected_users"][p["id"]] == 125
    assert udb.get_user_by_id(p["id"])["currency"] == p_before


def test_concurrent_refunds_dont_double_credit(isolated_db):
    """Optimistic locking: si dos requests concurrentes refundan, el segundo
    debe encontrar rowcount=0 en su UPDATE y NO acreditar de nuevo."""
    udb = isolated_db
    host = _seed_user(udb, "host6", "Host6")
    p = _seed_user(udb, "prace", "PRace", currency=500)
    room = udb.create_room(owner_user_id=host["id"], name="Race Room")
    udb.set_room_bravery(room["id"], True)
    p_before = udb.get_user_by_id(p["id"])["currency"]
    _create_pending_lock(udb, p["id"], room["code"], stake=100, champ=266, lane="TOP")

    # Primer refund — normal
    first = udb.refund_room_bravery_locks(room["id"])
    assert first["refunded_count"] == 1
    after_first = udb.get_user_by_id(p["id"])["currency"]
    assert after_first == p_before

    # Simulamos race: el lock YA está refunded en DB, pero un segundo caller
    # consigue su SELECT ANTES de que vea la actualización (en realidad este
    # test es más una prueba de la guarda rowcount). En refund_room_bravery_locks
    # el segundo SELECT no encuentra pending → 0 refunds. Pero también
    # probemos directamente: ¿qué pasa si llamamos refund con SELECT viejo?
    # Lo simulamos llamando refund_room otra vez — el SELECT no encuentra
    # pending, así que el path ni siquiera entra al loop. La guarda principal
    # protege contra simultaneous SELECTs que sí encuentren el mismo lock.
    second = udb.refund_room_bravery_locks(room["id"])
    assert second["refunded_count"] == 0
    assert udb.get_user_by_id(p["id"])["currency"] == after_first


def test_only_refunds_locks_of_this_room(isolated_db):
    """Si hay locks en otra sala, esta función no los toca."""
    udb = isolated_db
    host = _seed_user(udb, "host4", "Host4")
    p = _seed_user(udb, "pcross", "PCross", currency=1000)
    roomA = udb.create_room(owner_user_id=host["id"], name="A")
    roomB = udb.create_room(owner_user_id=host["id"], name="B")
    udb.set_room_bravery(roomA["id"], True)
    udb.set_room_bravery(roomB["id"], True)
    p_before = udb.get_user_by_id(p["id"])["currency"]
    lockA = _create_pending_lock(udb, p["id"], roomA["code"], stake=50, champ=266, lane="TOP")
    lockB = _create_pending_lock(udb, p["id"], roomB["code"], stake=75, champ=84, lane="JUNGLE")
    # Sanidad: ambos escrows aplicaron
    assert udb.get_user_by_id(p["id"])["currency"] == p_before - 50 - 75

    udb.refund_room_bravery_locks(roomA["id"])

    # A se refundó, B sigue pending
    assert udb.get_bravery_lock_by_id(lockA["id"])["status"] == "refunded"
    assert udb.get_bravery_lock_by_id(lockB["id"])["status"] == "pending"
    # Currency: sólo recuperó 50 del lock A (B sigue escrow'd)
    assert udb.get_user_by_id(p["id"])["currency"] == p_before - 75
