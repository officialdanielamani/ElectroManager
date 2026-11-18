"""Static checks over the templates."""
import pathlib
import re

from app import app as flask_app
from models import db

TEMPLATES = pathlib.Path(__file__).resolve().parent.parent / 'templates'


def test_every_url_for_names_a_real_endpoint():
    # A url_for() to an endpoint that does not exist only fails when that branch of the template
    # renders, which is often a rare case (no templates yet, a particular notification...).
    endpoints = set(flask_app.view_functions) | {'static'}
    missing = set()
    for path in TEMPLATES.rglob('*.html'):
        for name in re.findall(r"url_for\(\s*['\"]([\w.]+)['\"]", path.read_text(encoding='utf-8')):
            if name not in endpoints:
                missing.add(f'{path.name}: {name}')
    assert not missing, sorted(missing)


def test_sticker_pages_render_without_any_templates(app, admin_client, make_item):
    """The 'no templates yet' message used to link to a removed endpoint."""
    from models import Item, Location, Rack
    item_id = make_item('Part')
    with app.app_context():
        item = db.session.get(Item, item_id)
        location = Location(name='Lab')
        db.session.add(location)
        db.session.flush()
        rack = Rack(name='R', location_id=location.id)
        db.session.add(rack)
        db.session.commit()
        uuid, batch_id, loc_uuid, rack_uuid = item.uuid, item.batches[0].id, location.uuid, rack.uuid
    for path in (f'/item/{uuid}/batch/{batch_id}/qr-sticker',
                 f'/items/bulk-qr-sticker?item_ids={item_id}', f'/location/{loc_uuid}/qr-sticker',
                 f'/rack/{rack_uuid}/qr-sticker'):
        response = admin_client.get(path)
        assert response.status_code == 200, path
        assert b'Create one' in response.data, path


def test_notifications_page_with_a_kanban_reminder(app, admin_client):
    from datetime import date
    from models import KanbanBoard, KanbanCard, KanbanColumn, User
    with app.app_context():
        owner = User.query.filter_by(username='admin').one()
        board = KanbanBoard(user_id=owner.id, name='Work', board_uuid='BOARDBOARDXK', notify_due_enabled=True)
        db.session.add(board)
        db.session.flush()
        column = KanbanColumn(board_id=board.id, name='Todo')
        db.session.add(column)
        db.session.flush()
        db.session.add(KanbanCard(uuid='CARDCARDCARD', board_id=board.id, column_id=column.id,
                                  title='Ship it', due_date=date.today()))
        db.session.commit()
        board_id = board.id
    body = admin_client.get('/notifications').get_data(as_text=True)
    assert 'is due today' in body and f'/kanban?board={board_id}' in body


def test_project_with_an_uploaded_picture_thumbnail(app, admin_client):
    from models import Project, ProjectAttachment, User
    with app.app_context():
        owner = User.query.filter_by(username='admin').one()
        project = Project(name='Robot', project_id='ROBOTROBOTXP', created_by=owner.id, updated_by=owner.id,
                          thumbnail='front.png')
        db.session.add(project)
        db.session.flush()
        db.session.add(ProjectAttachment(project_id=project.id, filename='front.png', original_filename='front.png',
                                         file_path='projects/ROBOTROBOTXP/picture/front.png', file_type='png',
                                         file_size=2048, attachment_type='picture'))
        db.session.commit()
    for path in ('/project/ROBOTROBOTXP', '/project/ROBOTROBOTXP/edit'):
        body = admin_client.get(path).get_data(as_text=True)
        assert 'projects/ROBOTROBOTXP/picture/front.png' in body, path


def test_sticker_templates_respect_sharing(app, make_user, login, make_item):
    """Another user's private template is neither listed nor usable."""
    import json
    from models import Item, StickerTemplate, User
    item_id = make_item('Part')
    from models import Role
    with app.app_context():
        perms = Role.query.filter_by(name='Admin').one().get_permissions()
        perms['settings_sections']['qr_templates']['view'] = False   # this permission sees every template
        db.session.add(Role(name='no-template-view', permissions=json.dumps(perms)))
        db.session.commit()
    make_user('owner')
    make_user('other', role='no-template-view')
    with app.app_context():
        owner = User.query.filter_by(username='owner').one()
        for kind in ('Items', 'Item Batch'):
            db.session.add(StickerTemplate(name=f'Private {kind}', template_type=kind, width_mm=50, height_mm=30,
                                           layout='[]', owner_id=owner.id, is_public=False))
        db.session.commit()
        item = db.session.get(Item, item_id)
        uuid, batch_id = item.uuid, item.batches[0].id
        items_tpl = StickerTemplate.query.filter_by(template_type='Items').one().id
    other, owner_client = login('other'), login('owner')
    assert b'Private Item Batch' not in other.get(f'/item/{uuid}/batch/{batch_id}/qr-sticker').data
    assert b'Private Item Batch' in owner_client.get(f'/item/{uuid}/batch/{batch_id}/qr-sticker').data
    assert other.get(f'/api/item/{uuid}/sticker-preview/{items_tpl}').status_code == 403
    assert other.get(f'/api/item/{uuid}/sticker-print/{items_tpl}').status_code == 403
    assert owner_client.get(f'/api/item/{uuid}/sticker-preview/{items_tpl}').status_code == 200
