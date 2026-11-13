"""Alembic environment.

The application passes its own connection in (see db_migrate.py). When Alembic is
run from the command line instead, the app is imported and its engine is used.
"""
from alembic import context

from models import db

config = context.config


def run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=db.metadata,
        render_as_batch=connection.dialect.name == 'sqlite',
    )
    with context.begin_transaction():
        context.run_migrations()


connection = config.attributes.get('connection')
if connection is not None:
    run_migrations(connection)
else:
    from app import app
    with app.app_context():
        with db.engine.connect() as cli_connection:
            run_migrations(cli_connection)
            cli_connection.commit()
