"""Stock figures for items and batches, computed in SQL.

This is the only place that knows how stock is counted: a batch's available quantity is
what it holds, minus what is lent out, minus what projects have used. Lists filter, count
and display from these expressions; single objects read them through Item.stock and
ItemBatch.stock.
"""
from collections import namedtuple

from models import db, Item, ItemBatch, BatchSerialNumber, BatchLendRecord, ProjectBOMItem

func = db.func


def _batch_stock():
    """One row per batch: its item, quantity, lent and used quantities, availability and worth."""
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
    price = func.coalesce(ItemBatch.price_per_unit, 0.0)
    used = func.coalesce(used_in_projects.c.qty, 0)
    lent = db.case((func.coalesce(ItemBatch.sn_tracking_enabled, False) == db.true(), func.coalesce(lent_serials.c.qty, 0)),
                   else_=func.coalesce(lent_records.c.qty, 0))
    return (
        db.select(
            ItemBatch.id.label('batch_id'),
            ItemBatch.item_id.label('item_id'),
            quantity.label('quantity'),
            lent.label('lent'),
            used.label('used'),
            (quantity - lent - used).label('available'),
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
    """One row per item that has batches, summing its batches' figures."""
    batch = _batch_stock()
    return (
        db.select(
            batch.c.item_id,
            func.sum(batch.c.quantity).label('overall'),
            func.sum(batch.c.lent).label('lent'),
            func.sum(batch.c.used).label('used'),
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
        self.lent = func.coalesce(stock.c.lent, 0)
        self.used = func.coalesce(stock.c.used, 0)
        self.available = func.coalesce(stock.c.available, 0)
        self.value = func.coalesce(stock.c.value, 0.0)
        self.display_price = func.coalesce(stock.c.display_price, 0.0)
        self.average_price = db.case((self.overall == 0, 0.0), else_=self.value * 1.0 / self.overall)
        self.is_no_stock = db.and_(self.available <= 0, func.coalesce(Item.no_stock_warning, False) == db.true())
        self.is_low_stock = db.and_(self.available < func.coalesce(Item.min_quantity, 0), db.not_(self.is_no_stock))
        self.status = db.case((self.is_no_stock, 'no'), (self.is_low_stock, 'low'), else_='ok')

    def join(self, query):
        return query.outerjoin(self.stock, self.stock.c.item_id == Item.id)


class ItemStock(namedtuple('ItemStock', 'overall_quantity lend_quantity project_used_quantity available_quantity '
                                        'total_value total_price average_price status')):
    """Stock figures for one item across all its batches.

    total_value is what the stock on hand is worth; total_price is the display figure in
    which an empty batch counts as one unit. status is 'ok', 'low' or 'no'.
    """
    __slots__ = ()

    @property
    def is_no_stock(self):
        return self.status == 'no'

    @property
    def is_low_stock(self):
        return self.status == 'low'


BatchStock = namedtuple('BatchStock', 'quantity lend_quantity project_used_quantity available_quantity '
                                      'total_value total_price')


def _ids(rows):
    """Primary keys of the given objects, flushing first so new ones have theirs."""
    if any(row.id is None for row in rows):
        db.session.flush()
    return [row.id for row in rows]


def stock_for_items(items):
    """{item.id: ItemStock} for the given items, in one query."""
    ids = _ids(items)
    if not ids:
        return {}
    cols = StockColumns(item_stock_subquery())
    rows = db.session.execute(
        cols.join(db.select(Item.id, cols.overall, cols.lent, cols.used, cols.available, cols.value,
                            cols.display_price, cols.average_price, cols.status))
        .where(Item.id.in_(ids))
    )
    return {
        item_id: ItemStock(int(overall), int(lent), int(used), int(available),
                           float(value), float(display_price), float(average_price), status)
        for item_id, overall, lent, used, available, value, display_price, average_price, status in rows
    }


def stock_for_batches(batches):
    """{batch.id: BatchStock} for the given batches, in one query."""
    ids = _ids(batches)
    if not ids:
        return {}
    batch = _batch_stock()
    rows = db.session.execute(
        db.select(batch.c.batch_id, batch.c.quantity, batch.c.lent, batch.c.used, batch.c.available,
                  batch.c.value, batch.c.display_price)
        .where(batch.c.batch_id.in_(ids))
    )
    return {
        batch_id: BatchStock(int(quantity), int(lent), int(used), int(available), float(value), float(display_price))
        for batch_id, quantity, lent, used, available, value, display_price in rows
    }


def items_needing_restock():
    """Items that are low on stock or out of stock, lowest overall quantity first, with their stock."""
    cols = StockColumns(item_stock_subquery())
    items = (cols.join(Item.query).filter(cols.status.in_(('low', 'no')))
             .order_by(cols.overall, Item.id).all())
    return items, stock_for_items(items)


def stock_summary():
    """(total items, low stock items, no stock items) across the whole inventory."""
    cols = StockColumns(item_stock_subquery())
    total, low, no = db.session.execute(
        cols.join(db.select(func.count(Item.id),
                            func.coalesce(func.sum(db.case((cols.is_low_stock, 1), else_=0)), 0),
                            func.coalesce(func.sum(db.case((cols.is_no_stock, 1), else_=0)), 0)))
    ).one()
    return total, low, no
