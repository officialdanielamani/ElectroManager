import os

import pytest
import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from db_migrate import current_revision, head_revision, upgrade_database
from models import db


@pytest.fixture
def engine(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'scratch.db'}")
    yield engine
    engine.dispose()


def _columns(engine, table):
    return {c['name'] for c in sa.inspect(engine).get_columns(table)}


def _make_legacy(engine):
    """Turn a baseline database into what the pre-Alembic startup code would have left behind."""
    upgrade_database(engine, '0001_baseline')
    with engine.begin() as conn:
        conn.execute(sa.text('DROP TABLE alembic_version'))
        conn.execute(sa.text('DROP TABLE plugins'))
        conn.execute(sa.text('ALTER TABLE users DROP COLUMN mfa_enabled'))
        conn.execute(sa.text('ALTER TABLE kanban_cards DROP COLUMN card_icon'))
        conn.execute(sa.text("INSERT INTO roles (id, name, permissions) VALUES (1, 'Admin', '{}')"))
        conn.execute(sa.text(
            "INSERT INTO users (id, username, email, password_hash, role_id, user_uid) "
            "VALUES (1, 'old', 'old@example.com', 'x', 1, NULL)"))
        conn.execute(sa.text("INSERT INTO tags (id, name) VALUES (1, 'IR'), (2, 'SMD')"))
        conn.execute(sa.text(
            "INSERT INTO items (id, uuid, name, tags) VALUES "
            "(1, 'AAAAAAAAAAAI', 'tagged', '[1, 2, 99]'), (2, 'BBBBBBBBBBBI', 'untagged', NULL), "
            "(3, 'CCCCCCCCCCCI', 'broken', 'not json')"))
        conn.execute(sa.text(
            "INSERT INTO sticker_templates (id, name, template_type, width_mm, height_mm, layout, owner_id) "
            "VALUES (1, 'ownerless', 'item', 50, 30, '{}', NULL)"))


def test_new_database_matches_models(engine):
    assert upgrade_database(engine) is True
    assert current_revision(engine) == head_revision()
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), db.metadata)
    assert diff == [], 'models.py changed without a migration: run `alembic revision --autogenerate`'


def test_upgrade_is_a_no_op_when_current(engine):
    upgrade_database(engine)
    assert upgrade_database(engine) is False


def test_app_database_is_at_head(app):
    with app.app_context():
        assert current_revision(db.engine) == head_revision()


def test_legacy_database_is_adopted(engine):
    _make_legacy(engine)

    assert upgrade_database(engine) is True

    assert current_revision(engine) == head_revision()
    assert 'plugins' in sa.inspect(engine).get_table_names()
    assert 'mfa_enabled' in _columns(engine, 'users')
    assert 'card_icon' in _columns(engine, 'kanban_cards')
    with engine.connect() as conn:
        uid = conn.execute(sa.text('SELECT user_uid FROM users WHERE id = 1')).scalar()
        assert uid and uid.startswith('U') and len(uid) == 6
        assert conn.execute(sa.text('SELECT count(*) FROM sticker_templates')).scalar() == 0
        assert conn.execute(sa.text('SELECT count(*) FROM items')).scalar() == 3


def test_item_tags_move_from_json_to_table(engine):
    _make_legacy(engine)
    upgrade_database(engine)
    assert 'tags' not in _columns(engine, 'items')
    with engine.connect() as conn:
        links = conn.execute(sa.text('SELECT item_id, tag_id FROM item_tags ORDER BY 1, 2')).fetchall()
    assert [tuple(row) for row in links] == [(1, 1), (1, 2)], 'unknown tag ids and bad JSON are dropped'


def test_item_tags_downgrade_restores_json(engine):
    from alembic import command
    from db_migrate import _config
    _make_legacy(engine)
    upgrade_database(engine)
    config = _config()
    with engine.connect() as conn:
        config.attributes['connection'] = conn
        command.downgrade(config, '0001_baseline')
        conn.commit()
    with engine.connect() as conn:
        assert conn.execute(sa.text('SELECT tags FROM items WHERE id = 1')).scalar() == '[1, 2]'
        assert conn.execute(sa.text('SELECT tags FROM items WHERE id = 2')).scalar() is None
    assert 'item_tags' not in sa.inspect(engine).get_table_names()


def test_existing_database_is_backed_up_before_upgrade(engine):
    _make_legacy(engine)
    upgrade_database(engine)
    backups = [f for f in os.listdir(os.path.dirname(engine.url.database)) if f.endswith('.bak')]
    assert backups == ['scratch.db.before-migrations.bak']
