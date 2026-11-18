"""Edit / Delete shortcuts on the Edit Item page's batch cards follow the lending_return permissions."""
import json

import pytest

from models import db, Item, Role


@pytest.fixture
def role_user(app, make_user):
    """Create a user whose role is Admin's permissions with lending_return overridden."""
    def _make(username, **lending_return):
        with app.app_context():
            perms = Role.query.filter_by(name='Admin').one().get_permissions()
            perms['lending_return'] = {**perms.get('lending_return', {}), **lending_return}
            db.session.add(Role(name=f'role-{username}', permissions=json.dumps(perms)))
            db.session.commit()
        return make_user(username, role=f'role-{username}')
    return _make


def _shortcuts(client, app, item_id):
    with app.app_context():
        uuid = db.session.get(Item, item_id).uuid
    html = client.get(f'/item/{uuid}/edit').get_data(as_text=True)
    return html.count('title="Edit this batch on the In/Out page"'), html.count('title="Delete this batch')


@pytest.mark.parametrize('perms, expected', [
    (dict(view_page=True, edit_batch=True, delete_batch=True), (1, 1)),
    (dict(view_page=True, edit_batch=True, delete_batch=False), (1, 0)),
    # Delete lives inside the In/Out edit form, so it also needs edit access.
    (dict(view_page=True, edit_batch=False, delete_batch=True), (0, 0)),
    (dict(view_page=False, edit_batch=True, delete_batch=True), (0, 0)),
])
def test_shortcuts_follow_permissions(app, role_user, login, make_item, perms, expected):
    item_id = make_item('Part')
    role_user('someone', **perms)
    assert _shortcuts(login('someone'), app, item_id) == expected


def test_shortcut_targets_open_in_out_page(app, admin_client, make_item):
    item_id = make_item('Part')
    with app.app_context():
        item = db.session.get(Item, item_id)
        uuid, batch_id = item.uuid, item.batches[0].id
    html = admin_client.get(f'/item/{uuid}/edit').get_data(as_text=True)
    assert f'href="/in-out?batch={batch_id}"' in html
    assert f'href="/in-out?batch={batch_id}&amp;action=delete"' in html
    assert admin_client.get(f'/in-out?batch={batch_id}&action=delete').status_code == 200
