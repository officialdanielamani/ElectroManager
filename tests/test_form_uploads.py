"""Files picked in the New / Edit item and project forms are uploaded, checked and reported on save."""
import io
import json
import os

import pytest
from PIL import Image

from conftest import PASSWORD
from models import db, Attachment, Item, Project, ProjectAttachment, Role, Setting, SharedFile


def png_bytes(size=(8, 8)):
    buf = io.BytesIO()
    Image.new('RGB', size, '#3366ff').save(buf, 'PNG')
    return buf.getvalue()


def jpeg_bytes():
    buf = io.BytesIO()
    Image.new('RGB', (8, 8), '#ff6633').save(buf, 'JPEG')
    return buf.getvalue()


PDF = b'%PDF-1.4\n%test\n'
EXE = b'MZ\x90\x00' + b'\x00' * 200          # a Windows program
BIG = b'\x00' * (1024 * 1024 + 10)           # just over 1 MB


def files(*pairs):
    return [(io.BytesIO(data), name) for name, data in pairs]


@pytest.fixture
def upload_settings(app):
    with app.app_context():
        Setting.set('allowed_extensions', 'png,jpg,jpeg,pdf,txt')
        Setting.set('max_file_size_mb', '1')
        Setting.set('max_file_upload_count', '3')


def flashes(client):
    with client.session_transaction() as session:
        return [(category, message) for category, message in session.get('_flashes', [])]


def new_item(client, name='PCB 12X7CM', **extra):
    data = {'name': name, 'min_quantity': 0, 'location_type': 'general', **extra}
    return client.post('/item/new', data=data, content_type='multipart/form-data')


def test_new_item_saves_good_files_and_reports_each_rejected_one(app, admin_client, upload_settings):
    response = new_item(admin_client, new_attachments=files(
        ('1.jpeg', jpeg_bytes()), ('2.png', BIG), ('3.jpeg', EXE), ('notes.zip', b'PK\x03\x04'), ('info.pdf', PDF)))
    assert response.status_code == 302
    with app.app_context():
        item = Item.query.filter_by(name='PCB 12X7CM').one()
        assert sorted(a.original_filename for a in item.attachments) == ['1.jpeg', 'info.pdf']
        for att in item.attachments:
            assert os.path.isfile(os.path.join(app.config['UPLOAD_FOLDER'], att.filename))
    messages = flashes(admin_client)
    assert messages[0] == ('success', 'Item "PCB 12X7CM" created successfully! 2 files uploaded.')
    warnings = [m for c, m in messages if c == 'warning']
    assert any('"2.png"' in m and 'too large' in m for m in warnings)
    assert any('"3.jpeg"' in m and 'program (executable) disguised as .jpeg' in m for m in warnings)
    assert any('"notes.zip"' in m and '.zip files are not permitted' in m for m in warnings)
    assert len(warnings) == 3


def test_count_limit_includes_existing_files(app, admin_client, upload_settings):
    new_item(admin_client, new_attachments=files(('a.png', png_bytes()), ('b.png', png_bytes())))
    with app.app_context():
        uuid = Item.query.one().uuid
    admin_client.post(f'/item/{uuid}/edit', data={'name': 'PCB 12X7CM', 'min_quantity': 0, 'location_type': 'general',
                                                  'new_attachments': files(('c.png', png_bytes()), ('d.png', png_bytes()))},
                      content_type='multipart/form-data')
    with app.app_context():
        assert sorted(a.original_filename for a in Item.query.one().attachments) == ['a.png', 'b.png', 'c.png']
    assert any('"d.png"' in m and 'limit of 3 files' in m for _, m in flashes(admin_client))


def test_edit_applies_removals_renames_and_uploads_with_the_other_fields(app, admin_client, upload_settings):
    new_item(admin_client, new_attachments=files(('keep.png', png_bytes()), ('drop.pdf', PDF)))
    with app.app_context():
        item = Item.query.one()
        keep = next(a for a in item.attachments if a.original_filename == 'keep.png')
        drop = next(a for a in item.attachments if a.original_filename == 'drop.pdf')
        item.thumbnail = drop.filename
        db.session.commit()
        uuid, keep_id, drop_id, drop_path = item.uuid, keep.id, drop.id, drop.filename
    response = admin_client.post(f'/item/{uuid}/edit', data={
        'name': 'Renamed board', 'min_quantity': 2, 'location_type': 'general',
        'remove_attachment_ids[]': [str(drop_id)],
        'rename_attachments': json.dumps({str(keep_id): 'front.png'}),
        'new_attachments': files(('back.jpeg', jpeg_bytes())),
    }, content_type='multipart/form-data')
    assert response.status_code == 302
    with app.app_context():
        item = Item.query.one()
        assert item.name == 'Renamed board' and item.min_quantity == 2
        assert sorted(a.original_filename for a in item.attachments) == ['back.jpeg', 'front.png']
        assert item.thumbnail is None, 'a thumbnail pointing at a removed file is cleared'
    assert not os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], drop_path))


