"""The SQL stock figures must agree with the per-object methods on Item, which other pages still use."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import event

from conftest import item_names
from item_stock import stock_for_items, stock_summary
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


def test_sql_stock_matches_model_methods(app, varied_stock):
    with app.app_context():
        items = Item.query.all()
        stock = stock_for_items(items)
        assert len(stock) == len(items) == 8
        for item in items:
            figures = stock[item.id]
            assert figures.overall_quantity == item.get_overall_quantity(), item.name
            assert figures.available_quantity == item.get_available_quantity(), item.name
            assert figures.total_value == pytest.approx(item.get_total_value()), item.name
            assert figures.total_price == pytest.approx(item.get_total_price()), item.name
            assert figures.average_price == pytest.approx(item.get_average_price()), item.name
            assert figures.is_no_stock == item.is_no_stock(), item.name
            assert figures.is_low_stock == item.is_low_stock(), item.name


def test_expected_availability(app, varied_stock):
    with app.app_context():
        stock = {item.name: stock_for_items([item])[item.id] for item in Item.query.all()}
    assert stock['partly lent'].available_quantity == 7
    assert stock['serial tracked'].available_quantity == 2
    assert stock['used in project'].available_quantity == 0
    assert stock['plain'].total_price == pytest.approx(23.0)
    assert {name: s.status for name, s in stock.items()} == {
        'plain': 'ok', 'no batches': 'no', 'no batches, warning off': 'ok', 'free of charge': 'ok',
        'partly lent': 'low', 'serial tracked': 'ok', 'used in project': 'no', 'all gone, warning off': 'low',
    }


def test_summary_matches_model_methods(app, varied_stock):
    with app.app_context():
        items = Item.query.all()
        expected = (len(items), sum(i.is_low_stock() for i in items), sum(i.is_no_stock() for i in items))
        assert stock_summary() == expected == (8, 2, 2)


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
