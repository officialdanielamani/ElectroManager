import json

import pytest

from conftest import item_names, mp
from models import (db, Category, Footprint, Item, ItemBatch, ItemParameter, ItemParameterStringValue,
                    MagicParameter, ParameterStringOption, ParameterUnit, Tag)

ORIGINS = ['China', 'Vietnam', 'Malaysia', 'Japan']


@pytest.fixture
def catalog(app):
    """A small inventory; returns ids keyed by name for categories, tags, footprints and parameters."""
    ids = {}
    with app.app_context():
        for kind, model, names in (('cat', Category, ['Sensor', 'Resistor', 'MCU']),
                                   ('tag', Tag, ['IR', 'Distance', 'PIR', 'SMD']),
                                   ('fp', Footprint, ['0805', 'TO-92'])):
            for name in names:
                row = model(name=name)
                db.session.add(row)
                db.session.flush()
                ids[f'{kind}:{name}'] = row.id

        volt = MagicParameter(name='Operating Voltage', param_type='number', is_whole_number=False)
        size = MagicParameter(name='Size', param_type='number', is_whole_number=False)
        origin = MagicParameter(name='Origin Country', param_type='string', string_select_max=-1)
        due = MagicParameter(name='Calibration Due', param_type='date')
        db.session.add_all([volt, size, origin, due])
        db.session.flush()
        ids.update(volt=volt.id, size=size.id, origin=origin.id, due=due.id)
        db.session.add_all([ParameterUnit(parameter_id=volt.id, unit=u) for u in ('mV', 'V')])
        db.session.add_all([ParameterUnit(parameter_id=size.id, unit=u) for u in ('mm', 'cm')])
        db.session.add_all([ParameterStringOption(parameter_id=origin.id, value=v) for v in ORIGINS])

        def add(name, cat, tags, fp, qty, price, sku, model, short, params):
            item = Item(name=name, category_id=ids[f'cat:{cat}'], sku=sku, info=model, short_info=short,
                        footprint_id=ids.get(f'fp:{fp}'), min_quantity=3,
                        tags=json.dumps([ids[f'tag:{t}'] for t in tags]))
            db.session.add(item)
            db.session.flush()
            db.session.add(ItemBatch(item_id=item.id, batch_number=1, quantity=qty, price_per_unit=price))
            for param_id, operation, value, value2, unit, strings in params:
                row = ItemParameter(item_id=item.id, parameter_id=param_id, operation=operation,
                                    value=value, value2=value2, unit=unit)
                db.session.add(row)
                db.session.flush()
                for text in strings or []:
                    db.session.add(ItemParameterStringValue(item_parameter_id=row.id, value=text,
                                                            is_custom=text not in ORIGINS))
            db.session.flush()
            item.recalculate_from_batches()

        add('PIR', 'Sensor', ['PIR', 'IR'], None, 12, 1.5, 'SEN-001', 'HC-SR501', 'motion sensor',
            [(volt.id, 'range', '4.5', '20', 'V', None), (origin.id, 'value', None, None, None, ['China'])])
        add('ToF', 'Sensor', ['Distance', 'IR'], None, 4, 3.2, 'SEN-002', 'VL53L0X', 'laser distance',
            [(volt.id, 'range', '2.6', '3.5', 'V', None), (size.id, 'value', '4.4', None, 'mm', None),
             (origin.id, 'value', None, None, None, ['Malaysia', 'Thailand'])])
        add('Sharp', 'Sensor', ['Distance', 'IR'], None, 8, 9.9, 'SEN-003', 'GP2Y0A21', 'analog distance',
            [(volt.id, 'value', '5', None, 'V', None), (size.id, 'value', '4.5', None, 'cm', None),
             (origin.id, 'value', None, None, None, ['Japan']), (due.id, 'value', '2026-12-01', None, None, None)])
        add('TMP36', 'Sensor', [], 'TO-92', 0, 0.8, 'SEN-004', 'TMP36', 'temperature',
            [(volt.id, 'range', '2700', '5500', 'mV', None), (origin.id, 'value', None, None, None, ['Vietnam'])])
        add('10k', 'Resistor', ['SMD'], '0805', 500, 0.01, 'RES-10K', '10k 1%', '100% precise_ish',
            [(size.id, 'value', '2', None, 'mm', None)])
        add('ESP32', 'MCU', [], None, 2, 6.5, 'MCU-ESP32', 'ESP32-WROOM', 'wifi mcu',
            [(volt.id, 'max', '3.6', None, 'V', None), (origin.id, 'value', None, None, None, ['China'])])
        db.session.commit()
    return ids


