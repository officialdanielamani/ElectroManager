"""Every page that takes no URL arguments must render for an admin without a server error."""
import pytest

from app import app as flask_app

SKIP = {
    '/logout',            # ends the session the other pages need
    '/backup/download',   # writes a copy of the database into the working directory
}


def _pages():
    pages = set()
    for rule in flask_app.url_map.iter_rules():
        if 'GET' in rule.methods and not rule.arguments and rule.rule not in SKIP:
            pages.add(rule.rule)
    return sorted(pages)


@pytest.mark.parametrize('path', _pages())
def test_page_renders(path, admin_client, make_item):
    make_item('Smoke Test Part', sku='SMK-1')
    response = admin_client.get(path)
    assert response.status_code < 500, f'{path} returned {response.status_code}'
