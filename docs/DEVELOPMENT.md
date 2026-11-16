# ElectroManager — maintainer guide

For someone picking the project up. The [README](../README.md) covers what the app does and how to
install it; this covers how the code is put together, how to change it safely, and what is unfinished.

## Running it

```bash
pip install -r requirements-dev.txt     # app + test dependencies
python3 startup/init_db.py              # first run: roles, default settings, admin user
python3 app.py                          # http://localhost:5000, admin / admin123
pytest                                  # full test suite, about a minute
```

Python 3.11 is what the Docker image and CI use. WeasyPrint needs the Pango and Cairo system
libraries (the Dockerfile and the CI workflow show the package names).

Set `FLASK_DEBUG=1` for the reloader and debugger. Configuration is environment variables only
(`config.py`, `.env.example`).

## How the code is organised

The app is one Flask application object created at import time in `app.py` (there is no app factory).
Importing `app` connects to the database and applies migrations, so any script or test must set
`DATABASE_URI` *before* the import — `tests/conftest.py` shows the pattern.

| Where | What |
|-------|------|
| `app.py` | App object, login manager, context processors, security headers, file-serving routes, startup |
| `models.py` | Every SQLAlchemy model |
| `routes/` | One blueprint per feature area, registered in `routes/__init__.py` |
| `templates/`, `static/` | Jinja templates (Bootstrap 5, no build step) and bundled assets |
| `item_search.py` | Turns the item list's query string into a SQL query (quick and advanced search) |
| `item_stock.py` | Stock figures — see below |
| `db_migrate.py`, `migrations/` | Schema migrations |
| `plugins/`, `routes/plugins.py` | Plugin system |
| `startup/` | `init.py` (asset checks, runs `init_db.py`), `init_db.py` (roles, settings, admin user) |
| `utils.py`, `helpers.py` | Permission decorators, audit log, upload handling, Jinja filters |

Permissions are role-based. A role stores a JSON tree of permissions; check with
`current_user.has_permission('items', 'view')` or the decorators in `utils.py`. The canonical
permission sets for the built-in roles are in `startup/init_db.py` and are re-synced on every start,
so a new permission must be added there.

## Stock figures

`item_stock.py` is the only place that knows how stock is counted:

> available = quantity − lent out − used by projects

"Lent out" is the count of lent, non-deleted serial numbers for a batch with serial tracking, and the
sum of unreturned lend records otherwise. An item's figures are the sums over its batches. Status is
`no` (nothing available and the item's no-stock warning is on), `low` (available below the item's
minimum) or `ok`.

- Lists: `stock_for_items(items)` / `stock_for_batches(batches)` return a dict in one query;
  `stock_summary()` and `items_needing_restock()` serve the counters and the low-stock page.
- Filtering in SQL: `StockColumns(item_stock_subquery())` exposes the figures as expressions
  (`item_search.py` uses it).
- One object: `item.stock`, `batch.stock`, `item.batch_stock()`. Each access runs a query, so read it
  once into a variable; in a loop over many rows use the bulk functions instead.

Nothing about stock is stored on the item — do not add cached quantity or price columns back.

## Changing the database schema

1. Edit `models.py`.
2. `alembic revision --autogenerate -m "what changed"` — this writes a file in `migrations/versions/`.
3. Read the generated file. Autogenerate does not move data; write that by hand
   (`0002_item_tags_table.py` is an example). On SQLite, prefer plain `ALTER TABLE` operations over
   table rebuilds where the installed SQLite supports them.
4. Run `pytest`. `tests/test_migrations.py` fails if the models and migrations disagree, and exercises
   upgrading a database from before migrations existed.

Migrations run automatically when the app starts (`upgrade_database` in `db_migrate.py`), after
copying an existing SQLite file to `<name>.before-<revision>.bak`. `0001_baseline.py` is special: on
a pre-Alembic database it creates only missing tables and adds the columns the old startup code used
to patch in. Do not edit it; add new revisions instead.

Never call `db.create_all()` in application code — it would create tables that a later migration then
fails to create.

## Tests

`tests/conftest.py` points the app at a temporary database and gives each test a clean one with the
built-in roles. Useful fixtures: `make_user`, `login`, `admin_client`, `make_item`.

| File | Covers |
|------|--------|
| `test_smoke.py` | Every page with no URL arguments renders without a server error |
| `test_migrations.py` | Fresh database, legacy database adoption, backup copy, downgrade |
| `test_auth.py` | Login, lockout, registration, two-factor auth, session lifetime, security headers |
| `test_item_search.py` | Quick and advanced search, including Magic Parameter AND / OR groups |
| `test_item_stock.py` | Stock figures, low-stock page, report counters, query-count guard |
| `test_item_tags.py` | Tags through the item form, bulk edit and tag deletion |
| `test_kanban.py` | Card move / duplicate permissions |
| `test_plugins_backup.py` | Plugin admin pages, restoring a backup |

A test client request must not run inside `with app.app_context():` — the request would share that
context's `g`, which breaks Flask-Login. Do database setup inside the context, requests outside it.

Not covered: most write paths for projects, lending sessions, contacts, QR templates and the REST
API; anything that needs a browser (JavaScript behaviour).

CI is `.github/workflows/tests.yml`: the test suite on Python 3.11 and 3.13, then a Docker image
build that starts the container with Docker Compose and waits for its health check.

## Plugins

A plugin is a package in `plugins/` whose `__init__.py` subclasses `PluginBase` (`plugins/base.py`)
and calls `register_plugin(MyPlugin())`. `plugins/example_oauth/` is a template. A plugin declares:

- `slug`, `name`, `description`, `version`, `plugin_type`
- `config_schema` — a list of fields (`text`, `password`, `bool`, `select`) that the admin page turns
  into a settings form; values are stored as JSON on the `plugins` table
- hooks: `on_enable(config)`, `on_disable()`, `on_config_update(config)`, `validate_config(config)`,
  `register_blueprints(app)`

Plugins are imported at startup and listed under Settings → Plugins. Adding or removing one needs a
restart.

## Known gaps

Things a new maintainer should know are unfinished or weak, roughly by importance:

- **Plugin system is a skeleton.** `on_enable` is called when an admin clicks Enable, but not at
  startup for plugins that were already enabled, and `PluginBase.register_blueprints` is never called
  (the loader looks for a module-level function of that name instead). The OAuth example has no
  login flow. Plugin secrets are stored unencrypted.
- **Two-factor secrets and backup codes are stored unencrypted** in the `users` table.
- **Content-Security-Policy allows inline scripts and styles**, because the templates rely on them.
- **Default admin password** is `admin123` unless `ADMIN_PASSWORD` is set before first run.
- **After a 2FA login the user lands on the home page**, not the page they originally asked for.
- **Magic Parameter numbers have no unit conversion**: 3300 mV and 3.3 V are unrelated to the search.
- **Project tags are still a JSON list** on the project (item tags were moved to a table).
- **Tag labels are white on every tag colour** outside the bulk-edit dialog, so pale tags are hard
  to read.
- **Print pages link a Bootstrap CSS path that does not exist** (`static/lib/bootstrap/css/…`), so
  they render without Bootstrap styling.
- **SQLite only in practice.** Backup and restore copy the SQLite file, and migrations are tested on
  SQLite only.
- **Single process.** Rate limits, the API rate limiter and Kanban live updates are held in memory,
  and migrations run at import time, so the app must run as one process (`python3 app.py`).
