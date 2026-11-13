"""Bring the database schema up to date with Alembic.

Schema changes live in migrations/versions. To add one, change models.py, then run
`alembic revision --autogenerate -m "what changed"` and review the generated file.
"""
import logging
import os
import shutil

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'migrations')


def _config():
    config = Config()
    config.set_main_option('script_location', MIGRATIONS_DIR)
    return config


def head_revision():
    return ScriptDirectory.from_config(_config()).get_current_head()


def current_revision(engine):
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def _backup_sqlite_file(engine, revision):
    """Copy the database file aside before changing a database that already holds data."""
    path = engine.url.database
    if engine.dialect.name != 'sqlite' or not path or path == ':memory:' or not os.path.isfile(path):
        return None
    if os.path.getsize(path) == 0:
        return None
    backup_path = f'{path}.before-{revision or "migrations"}.bak'
    shutil.copy2(path, backup_path)
    return backup_path


def upgrade_database(engine, revision='head'):
    """Apply pending migrations up to `revision`. Returns True when the schema changed."""
    head = head_revision()
    current = current_revision(engine)
    if current == head:
        return False

    backup_path = _backup_sqlite_file(engine, current)
    if backup_path:
        logger.info('Database backed up to %s before upgrading', backup_path)

    config = _config()
    with engine.connect() as connection:
        config.attributes['connection'] = connection
        command.upgrade(config, revision)
        connection.commit()
    logger.info('Database upgraded from %s to %s', current or 'no revision', revision)
    return True
