"""Store item tags in an association table instead of a JSON list on the item.

Revision ID: 0002_item_tags_table
Revises: 0001_baseline
"""
import json
import sqlite3

import sqlalchemy as sa
from alembic import op

revision = '0002_item_tags_table'
down_revision = '0001_baseline'
branch_labels = None
depends_on = None


def _drop_tags_column(bind):
    if bind.dialect.name == 'sqlite' and sqlite3.sqlite_version_info >= (3, 35):
        # Native DROP COLUMN avoids rebuilding the whole items table.
        op.execute('ALTER TABLE items DROP COLUMN tags')
    else:
        with op.batch_alter_table('items') as batch_op:
            batch_op.drop_column('tags')


def upgrade():
    bind = op.get_bind()
    item_tags = op.create_table(
        'item_tags',
        sa.Column('item_id', sa.Integer(), nullable=False),
        sa.Column('tag_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['item_id'], ['items.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('item_id', 'tag_id'),
    )
    op.create_index('ix_item_tags_tag_id', 'item_tags', ['tag_id'])

    known_tags = {row[0] for row in bind.execute(sa.text('SELECT id FROM tags'))}
    links = set()
    for item_id, raw in bind.execute(sa.text("SELECT id, tags FROM items WHERE tags IS NOT NULL AND tags != ''")):
        try:
            tag_ids = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(tag_ids, list):
            continue
        for tag_id in tag_ids:
            # Ids of tags deleted since the item was saved were left behind in the JSON.
            if str(tag_id).isdigit() and int(tag_id) in known_tags:
                links.add((item_id, int(tag_id)))
    if links:
        op.bulk_insert(item_tags, [{'item_id': i, 'tag_id': t} for i, t in sorted(links)])

    _drop_tags_column(bind)


def downgrade():
    bind = op.get_bind()
    op.add_column('items', sa.Column('tags', sa.Text(), nullable=True))
    by_item = {}
    for item_id, tag_id in bind.execute(sa.text('SELECT item_id, tag_id FROM item_tags ORDER BY item_id, tag_id')):
        by_item.setdefault(item_id, []).append(tag_id)
    for item_id, tag_ids in by_item.items():
        bind.execute(sa.text('UPDATE items SET tags = :tags WHERE id = :id'),
                     {'tags': json.dumps(tag_ids), 'id': item_id})
    op.drop_index('ix_item_tags_tag_id', table_name='item_tags')
    op.drop_table('item_tags')
