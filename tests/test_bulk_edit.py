"""Bulk edit: short info / type-model overwrite; thumbnail from share files; share files and URLs append."""
import json

import pytest

from models import db, Item, Role, SharedFile


@pytest.fixture
def files(app):
    with app.app_context():
        rows = [SharedFile(name='photo', filename='photo.png', category='item'),
                SharedFile(name='sheet', filename='sheet.pdf', category='item'),
                SharedFile(name='chip', filename='chip.png', category='icon'),
                SharedFile(name='avatar', filename='avatar.png', category='profile')]
        db.session.add_all(rows)
        db.session.commit()
        return {r.name: r.id for r in rows}


@pytest.fixture
def two_items(app, make_item):
    first, second = make_item('First', short_info='keep me', info='OLD-1'), make_item('Second')
    with app.app_context():
        db.session.get(Item, first).datasheet_urls = json.dumps([{'url': 'https://a.example/1', 'title': 'A', 'info': ''}])
        db.session.get(Item, second).datasheet_urls = 'https://legacy.example/x\nhttps://legacy.example/y'
        db.session.commit()
    return [first, second]


def _edit(client, ids, **fields):
    return client.post('/items/bulk-edit', json={'item_ids': ids, **fields})


def _urls(raw):
    if not raw:
        return []
    try:
        return json.loads(raw)
    except json.JSONDecodeError:   # legacy newline-separated list
        return [{'url': u} for u in raw.splitlines()]


def _item(app, item_id):
    with app.app_context():
        item = db.session.get(Item, item_id)
        return {'short_info': item.short_info, 'info': item.info, 'thumbnail': item.thumbnail,
                'urls': _urls(item.datasheet_urls),
                'files': sorted(f.name for f in item.linked_share_files)}


def test_short_info_and_model_overwrite_and_blank_keeps(app, admin_client, two_items):
    assert _edit(admin_client, two_items, short_info='  New info ', info='MDL-2').status_code == 200
    assert [(_item(app, i)['short_info'], _item(app, i)['info']) for i in two_items] == [('New info', 'MDL-2')] * 2
    assert _edit(admin_client, two_items, short_info='', info='   ', min_quantity=3).status_code == 200
    assert _item(app, two_items[0])['short_info'] == 'New info'


def test_thumbnail_only_from_share_files(app, admin_client, two_items, files):
    assert _edit(admin_client, two_items, thumbnail='share:photo.png').status_code == 200
    assert _edit(admin_client, two_items[:1], thumbnail='icon:chip.png').status_code == 200
    assert [_item(app, i)['thumbnail'] for i in two_items] == ['icon:chip.png', 'share:photo.png']
    for bad in ('share:sheet.pdf', 'share:missing.png', 'profile:avatar.png', 'uploads/x.png', 'biicon:star'):
        assert _edit(admin_client, two_items, thumbnail=bad).status_code == 400, bad
    assert _item(app, two_items[1])['thumbnail'] == 'share:photo.png'


def test_share_files_are_added_not_replaced(app, admin_client, two_items, files):
    with app.app_context():
        db.session.get(Item, two_items[0]).linked_share_files = [db.session.get(SharedFile, files['photo'])]
        db.session.commit()
    assert _edit(admin_client, two_items, share_file_ids=[files['photo'], files['sheet']]).status_code == 200
    assert [_item(app, i)['files'] for i in two_items] == [['photo', 'sheet'], ['photo', 'sheet']]
    # Only item-category files can be linked.
    assert _edit(admin_client, two_items, share_file_ids=[files['chip']]).status_code == 400


def test_urls_are_appended_and_deduplicated(app, admin_client, two_items):
    response = _edit(admin_client, two_items, urls=[
        {'url': 'https://a.example/1', 'title': 'dup'}, {'url': 'https://b.example/2', 'title': "Maker's sheet"},
        {'url': '', 'title': 'ignored'}])
    assert response.status_code == 200
    assert [u['url'] for u in _item(app, two_items[0])['urls']] == ['https://a.example/1', 'https://b.example/2']
    assert _item(app, two_items[0])['urls'][0]['title'] == 'A', 'an existing entry is left as it was'
    assert [u['url'] for u in _item(app, two_items[1])['urls']] == [
        'https://legacy.example/x', 'https://legacy.example/y', 'https://a.example/1', 'https://b.example/2']


@pytest.mark.parametrize('entry', [
    {'url': 'javascript:alert(1)'}, {'url': 'data:text/html,hi'}, {'url': 'https://x.example/"onmouseover'},
    {'url': 'https://x.example/${alert(1)}'}, {'url': 'https://x.example/a b'},
    {'url': 'https://x.example/', 'title': '<img src=x>'}, {'url': 'https://x.example/', 'info': 'a`b'},
])
def test_unsafe_urls_are_rejected(app, admin_client, two_items, entry):
    assert _edit(admin_client, two_items, urls=[entry]).status_code == 400
    assert len(_item(app, two_items[0])['urls']) == 1


def test_url_without_scheme_or_with_port_is_allowed(app, admin_client, two_items):
    assert _edit(admin_client, two_items[:1], urls=[{'url': 'example.com/ds.pdf'}, {'url': 'lab.local:8080/x'}]).status_code == 200


def test_url_list_overflow_saves_nothing(app, admin_client, two_items):
    long = [{'url': f'https://example.com/{"x" * 200}/{n}'} for n in range(12)]
    response = _edit(admin_client, two_items, urls=long, short_info='should not stick')
    assert response.status_code == 400 and 'too long' in response.get_json()['message']
    assert _item(app, two_items[0])['short_info'] == 'keep me'
    assert len(_item(app, two_items[0])['urls']) == 1


def test_advanced_fields_need_edit_advance(app, make_user, login, two_items, files):
    with app.app_context():
        perms = Role.query.filter_by(name='Admin').one().get_permissions()
        perms['items']['edit_advance'] = False
        db.session.add(Role(name='no-advance', permissions=json.dumps(perms)))
        db.session.commit()
    make_user('basic', role='no-advance')
    client = login('basic')
    for fields in ({'thumbnail': 'share:photo.png'}, {'share_file_ids': [files['photo']]}, {'urls': [{'url': 'https://x.example'}]}):
        assert _edit(client, two_items, **fields).status_code == 403, fields
    assert _edit(client, two_items, short_info='allowed').status_code == 200
    page = client.get('/items').get_data(as_text=True)
    assert 'id="be_short_info"' in page and 'id="be_thumbnail"' not in page and 'id="be_url_rows"' not in page
    assert client.get('/items/share-files').status_code == 403
