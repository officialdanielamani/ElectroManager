import re

import pytest

from models import db, Item, Tag


@pytest.fixture
def tags(app):
    with app.app_context():
        rows = [Tag(name=name) for name in ('IR', 'SMD', 'Wifi')]
        db.session.add_all(rows)
        db.session.commit()
        return {row.name: row.id for row in rows}


def _tag_names(app, item_id):
    with app.app_context():
        return [tag.name for tag in db.session.get(Item, item_id).tags]


def test_new_item_form_saves_tags(app, admin_client, tags):
    response = admin_client.post('/item/new', data={
        'name': 'Tagged Part', 'quantity': 3, 'min_quantity': 0, 'location_type': 'general',
        'tags[]': [tags['IR'], tags['Wifi'], 99999],
    })
    assert response.status_code == 302, response.get_data(as_text=True)[:2000]
    with app.app_context():
        item_id = Item.query.filter_by(name='Tagged Part').one().id
    assert _tag_names(app, item_id) == ['IR', 'Wifi']


def test_edit_form_replaces_tags(app, admin_client, tags, make_item):
    item_id = make_item('Part')
    with app.app_context():
        item = db.session.get(Item, item_id)
        item.set_tag_ids([tags['IR'], tags['SMD']])
        db.session.commit()
        uuid = item.uuid
    page = admin_client.get(f'/item/{uuid}/edit').get_data(as_text=True)
    def is_checked(tag_id):
        return re.search(rf'id="tag{tag_id}"\s+checked', page) is not None
    assert is_checked(tags['IR']) and is_checked(tags['SMD']) and not is_checked(tags['Wifi'])

    response = admin_client.post(f'/item/{uuid}/edit', data={
        'name': 'Part', 'quantity': 10, 'min_quantity': 0, 'location_type': 'general', 'tags[]': [tags['Wifi']],
    })
    assert response.status_code == 302, response.get_data(as_text=True)[:2000]
    assert _tag_names(app, item_id) == ['Wifi']


def test_bulk_edit_tags(app, admin_client, tags, make_item):
    first, second, untouched = make_item('A'), make_item('B'), make_item('C')
    with app.app_context():
        db.session.get(Item, untouched).set_tag_ids([tags['IR']])
        db.session.commit()

    response = admin_client.post('/items/bulk-edit', json={'item_ids': [first, second], 'tags': [tags['SMD'], tags['Wifi']]})
    assert response.status_code == 200, response.get_data(as_text=True)
    assert _tag_names(app, first) == ['SMD', 'Wifi'] and _tag_names(app, second) == ['SMD', 'Wifi']
    assert _tag_names(app, untouched) == ['IR']

    # An empty list clears tags; leaving the key out changes nothing.
    admin_client.post('/items/bulk-edit', json={'item_ids': [first], 'tags': []})
    admin_client.post('/items/bulk-edit', json={'item_ids': [second], 'min_quantity': 4})
    assert _tag_names(app, first) == []
    assert _tag_names(app, second) == ['SMD', 'Wifi']


def test_deleting_a_tag_removes_it_from_items(app, admin_client, tags, make_item):
    item_id = make_item('Part')
    with app.app_context():
        db.session.get(Item, item_id).set_tag_ids([tags['IR'], tags['SMD']])
        db.session.commit()
    admin_client.post(f"/tag/{tags['IR']}/delete")
    assert _tag_names(app, item_id) == ['SMD']
    with app.app_context():
        assert db.session.execute(db.text('SELECT count(*) FROM item_tags')).scalar() == 1


def test_deleting_an_item_removes_its_tag_links(app, admin_client, tags, make_item):
    item_id = make_item('Part')
    with app.app_context():
        item = db.session.get(Item, item_id)
        item.set_tag_ids([tags['IR']])
        db.session.commit()
        db.session.delete(item)
        db.session.commit()
        assert db.session.execute(db.text('SELECT count(*) FROM item_tags')).scalar() == 0
        assert Tag.query.count() == 3


def test_tags_show_on_list_and_detail(app, admin_client, tags, make_item):
    item_id = make_item('Part')
    with app.app_context():
        item = db.session.get(Item, item_id)
        item.set_tag_ids([tags['Wifi']])
        db.session.commit()
        uuid = item.uuid
    assert b'Wifi' in admin_client.get('/items').data.split(b'id="itemTable"')[1].split(b'</table>')[0]
    assert b'Wifi' in admin_client.get(f'/item/{uuid}').data
