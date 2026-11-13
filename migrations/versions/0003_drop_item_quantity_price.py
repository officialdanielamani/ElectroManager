"""Drop the quantity and price cached on items; both are derived from batches.

Revision ID: 0003_drop_item_quantity_price
Revises: 0002_item_tags_table
"""
import sqlite3

import sqlalchemy as sa
from alembic import op

revision = '0003_drop_item_quantity_price'
down_revision = '0002_item_tags_table'
branch_labels = None
depends_on = None

COLUMNS = ('quantity', 'price')


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == 'sqlite' and sqlite3.sqlite_version_info >= (3, 35):
        # Native DROP COLUMN avoids rebuilding the whole items table.
        for column in COLUMNS:
            op.execute(f'ALTER TABLE items DROP COLUMN {column}')
    else:
        with op.batch_alter_table('items') as batch_op:
            for column in COLUMNS:
                batch_op.drop_column(column)


def downgrade():
    op.add_column('items', sa.Column('quantity', sa.Integer(), nullable=True))
    op.add_column('items', sa.Column('price', sa.Float(), nullable=True))
    op.execute("""
        UPDATE items SET
            quantity = COALESCE((SELECT SUM(COALESCE(b.quantity, 0)) FROM item_batches b WHERE b.item_id = items.id), 0),
            price = COALESCE((
                SELECT CASE WHEN SUM(COALESCE(b.quantity, 0)) > 0
                            THEN SUM(COALESCE(b.price_per_unit, 0.0) * COALESCE(b.quantity, 0)) * 1.0
                                 / SUM(COALESCE(b.quantity, 0))
                            ELSE 0.0 END
                FROM item_batches b WHERE b.item_id = items.id), 0.0)
    """)