@pytest.fixture
def search(admin_client, catalog):
    def _search(**params):
        response = admin_client.get('/items', query_string={'per_page': 100, **params})
        assert response.status_code == 200
        return set(item_names(response))
    _search.ids = catalog
    return _search


def test_no_filters_lists_everything(search):
    assert search() == {'PIR', 'ToF', 'Sharp', 'TMP36', '10k', 'ESP32'}


def test_quick_search_and_single_category(search):
    assert search(search='esp') == {'ESP32'}
    assert search(search='uuid:nope') == set()
    assert len(search(category=search.ids['cat:Sensor'])) == 4


def test_text_fields(search):
    assert search(name='sha') == {'Sharp'}
    assert search(sku='sen-00') == {'PIR', 'ToF', 'Sharp', 'TMP36'}
    assert search(model='wroom') == {'ESP32'}
    assert search(short_info='distance') == {'ToF', 'Sharp'}
    assert len(search(uuid='I')) == 6


def test_like_wildcards_are_literal(search):
    assert search(short_info='100%') == {'10k'}
    assert search(short_info='precise_') == {'10k'}
    assert search(name='%') == set()


def test_multiple_categories_and_footprints(search):
    ids = search.ids
    assert search(cat=[ids['cat:Resistor'], ids['cat:MCU']]) == {'10k', 'ESP32'}
    assert search(fp=[ids['fp:0805'], ids['fp:TO-92']]) == {'10k', 'TMP36'}


def test_tags_any_and_all(search):
    ids = search.ids
    assert search(tag=[ids['tag:PIR'], ids['tag:Distance']]) == {'PIR', 'ToF', 'Sharp'}
    assert search(tag=[ids['tag:IR'], ids['tag:Distance']], tag_mode='all') == {'ToF', 'Sharp'}
    assert search(tag=[ids['tag:PIR'], ids['tag:SMD']], tag_mode='all') == set()


def test_available_quantity_and_price_ranges(search):
    assert search(qty_min=5) == {'PIR', 'Sharp', '10k'}
    assert search(qty_min=2, qty_max=8) == {'ToF', 'Sharp', 'ESP32'}
    assert search(price_min=3, price_max=10) == {'ToF', 'Sharp', 'ESP32'}
    assert search(qty_min='abc') == search()


def test_status(search):
    assert search(status='no') == {'TMP36'}
    assert search(status='low') == {'ESP32'}
    assert search(status='ok,no') == {'PIR', 'ToF', 'Sharp', '10k', 'TMP36'}
    assert search(status=['low', 'no']) == {'ESP32', 'TMP36'}


def test_number_parameter_respects_unit_and_overlap(search):
    volt = search.ids['volt']
    in_volts = mp({'id': volt, 'units': ['V'], 'op': 'range', 'min': 3.2, 'max': 5.5})
    assert search(mp=in_volts) == {'PIR', 'ToF', 'Sharp', 'ESP32'}
    assert search(mp=mp({'id': volt, 'units': ['mV'], 'op': 'max', 'max': 500})) == set()
    assert search(mp=mp({'id': volt, 'units': ['mV'], 'op': 'range', 'min': 3000, 'max': 4000})) == {'TMP36'}
    assert search(mp=mp({'id': volt, 'op': 'eq', 'min': 5})) == {'PIR', 'Sharp'}
    assert search(mp=mp({'id': volt, 'units': ['V'], 'op': 'min', 'min': 10})) == {'PIR'}


def test_parameter_without_criteria_means_has_parameter(search):
    assert search(mp=mp({'id': search.ids['size']})) == {'ToF', 'Sharp', '10k'}


def test_string_parameter_any_and_all(search):
    origin = search.ids['origin']
    assert search(mp=mp({'id': origin, 'values': ['China', 'Vietnam', 'Malaysia']})) == {'PIR', 'ToF', 'TMP36', 'ESP32'}
    assert search(mp=mp({'id': origin, 'values': ['Malaysia', 'Thailand'], 'mode': 'all'})) == {'ToF'}
    assert search(mp=mp({'id': origin, 'values': ['Malaysia', 'Japan'], 'mode': 'all'})) == set()


