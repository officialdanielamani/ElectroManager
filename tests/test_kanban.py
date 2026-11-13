import json

import pytest

from models import db, KanbanBoard, KanbanCard


@pytest.fixture
def boards(app, make_user, login):
    """Owner has 'Personal' and 'Shared'; guest can edit 'Shared' and view 'Readonly'; 'Public' is public."""
    owner_id, guest_id = make_user('owner'), make_user('guest')
    owner, guest = login('owner'), login('guest')

    def board(client, name):
        board_id = client.post('/kanban/boards', json={'name': name}).get_json()['id']
        column_id = client.post(f'/kanban/boards/{board_id}/columns', json={'name': 'Todo'}).get_json()['id']
        return {'id': board_id, 'col': column_id}

    result = {name: board(owner, name) for name in ('Personal', 'Shared', 'Readonly', 'Public')}
    result['Guest'] = board(guest, 'Guest')
    share = json.dumps([{'id': guest_id, 'name': 'guest'}])
    with app.app_context():
        db.session.get(KanbanBoard, result['Shared']['id']).share_edit_users = share
        db.session.get(KanbanBoard, result['Readonly']['id']).share_view_users = share
        db.session.get(KanbanBoard, result['Public']['id']).is_public = True
        db.session.commit()

    def card(board_name, title='Network'):
        b = result[board_name]
        response = owner.post(f"/kanban/boards/{b['id']}/cards", json={'title': title, 'column_id': b['col']})
        assert response.status_code in (200, 201), response.get_data(as_text=True)
        return response.get_json()['id']

    result.update(owner=owner, guest=guest, card=card)
    return result


def _dest(boards, name):
    return {'board_id': boards[name]['id'], 'column_id': boards[name]['col']}


def _titles(app, board_id):
    with app.app_context():
        return sorted(c.title for c in KanbanCard.query.filter_by(board_id=board_id))


def test_owner_moves_card_between_own_boards(app, boards):
    card_id = boards['card']('Personal')
    response = boards['owner'].post(f'/kanban/cards/{card_id}/move', json=_dest(boards, 'Shared'))
    assert response.status_code == 200
    assert _titles(app, boards['Personal']['id']) == []
    assert _titles(app, boards['Shared']['id']) == ['Network']


def test_move_requires_write_access_to_source(app, boards):
    for source in ('Readonly', 'Public'):
        card_id = boards['card'](source)
        response = boards['guest'].post(f'/kanban/cards/{card_id}/move', json=_dest(boards, 'Guest'))
        assert response.status_code in (403, 404)
        assert _titles(app, boards[source]['id']) == ['Network']


def test_editor_can_move_out_of_shared_board(app, boards):
    card_id = boards['card']('Shared')
    assert boards['guest'].post(f'/kanban/cards/{card_id}/move', json=_dest(boards, 'Guest')).status_code == 200
    assert _titles(app, boards['Guest']['id']) == ['Network']


def test_move_requires_write_access_to_destination(app, boards):
    card_id = boards['card']('Shared')
    for destination in ('Readonly', 'Public', 'Personal'):
        response = boards['guest'].post(f'/kanban/cards/{card_id}/move', json=_dest(boards, destination))
        assert response.status_code in (403, 404)
    assert _titles(app, boards['Shared']['id']) == ['Network']


def test_duplicate_from_readable_board_to_writable_board(app, boards):
    for source in ('Readonly', 'Public', 'Shared'):
        card_id = boards['card'](source, title=source)
        response = boards['guest'].post(f'/kanban/cards/{card_id}/duplicate', json=_dest(boards, 'Guest'))
        assert response.status_code in (200, 201)
        assert _titles(app, boards[source]['id']) == [source], 'the original stays put'
    assert _titles(app, boards['Guest']['id']) == ['Public-copy', 'Readonly-copy', 'Shared-copy']


def test_duplicate_is_refused_without_access(app, boards):
    private_card = boards['card']('Personal')
    assert boards['guest'].post(f'/kanban/cards/{private_card}/duplicate',
                                json=_dest(boards, 'Guest')).status_code in (403, 404)
    public_card = boards['card']('Public')
    assert boards['guest'].post(f'/kanban/cards/{public_card}/duplicate',
                                json=_dest(boards, 'Readonly')).status_code in (403, 404)
    assert _titles(app, boards['Guest']['id']) == []
    assert _titles(app, boards['Readonly']['id']) == []


def test_column_must_belong_to_destination_board(boards):
    card_id = boards['card']('Personal')
    mismatched = {'board_id': boards['Shared']['id'], 'column_id': boards['Personal']['col']}
    assert boards['owner'].post(f'/kanban/cards/{card_id}/move', json=mismatched).status_code == 400


def test_writable_board_list(boards):
    names = {b['name'] for b in boards['guest'].get('/kanban/boards/writable').get_json()}
    assert names == {'Guest', 'Shared'}


def test_card_icon_round_trip(boards):
    card_id = boards['card']('Personal')
    owner = boards['owner']
    owner.put(f'/kanban/cards/{card_id}', json={'card_icon': 'bi-star'})
    assert owner.get(f'/kanban/cards/{card_id}').get_json()['card_icon'] == 'bi-star'
    owner.put(f'/kanban/cards/{card_id}', json={'card_icon': ''})
    assert owner.get(f'/kanban/cards/{card_id}').get_json()['card_icon'] == ''
