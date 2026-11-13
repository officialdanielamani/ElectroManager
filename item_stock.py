"""Stock figures for items, computed in SQL.

Mirrors the per-object methods on Item/ItemBatch (get_available_quantity, is_low_stock, ...)
so that lists can filter, count and display stock without loading every batch.
"""
from collections import namedtuple

from models import db, Item, ItemBatch, BatchSerialNumber, BatchLendRecord, ProjectBOMItem

func = db.func


def _batch_stock():
    """One row per batch: its item, quantity, price and available quantity."""
    lent_serials = (
        db.select(BatchSerialNumber.batch_id.label('batch_id'), func.count().label('qty'))
        .where(func.coalesce(BatchSerialNumber.lend_to_id, 0) != 0,
               func.coalesce(BatchSerialNumber.is_deleted, False) == db.false())
        .group_by(BatchSerialNumber.batch_id).subquery()
    )
    lent_records = (
        db.select(BatchLendRecord.batch_id.label('batch_id'),
                  func.sum(func.coalesce(BatchLendRecord.quantity, 0)).label('qty'))
        .where(BatchLendRecord.returned_at.is_(None))
        .group_by(BatchLendRecord.batch_id).subquery()
    )
    used_in_projects = (
        db.select(ProjectBOMItem.batch_id.label('batch_id'), func.sum(ProjectBOMItem.used_quantity).label('qty'))
        .where(ProjectBOMItem.used_quantity > 0)
        .group_by(ProjectBOMItem.batch_id).subquery()
    )
    quantity = func.coalesce(ItemBatch.quantity, 0)
    price = func.coalesce(ItemBatch.price_per_unit, 0)
    lent = db.case((func.coalesce(ItemBatch.sn_tracking_enabled, False) == db.true(), func.coalesce(lent_serials.c.qty, 0)),
                   else_=func.coalesce(lent_records.c.qty, 0))
    return (
        db.select(
            ItemBatch.item_id.label('item_id'),
            quantity.label('quantity'),
            (quantity - lent - func.coalesce(used_in_projects.c.qty, 0)).label('available'),
            (price * quantity).label('value'),
            # Display price counts an empty batch as one unit so its unit price stays visible.
            (price * db.case((quantity < 1, 1), else_=quantity)).label('display_price'),
        )
        .outerjoin(lent_serials, lent_serials.c.batch_id == ItemBatch.id)
        .outerjoin(lent_records, lent_records.c.batch_id == ItemBatch.id)
        .outerjoin(used_in_projects, used_in_projects.c.batch_id == ItemBatch.id)
        .subquery()
    )


def item_stock_subquery():
    """One row per item that has batches: item_id, overall, available, value, display_price."""
    batch = _batch_stock()
    return (
        db.select(
            batch.c.item_id,
            func.sum(batch.c.quantity).label('overall'),
            func.sum(batch.c.available).label('available'),
            func.sum(batch.c.value).label('value'),
            func.sum(batch.c.display_price).label('display_price'),
        )
        .group_by(batch.c.item_id).subquery()
    )


class StockColumns:
    """SQL expressions over Item joined to item_stock_subquery(); items without batches count as zero."""

    def __init__(self, stock):
        self.stock = stock
        self.overall = func.coalesce(stock.c.overall, 0)
        self.available = func.coalesce(stock.c.available, 0)
        self.value = func.coalesce(stock.c.value, 0.0)
        self.display_price = func.coalesce(stock.c.display_price, 0.0)
        self.average_price = db.case((self.overall == 0, 0.0), else_=self.value * 1.0 / self.overall)
        self.is_no_stock = db.and_(self.available <= 0, func.coalesce(Item.no_stock_warning, False) == db.true())
        self.is_low_stock = db.and_(self.available < func.coalesce(Item.min_quantity, 0), db.not_(self.is_no_stock))
        self.status = db.case((self.is_no_stock, 'no'), (self.is_low_stock, 'low'), else_='ok')

    def join(self, query):
        return query.outerjoin(self.stock, self.stock.c.item_id == Item.id)


class ItemStock(namedtuple('ItemStock', 'overall_quantity available_quantity total_value total_price '
                                        'average_price status')):
    """Stock figures for one item, as shown in item lists."""
    __slots__ = ()

    @property
    def is_no_stock(self):
        return self.status == 'no'

    @property
    def is_low_stock(self):
        return self.status == 'low'


def stock_for_items(items):
    """{item.id: ItemStock} for the given items, in one query."""
    ids = [item.id for item in items]
    if not ids:
        return {}
    cols = StockColumns(item_stock_subquery())
    rows = db.session.execute(
        cols.join(db.select(Item.id, cols.overall, cols.available, cols.value, cols.display_price,
                            cols.average_price, cols.status))
        .where(Item.id.in_(ids))
    )
    return {row[0]: ItemStock(*row[1:]) for row in rows}


def stock_summary():
    """(total items, low stock items, no stock items) across the whole inventory."""
    cols = StockColumns(item_stock_subquery())
    total, low, no = db.session.execute(
        cols.join(db.select(func.count(Item.id),
                            func.coalesce(func.sum(db.case((cols.is_low_stock, 1), else_=0)), 0),
                            func.coalesce(func.sum(db.case((cols.is_no_stock, 1), else_=0)), 0)))
    ).one()
    return total, low, no