def test_date_parameter_range(search):
    due = search.ids['due']
    assert search(mp=mp({'id': due, 'from': '2026-11-01', 'to': '2027-01-01'})) == {'Sharp'}
    assert search(mp=mp({'id': due, 'to': '2026-01-01'})) == set()


def test_parameters_combine_with_and_by_default(search):
    ids = search.ids
    both = mp({'id': ids['volt'], 'units': ['V'], 'op': 'range', 'min': 3.2, 'max': 5.5},
              {'id': ids['origin'], 'values': ['China', 'Japan']})
    assert search(mp=both, cat=ids['cat:Sensor']) == {'PIR', 'Sharp'}


def test_or_groups(search):
    ids = search.ids
    volt = {'id': ids['volt'], 'units': ['V'], 'op': 'range', 'min': 3.2, 'max': 5.5}
    size_mm = {'id': ids['size'], 'units': ['mm'], 'op': 'range', 'min': 2, 'max': 30}
    size_cm = {'id': ids['size'], 'units': ['cm'], 'op': 'range', 'min': 4, 'max': 5}
    # volt AND (mm OR cm)
    assert search(mp=mp(volt, size_mm, {**size_cm, 'join': 'or'})) == {'ToF', 'Sharp'}
    # (volt OR mm) AND cm
    assert search(mp=mp(volt, {**size_mm, 'join': 'or'}, size_cm)) == {'Sharp'}
    # a leading OR has nothing to join to
    assert search(mp=mp({**size_mm, 'join': 'or'})) == {'ToF', '10k'}


def test_malformed_parameter_filter_is_ignored(search):
    everything = search()
    assert search(mp='{bad json') == everything
    assert search(mp='[{"id": "x"}, 5, {"id": 99999}]') == everything
    assert search(mp='"string"') == everything


def test_filters_survive_pagination_and_show_as_chips(admin_client, catalog, make_item):
    for n in range(12):
        make_item(f'Filler {n:02d}', category_id=catalog['cat:Resistor'])
    query = {'cat': catalog['cat:Resistor'], 'per_page': 5}
    first = admin_client.get('/items', query_string=query)
    html = first.get_data(as_text=True)
    assert 'Category: Resistor' in html
    assert f"page=2&amp;cat={catalog['cat:Resistor']}" in html or 'page=2' in html
    pages = [set(item_names(admin_client.get('/items', query_string={**query, 'page': p}))) for p in (1, 2, 3)]
    assert [len(p) for p in pages] == [5, 5, 3]
    assert len(set().union(*pages)) == 13


def test_print_view_uses_the_same_filters(admin_client, catalog):
    body = admin_client.get('/items/print', query_string={'cat': catalog['cat:MCU']}).get_data(as_text=True)
    assert 'ESP32' in body and 'Sharp' not in body


def test_advanced_form_is_prefilled(admin_client, catalog):
    criteria = mp({'id': catalog['volt'], 'units': ['V'], 'op': 'max', 'max': 5})
    html = admin_client.get('/items/advanced-search',
                            query_string={'name': 'abc', 'cat': catalog['cat:Sensor'], 'mp': criteria}).get_data(as_text=True)
    assert 'value="abc"' in html
    assert f'name="cat" value="{catalog["cat:Sensor"]}" checked' in html
    assert '"op": "max"' in html and 'Thailand' in html


def test_viewer_cannot_filter_on_hidden_fields(app, catalog, make_user, login):
    from models import Role
    with app.app_context():
        role = Role.query.filter_by(name='Viewer').one()
        perms = role.get_permissions()
        perms.setdefault('items', {}).update(view=True, view_price=False, view_info=False)
        role.set_permissions(perms)
        db.session.commit()
    make_user('viewer', role='Viewer')
    client = login('viewer')
    everything = set(item_names(client.get('/items', query_string={'per_page': 100})))
    assert len(everything) == 6
    restricted = client.get('/items', query_string={'per_page': 100, 'price_min': 5, 'sku': 'SEN', 'cat': catalog['cat:MCU']})
    assert set(item_names(restricted)) == everything
    form = client.get('/items/advanced-search').get_data(as_text=True)
    assert 'name="price_min"' not in form and 'name="sku"' not in form