def test_files_of_another_item_cannot_be_removed(app, admin_client, upload_settings, make_item):
    new_item(admin_client, name='Owner', new_attachments=files(('a.png', png_bytes())))
    other_id = make_item('Other')
    with app.app_context():
        att_id = Attachment.query.one().id
        other_uuid = db.session.get(Item, other_id).uuid
    admin_client.post(f'/item/{other_uuid}/edit', data={'name': 'Other', 'min_quantity': 0, 'location_type': 'general',
                                                        'remove_attachment_ids[]': [str(att_id)]})
    with app.app_context():
        assert Attachment.query.count() == 1


def _role_without(app, *actions):
    with app.app_context():
        perms = Role.query.filter_by(name='Admin').one().get_permissions()
        for action in actions:
            perms['items'][action] = False
        name = 'no-' + '-'.join(actions)
        db.session.add(Role(name=name, permissions=json.dumps(perms)))
        db.session.commit()
        return name


def test_uploads_and_removals_follow_permissions(app, make_user, login, upload_settings, admin_client):
    new_item(admin_client, name='Shared', new_attachments=files(('a.png', png_bytes())))
    with app.app_context():
        uuid, att_id = Item.query.one().uuid, Attachment.query.one().id

    make_user('noupload', role=_role_without(app, 'edit_advance'))
    client = login('noupload')
    client.post(f'/item/{uuid}/edit', data={'name': 'Shared', 'min_quantity': 0, 'location_type': 'general',
                                            'new_attachments': files(('b.png', png_bytes()))},
                content_type='multipart/form-data')
    assert any('permission to add files' in m for _, m in flashes(client))

    make_user('noremove', role=_role_without(app, 'delete_advance'))
    client = login('noremove')
    client.post(f'/item/{uuid}/edit', data={'name': 'Shared', 'min_quantity': 0, 'location_type': 'general',
                                            'remove_attachment_ids[]': [str(att_id)]})
    assert any('permission to delete files' in m for _, m in flashes(client))
    with app.app_context():
        assert [a.original_filename for a in Item.query.one().attachments] == ['a.png']


def test_uploads_turned_off(app, admin_client, upload_settings):
    with app.app_context():
        Setting.set('max_file_upload_count', '0')
    new_item(admin_client, new_attachments=files(('a.png', png_bytes())))
    with app.app_context():
        assert Attachment.query.count() == 0
    assert any('uploads are turned off' in m for _, m in flashes(admin_client))


def test_new_item_links_share_files(app, admin_client):
    with app.app_context():
        sf = SharedFile(name='info-pcb', filename='info-pcb.pdf', category='item')
        db.session.add(sf)
        db.session.commit()
        sf_id = sf.id
    new_item(admin_client, **{'share_file_ids[]': [str(sf_id)]})
    with app.app_context():
        assert [f.name for f in Item.query.one().linked_share_files] == ['info-pcb']


def test_new_and_edit_pages_offer_uploads(app, admin_client, make_item):
    page = admin_client.get('/item/new').get_data(as_text=True)
    assert 'class="pending-uploads"' in page and 'Browse Share Files' in page
    with app.app_context():
        uuid = db.session.get(Item, make_item('Part')).uuid
    assert 'class="pending-uploads"' in admin_client.get(f'/item/{uuid}/edit').get_data(as_text=True)


# ── Projects ─────────────────────────────────────────────────────────────

def new_project(client, **extra):
    return client.post('/project/new', data={'name': 'Robot', **extra}, content_type='multipart/form-data')


def test_new_project_uploads_per_attachment_type(app, admin_client):
    with app.app_context():
        Setting.set('project_upload_picture_max_size', '1')
        sf = SharedFile(name='spec', filename='spec.pdf', category='project')
        db.session.add(sf)
        db.session.commit()
        sf_id = sf.id
    response = new_project(admin_client, **{
        'new_files_picture': files(('front.png', png_bytes()), ('huge.png', BIG), ('fake.jpg', EXE)),
        'new_files_document': files(('manual.pdf', PDF), ('virus.exe', EXE)),
        'share_file_ids[]': [str(sf_id)],
    })
    assert response.status_code == 302
    with app.app_context():
        project = Project.query.one()
        assert sorted((a.attachment_type, a.original_filename) for a in project.attachments) == [
            ('document', 'manual.pdf'), ('picture', 'front.png')]
        assert [f.name for f in project.linked_share_files] == ['spec']
        picture = next(a for a in project.attachments if a.attachment_type == 'picture')
        assert os.path.isfile(os.path.join(app.config['UPLOAD_FOLDER'], picture.file_path))
    messages = flashes(admin_client)
    assert messages[0] == ('success', 'Project "Robot" created successfully! 2 files uploaded.')
    warnings = [m for c, m in messages if c == 'warning']
    assert any('"huge.png" (Pictures)' in m and 'too large' in m for m in warnings)
    assert any('"fake.jpg" (Pictures)' in m and 'disguised as .jpg' in m for m in warnings)
    assert any('"virus.exe" (Documents)' in m and 'not permitted' in m for m in warnings)


