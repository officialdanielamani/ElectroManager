"""Stock figures come from one SQL engine (item_stock.py); these pin down what it counts."""
import re
from datetime import datetime, timezone

import pytest
from sqlalchemy import event

from conftest import item_names
from item_stock import stock_for_batches, stock_for_items, stock_summary
from models import (db, BatchLendRecord, BatchSerialNumber, Item, ItemBatch, Project, ProjectBOMItem)


@pytest.fixture
def varied_stock(app, make_user):
    """Items exercising every way stock can be reduced; returns their names."""
    user_id = make_user('stock-owner')
    with app.app_context():
        project = Project(name='Build', created_by=user_id, updated_by=user_id)
        db.session.add(project)
        db.session.flush()

        def item(name, min_quantity=0, no_stock_warning=True):
            row = Item(name=name, min_quantity=min_quantity, no_stock_warning=no_stock_warning)
            db.session.add(row)
            db.session.flush()
            return row

        def batch(row, number, quantity, price, tracked=False):
            b = ItemBatch(item_id=row.id, batch_number=number, quantity=quantity, price_per_unit=price,
                          sn_tracking_enabled=tracked)
            db.session.add(b)
            db.session.flush()
            return b

        plain = item('plain', min_quantity=5)
        batch(plain, 1, 10, 2.0)
        batch(plain, 2, 0, 3.0)                     # empty batch still shows its unit price

        item('no batches')
        item('no batches, warning off', no_stock_warning=False)

        free = item('free of charge', min_quantity=1)
        batch(free, 1, 4, None)

        lent = item('partly lent', min_quantity=8)
        b = batch(lent, 1, 10, 1.5)
        db.session.add(BatchLendRecord(batch_id=b.id, lend_to_id=1, quantity=3))
        db.session.add(BatchLendRecord(batch_id=b.id, lend_to_id=1, quantity=4,
                                       returned_at=datetime.now(timezone.utc)))   # returned: not counted

        tracked = item('serial tracked', min_quantity=2)
        b = batch(tracked, 1, 3, 9.0, tracked=True)
        db.session.add(BatchLendRecord(batch_id=b.id, lend_to_id=1, quantity=2))   # ignored for tracked batches
        for seq, (lend_to, deleted) in enumerate([(7, False), (7, True), (None, False)], start=1):
            db.session.add(BatchSerialNumber(batch_id=b.id, sequence_number=seq, internal_serial_number=f'SN-{seq}',
                                             lend_to_id=lend_to, is_deleted=deleted))

        used = item('used in project', min_quantity=1)
        b = batch(used, 1, 2, 4.0)
        db.session.add(ProjectBOMItem(project_id=project.id, item_id=used.id, batch_id=b.id, quantity=5, used_quantity=2))
        db.session.add(ProjectBOMItem(project_id=project.id, item_id=used.id, batch_id=b.id, quantity=5, used_quantity=0))

        all_gone = item('all gone, warning off', min_quantity=3, no_stock_warning=False)
        batch(all_gone, 1, 0, 1.0)

        db.session.commit()
        return [row.name for row in Item.query.all()]


def _stock_by_name(app):
    with app.app_context():
        items = Item.query.all()
        stock = stock_for_items(items)
        return {item.name: stock[item.id] for item in items}


def test_item_stock_figures(app, varied_stock):
    stock = _stock_by_name(app)
    assert len(stock) == 8

    plain = stock['plain']
    assert (plain.overall_quantity, plain.available_quantity) == (10, 10)
    assert plain.total_value == pytest.approx(20.0)
    assert plain.total_price == pytest.approx(23.0), 'an empty batch counts as one unit of display price'
    assert plain.average_price == pytest.approx(2.0)

    lent = stock['partly lent']
    assert (lent.overall_quantity, lent.lend_quantity, lent.available_quantity) == (10, 3, 7), \
        'returned lend records are not counted'

    tracked = stock['serial tracked']
    assert (tracked.lend_quantity, tracked.available_quantity) == (1, 2), \
        'tracked batches count lent serial numbers that are not deleted, and ignore lend records'

    used = stock['used in project']
    assert (used.project_used_quantity, used.available_quantity) == (2, 0)

    empty = stock['no batches']
    assert (empty.overall_quantity, empty.available_quantity, empty.total_value, empty.average_price) == (0, 0, 0.0, 0.0)
    assert stock['free of charge'].total_value == 0.0

    assert {name: s.status for name, s in stock.items()} == {
        'plain': 'ok', 'no batches': 'no', 'no batches, warning off': 'ok', 'free of charge': 'ok',
        'partly lent': 'low', 'serial tracked': 'ok', 'used in project': 'no', 'all gone, warning off': 'low',
    }
    assert stock['partly lent'].is_low_stock and not stock['partly lent'].is_no_stock
    assert stock['no batches'].is_no_stock and not stock['no batches'].is_low_stock


