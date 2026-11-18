"""Item URLs: stored as JSON, rendered escaped, and only http(s) targets become links."""
import json
import re

import pytest

from helpers import dump_item_urls, item_url_href, parse_item_urls
from models import db, Item


@pytest.mark.parametrize('url, href', [
    ('https://example.com/a.pdf', 'https://example.com/a.pdf'),
    ('HTTP://example.com', 'HTTP://example.com'),
    ('example.com/ds.pdf', 'https://example.com/ds.pdf'),
    ('lab.local:8080/x', 'https://lab.local:8080/x'),
    ('javascript:alert(1)', None), (' JaVaScRiPt:alert(1)', None), ('data:text/html,x', None),
    ('vbscript:x', None), ('https://a b', None), ('', None),
])
def test_link_targets(url, href):
    assert item_url_href(url) == href


def test_parse_handles_json_legacy_and_junk():
    assert parse_item_urls(None) == []
    assert parse_item_urls('https://a\n\nhttps://b ') == [
        {'url': 'https://a', 'title': '', 'info': ''}, {'url': 'https://b', 'title': '', 'info': ''}]
    assert parse_item_urls(json.dumps([{'url': ' https://a ', 'title': 'A'}, {'title': 'no url'}, 'https://c', 5])) == [
        {'url': 'https://a', 'title': 'A', 'info': ''}, {'url': 'https://c', 'title': '', 'info': ''}]
    assert parse_item_urls('{"url": "x"}') == []


def test_dump_drops_entries_that_do_not_fit_instead_of_cutting_json():
    entries = [{'url': f'https://example.com/{"x" * 300}/{n}'} for n in range(10)]
    text = dump_item_urls(entries)
    kept = [e['url'] for e in json.loads(text)]
    assert len(text) <= 2048 and kept == [e['url'] for e in entries[:len(kept)]] and 0 < len(kept) < 10
    assert dump_item_urls([]) is None


@pytest.fixture
def hostile_item(app, make_item):
    item_id = make_item('Part')
    with app.app_context():
        item = db.session.get(Item, item_id)
        item.datasheet_urls = json.dumps([
            {'url': 'javascript:alert(document.cookie)', 'title': 'Click me', 'info': ''},
            {'url': 'https://ok.example/ds.pdf', 'title': '</strong><script>alert(1)</script>', 'info': '`${alert(2)}`'},
        ])
        db.session.commit()
        return item.uuid


def test_detail_page_escapes_and_never_links_unsafe_targets(admin_client, hostile_item):
    body = admin_client.get(f'/item/{hostile_item}').get_data(as_text=True)
    assert '<script>alert(1)</script>' not in body
    assert '&lt;/strong&gt;&lt;script&gt;alert(1)&lt;/script&gt;' in body
    assert 'href="javascript:' not in body.lower()
    assert re.search(r'href="https://ok\.example/ds\.pdf"[^>]*rel="noopener noreferrer"', body)


def test_edit_page_embeds_urls_as_json_not_raw(admin_client, hostile_item):
    body = admin_client.get(f'/item/{hostile_item}/edit').get_data(as_text=True)
    assert '<script>alert(1)</script>' not in body
    assert '`${alert(2)}`' not in body.split('formDatasheets = (', 1)[1].split(')', 1)[0]


def test_saving_the_edit_form_keeps_valid_json(app, admin_client, make_item):
    item_id = make_item('Part')
    with app.app_context():
        uuid = db.session.get(Item, item_id).uuid
    urls = [{'url': f'https://example.com/{"y" * 300}/{n}', 'title': '', 'info': ''} for n in range(10)]
    response = admin_client.post(f'/item/{uuid}/edit', data={
        'name': 'Part', 'min_quantity': 0, 'location_type': 'general', 'datasheet_urls': json.dumps(urls)})
    assert response.status_code == 302
    with app.app_context():
        stored = db.session.get(Item, item_id).datasheet_urls
    assert len(stored) <= 2048 and len(json.loads(stored)) >= 1, 'too many entries are dropped, not cut mid-JSON'