def test_edit_project_removes_files_and_keeps_share_files(app, admin_client):
    with app.app_context():
        sf = SharedFile(name='spec', filename='spec.pdf', category='project')
        db.session.add(sf)
        db.session.commit()
        sf_id = sf.id
    new_project(admin_client, **{'new_files_document': files(('a.pdf', PDF), ('b.pdf', PDF)),
                                 'share_file_ids[]': [str(sf_id)]})
    with app.app_context():
        project = Project.query.one()
        drop = next(a for a in project.attachments if a.original_filename == 'b.pdf')
        pid, drop_id, drop_path = project.project_id, drop.id, drop.file_path
    admin_client.post(f'/project/{pid}/edit', data={'name': 'Robot v2', 'remove_attachment_ids[]': [str(drop_id)],
                                                    'share_file_ids[]': [str(sf_id)]})
    with app.app_context():
        project = Project.query.one()
        assert project.name == 'Robot v2'
        assert [a.original_filename for a in project.attachments] == ['a.pdf']
        assert [f.name for f in project.linked_share_files] == ['spec']
    assert not os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], drop_path))


def test_project_share_file_inputs_belong_to_the_form(app, admin_client):
    """They sit outside <form>, so without form="projectForm" saving silently unlinked every share file."""
    with app.app_context():
        sf = SharedFile(name='spec', filename='spec.pdf', category='project')
        db.session.add(sf)
        db.session.commit()
        sf_id = sf.id
    new_project(admin_client, **{'share_file_ids[]': [str(sf_id)]})
    with app.app_context():
        pid = Project.query.one().project_id
    page = admin_client.get(f'/project/{pid}/edit').get_data(as_text=True)
    assert f'name="share_file_ids[]" value="{sf_id}" id="sfhid_{sf_id}" form="projectForm"' in page
    assert 'class="pending-uploads" data-form="projectForm"' in admin_client.get('/project/new').get_data(as_text=True)


# ── Request size ─────────────────────────────────────────────────────────

def test_request_limit_fits_a_full_form(app, upload_settings):
    from uploads import request_size_limit
    with app.app_context():
        assert request_size_limit() >= 3 * 1024 * 1024
        Setting.set('max_file_size_mb', '40')
        Setting.set('max_file_upload_count', '-1')
        assert request_size_limit() >= 50 * 40 * 1024 * 1024


def test_oversized_request_returns_to_the_form_with_a_message(app, admin_client):
    previous = app.config['MAX_CONTENT_LENGTH']
    app.config['MAX_CONTENT_LENGTH'] = 1024
    try:
        response = admin_client.post('/item/new', data={'name': 'x', 'new_attachments': files(('a.png', BIG))},
                                     content_type='multipart/form-data', headers={'Referer': 'http://localhost/item/new'})
    finally:
        app.config['MAX_CONTENT_LENGTH'] = previous
    assert response.status_code == 302 and response.headers['Location'].endswith('/item/new')
    assert any('Nothing was saved' in m for _, m in flashes(admin_client))


# ── Share Files library ──────────────────────────────────────────────────

def test_share_library_upload_uses_the_same_checks(app, admin_client):
    with app.app_context():
        Setting.set('share_item_extensions', 'png,pdf')
        Setting.set('share_item_max_size', '1')
        Setting.set('share_item_max_files', '2')
    response = admin_client.post('/settings/share-files/upload', data={
        'category': 'item',
        'files': files(('board.png', png_bytes()), ('trojan.pdf', EXE), ('big.png', BIG),
                       ('notes.txt', b'hi'), ('sheet.pdf', PDF), ('third.png', png_bytes())),
    }, content_type='multipart/form-data')
    assert response.status_code == 302
    with app.app_context():
        assert sorted(f.name for f in SharedFile.query.filter_by(category='item')) == ['board', 'sheet']
    messages = flashes(admin_client)
    assert messages[0] == ('success', '2 files uploaded to item.')
    warnings = [m for c, m in messages if c == 'warning']
    assert any('"trojan.pdf"' in m and 'disguised as .pdf' in m for m in warnings)
    assert any('"big.png"' in m and 'too large' in m for m in warnings)
    assert any('"notes.txt"' in m and 'not permitted' in m for m in warnings)
    assert any('"third.png"' in m and 'limit of 2 files' in m for m in warnings)


