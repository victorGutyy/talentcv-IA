import sqlite3

import pytest

from app.core.db import migrate


def test_migrar_bd_nueva_no_hace_copia(settings):
    assert migrate(settings) is None
    assert settings.db_path.exists()


def test_migrar_dos_veces_es_idempotente(settings):
    migrate(settings)
    assert migrate(settings) is None  # ya esta en head: sin copia
    assert not settings.backups_dir.exists()


def test_copia_antes_de_migrar_si_la_bd_no_esta_en_head(settings):
    settings.data_dir.mkdir(parents=True)
    con = sqlite3.connect(settings.db_path)
    con.execute("CREATE TABLE previa (x INTEGER)")
    con.execute("INSERT INTO previa VALUES (42)")
    con.commit()
    con.close()

    copia = migrate(settings)
    assert copia is not None and copia.exists()
    # la copia conserva el estado anterior; la BD ya tiene el esquema nuevo
    c1 = sqlite3.connect(copia)
    assert c1.execute("SELECT x FROM previa").fetchone()[0] == 42
    assert not c1.execute("SELECT name FROM sqlite_master WHERE name='profiles'").fetchone()
    c1.close()
    c2 = sqlite3.connect(settings.db_path)
    assert c2.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0001"
    assert c2.execute("SELECT x FROM previa").fetchone()[0] == 42
    c2.close()


def test_si_la_migracion_falla_se_restaura_la_copia(settings, monkeypatch):
    settings.data_dir.mkdir(parents=True)
    con = sqlite3.connect(settings.db_path)
    con.execute("CREATE TABLE previa (x INTEGER)")
    con.commit()
    con.close()

    def falla(cfg, rev):
        # simula una migracion que modifica la BD y luego se rompe
        c = sqlite3.connect(settings.db_path)
        c.execute("CREATE TABLE basura (y INTEGER)")
        c.commit()
        c.close()
        raise RuntimeError("fallo simulado")

    monkeypatch.setattr("app.core.db.command.upgrade", falla)
    with pytest.raises(RuntimeError):
        migrate(settings)
    c = sqlite3.connect(settings.db_path)
    assert not c.execute("SELECT name FROM sqlite_master WHERE name='basura'").fetchone()
    assert c.execute("SELECT name FROM sqlite_master WHERE name='previa'").fetchone()
    c.close()