def test_batch_stock_figures(app, varied_stock):
    with app.app_context():
        plain = Item.query.filter_by(name='plain').one()
        by_number = {b.batch_number: s for b in plain.batches for s in [plain.batch_stock()[b.id]]}
        assert by_number[1] == (10, 0, 0, 10, 20.0, 20.0)
        assert by_number[2] == (0, 0, 0, 0, 0.0, 3.0)

        tracked = Item.query.filter_by(name='serial tracked').one().batches[0]
        assert tracked.stock == (3, 1, 0, 2, 27.0, 27.0)
        assert tracked.stock == stock_for_batches([tracked])[tracked.id]


def test_object_and_bulk_lookups_agree(app, varied_stock):
    with app.app_context():
        items = Item.query.all()
        bulk = stock_for_items(items)
        for item in items:
            assert item.stock == bulk[item.id]
            batch_stock = item.batch_stock()
            assert item.stock.available_quantity == sum(s.available_quantity for s in batch_stock.values())
            assert item.stock.lend_quantity == sum(s.lend_quantity for s in batch_stock.values())


def test_stock_sees_unsaved_changes(app, varied_stock):
    with app.app_context():
        item = Item(name='brand new')
        db.session.add(item)
        assert item.stock.overall_quantity == 0
        batch = ItemBatch(item_id=item.id, batch_number=1, quantity=6, price_per_unit=2.0)
        db.session.add(batch)
        assert batch.stock.available_quantity == 6
        db.session.add(BatchLendRecord(batch_id=batch.id, lend_to_id=1, quantity=4))
        assert batch.stock.available_quantity == 2
        item.recalculate_from_batches()
        assert (item.quantity, item.price) == (6, 2.0)
        db.session.rollback()


def test_summary_counts(app, varied_stock):
    with app.app_context():
        assert stock_summary() == (8, 2, 2)


def test_low_stock_page_lists_low_and_empty_items(admin_client, varied_stock):
    body = admin_client.get('/low-stock').get_data(as_text=True)
    listed = re.findall(r'<a href="/item/[^"]+">([^<]+)</a>', body)
    assert listed == ['no batches', 'all gone, warning off', 'used in project', 'partly lent'], \
        'lowest overall quantity first'


def test_reports_page_counters(admin_client, varied_stock):
    body = admin_client.get('/reports').get_data(as_text=True)
    assert '<div class="fs-3 fw-bold text-primary">8</div>' in body
    assert '<div class="fs-3 fw-bold text-warning">2</div>' in body
    assert '<div class="fs-3 fw-bold text-danger">2</div>' in body


def test_item_pages_show_stock(app, admin_client, varied_stock):
    with app.app_context():
        uuid = Item.query.filter_by(name='partly lent').one().uuid
    detail = admin_client.get(f'/item/{uuid}').get_data(as_text=True)
    assert '<h3 class="text-success">7</h3>' in detail and 'Low Stock' in detail
    for path in (f'/item/{uuid}/edit', f'/item/{uuid}/print'):
        assert admin_client.get(path).status_code == 200


def test_batch_transfer_is_limited_to_available_quantity(app, admin_client, varied_stock):
    with app.app_context():
        item = Item.query.filter_by(name='partly lent').one()
        target = ItemBatch(item_id=item.id, batch_number=2, quantity=0, price_per_unit=1.5)
        db.session.add(target)
        db.session.commit()
        uuid, source_id, target_id = item.uuid, item.batches[0].id, target.id

    def transfer(quantity):
        admin_client.post(f'/item/{uuid}/batch/transfer', data={
            'from_batch_id': source_id, 'to_batch_id': target_id, 'transfer_quantity': quantity})
        with app.app_context():
            return db.session.get(ItemBatch, source_id).quantity, db.session.get(ItemBatch, target_id).quantity

    assert transfer(8) == (10, 0), '3 of the 10 are lent out, so only 7 can move'
    assert transfer(7) == (3, 7)


def test_list_filters_use_the_same_figures(admin_client, varied_stock):
    def names(**params):
        return set(item_names(admin_client.get('/items', query_string=params)))
    assert names(status='low') == {'partly lent', 'all gone, warning off'}
    assert names(status='no') == {'no batches', 'used in project'}
    assert names(qty_min=7, qty_max=7) == {'partly lent'}
    assert names(qty_max=0) == {'no batches', 'no batches, warning off', 'used in project', 'all gone, warning off'}
    assert names(price_min=9) == {'serial tracked'}
    page = admin_client.get('/items').get_data(as_text=True)
    assert page.count('font-weight: 500;">2<') == 2   # the Low Stock and No Stock counters


def test_summary_on_empty_inventory(app):
    with app.app_context():
        assert stock_summary() == (0, 0, 0)
        assert stock_for_items([]) == {}


def test_list_query_count_does_not_grow_with_items(app, admin_client, make_item):
    def queries_for_list():
        seen = []
        with app.app_context():
            engine = db.engine
        listener = lambda *args: seen.append(1)
        event.listen(engine, 'before_cursor_execute', listener)
        try:
            assert admin_client.get('/items?per_page=100').status_code == 200
        finally:
            event.remove(engine, 'before_cursor_execute', listener)
        return len(seen)

    for n in range(3):
        make_item(f'First {n}')
    few = queries_for_list()
    for n in range(40):
        make_item(f'More {n}')
    assert queries_for_list() == few