def test_share_page_has_the_upload_area(admin_client):
    page = admin_client.get('/settings/share-files').get_data(as_text=True)
    assert 'id="shareUploadArea" data-form="shareUploadForm" data-name="files"' in page


# ── Kanban cards ─────────────────────────────────────────────────────────

@pytest.fixture
def card(app, admin_client):
    board = admin_client.post('/kanban/boards', json={'name': 'Work'}).get_json()['id']
    column = admin_client.post(f'/kanban/boards/{board}/columns', json={'name': 'Todo'}).get_json()['id']
    return admin_client.post(f'/kanban/boards/{board}/cards', json={'title': 'Wire it', 'column_id': column}).get_json()['id']


def card_files(client, card_id, **data):
    return client.post(f'/kanban/cards/{card_id}/files', data=data, content_type='multipart/form-data')


def test_card_files_are_checked_and_removals_applied(app, admin_client, card):
    from models import KanbanAttachment
    with app.app_context():
        Setting.set('kanban_upload_extensions', 'png,pdf')
        Setting.set('kanban_upload_max_files', '2')
    result = card_files(admin_client, card, files=files(('a.png', png_bytes()), ('b.pdf', EXE), ('c.pdf', PDF),
                                                        ('d.png', png_bytes()))).get_json()
    assert result['uploaded'] == 2
    assert any('"b.pdf"' in m and 'disguised' in m for m in result['messages'])
    assert any('"d.png"' in m and 'limit of 2 files' in m for m in result['messages'])
    with app.app_context():
        atts = KanbanAttachment.query.filter_by(card_id=card).all()
        a_id = next(a.id for a in atts if a.original_filename == 'a.png')
        a_path = next(a.filename for a in atts if a.original_filename == 'a.png')
    result = card_files(admin_client, card, **{'remove_attachment_ids[]': [str(a_id)],
                                               'files': files(('e.png', png_bytes()))}).get_json()
    assert (result['uploaded'], result['removed']) == (1, 1), 'a removal frees a slot in the same save'
    with app.app_context():
        assert sorted(a.original_filename for a in KanbanAttachment.query.filter_by(card_id=card)) == ['c.pdf', 'e.png']
    assert not os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], a_path))


def test_card_files_need_board_access(app, card, make_user, login):
    make_user('stranger')
    response = card_files(login('stranger'), card, files=files(('a.png', png_bytes())))
    assert response.status_code == 403


def test_view_shared_users_may_change_files(app, admin_client, card, make_user, login):
    from models import KanbanBoard, KanbanCard, User
    viewer_id = make_user('viewer')
    with app.app_context():
        board = db.session.get(KanbanBoard, db.session.get(KanbanCard, card).board_id)
        board.share_view_users = json.dumps([{'id': viewer_id, 'name': 'viewer'}])
        db.session.commit()
    assert card_files(login('viewer'), card, files=files(('a.png', png_bytes()))).get_json()['uploaded'] == 1


def test_kanban_page_has_the_upload_area(admin_client, card):
    assert 'id="card-pending-uploads"' in admin_client.get('/kanban').get_data(as_text=True)


# ── Project URLs ─────────────────────────────────────────────────────────

def test_project_urls_apply_on_save(app, admin_client):
    from models import ProjectURL
    new_project(admin_client, **{'new_url[]': ['https://a.example/spec', 'javascript:alert(1)'],
                                 'new_url_title[]': ['Spec', 'Evil'], 'new_url_description[]': ['first', '']})
    assert any('"javascript:alert(1)" was not added' in m for _, m in flashes(admin_client))
    with app.app_context():
        project = Project.query.one()
        assert [(u.url, u.title, u.description) for u in project.urls] == [('https://a.example/spec', 'Spec', 'first')]
        pid, url_id = project.project_id, project.urls[0].id
    admin_client.post(f'/project/{pid}/edit', data={'name': 'Robot', 'remove_url_ids[]': [str(url_id)],
                                                    'new_url[]': ['http://b.example'], 'new_url_title[]': [''],
                                                    'new_url_description[]': ['']})
    with app.app_context():
        assert [(u.url, u.title) for u in ProjectURL.query.all()] == [('http://b.example', None)]


def test_project_url_of_another_project_cannot_be_removed(app, admin_client):
    from models import ProjectURL
    new_project(admin_client, **{'new_url[]': ['https://a.example'], 'new_url_title[]': [''], 'new_url_description[]': ['']})
    with app.app_context():
        url_id = ProjectURL.query.one().id
    admin_client.post('/project/new', data={'name': 'Other'})
    with app.app_context():
        other = Project.query.filter_by(name='Other').one().project_id
    admin_client.post(f'/project/{other}/edit', data={'name': 'Other', 'remove_url_ids[]': [str(url_id)]})
    with app.app_context():
        assert ProjectURL.query.count() == 1
