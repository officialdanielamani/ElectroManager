# ElectroManager

A web-based inventory management system built with Flask, designed for individuals and small teams that need to track, organize, and manage physical inventory — especially electronic components — across multiple locations and storage racks.

### ⚠️ **Not for Production Usage — the app is highly experimental**

---

## Overview

ElectroManager runs entirely in a web browser, making it accessible from any device on your network without client-side installations. It combines detailed component tracking (batches, serial numbers, datasheets) with project management, lending/return workflows, contact management, and a flexible permission system — all backed by a local SQLite database.

---

## ✨ Features

### Item Management
- Create, edit, and delete items with name, SKU, type/model, description (Markdown supported), and datasheet URLs
- **Batch system** — each item's stock is split into independent batches with their own quantity, price per unit, purchase date, manufacturer, note, and optional label
- **Per-batch location override** — each batch can follow the item's main location or be assigned its own rack/drawer or general location independently
- **Serial number tracking** — enable per-batch SN tracking (up to 100 units); generate, edit, and transfer individual serial numbers; inline editing of SN, info, and lend-to fields; ISN remap
- **Lending tracking** — mark items or individual serial numbers as lent; available quantity is calculated after deducting lent and project-allocated stock
- **Pre-create batches** on the new-item form — add initial batches before saving the item
- **"Save and Create New"** button — save the current item and immediately open a fresh form to enter the next one
- Minimum quantity threshold with low-stock warnings (per item, toggleable)
- Attach files (PDFs, images, documents) directly to items
- Multiple datasheet URLs per item
- Link shared library files to items (reuse the same file across multiple items without re-uploading)
- Item thumbnail image
- **Advanced search** — filter the item list by name, UUID, short info, SKU, type/model, stock status, available-quantity and price ranges, and multiple categories, tags and footprints; add Magic Parameter filters (number with unit and range/min/max/exact, string values, date range) combined with AND / OR; filters carry through pagination and printing

### Organisation
- **Categories** — name, description, color; quick-add modal directly from item form
- **Footprints** — physical package types (DIP, QFP, etc.) with color coding; quick-add modal
- **Tags** — multi-tag support with custom colors for flexible cross-category labeling; quick-add modal
- **Magic Parameters** — define reusable custom attributes (numeric, date, string) with configurable units and predefined string options; apply parameter templates to items in bulk
- Item filtering by category and stock status (OK / Low / No Stock)
- Full-text search across name, SKU, and description

### Storage Locations
- **General locations** — named storage areas with description, color, info field, and optional picture
- **Rack / Drawer system** — define racks as row × column grids; each drawer tracks which item lives there
- **Visual storage view** — graphical rack map with per-drawer item preview and pagination
- **Rack icons and drawer icons** — assign Bootstrap icons or custom images to racks and individual drawers
- **Drawer short info** — add a text label to each drawer slot visible in the visual view
- **Cell merging** — merge adjacent rack cells into one logical slot (rectangular or non-rectangular groups); split merged cells back
- Mark individual drawers as unavailable
- Bulk-move drawer contents to another drawer or location
- Swap contents between two drawers in one operation
- Prefill location/drawer on item creation from the visual storage view
- QR sticker generation for locations, racks, and individual drawer slots

### In/Out — Lending & Returns
- **Cart-based workflow** — search for items/batches, add them to a cart, then submit a single lending or return session
- **Lending sessions** — each lend or return is grouped under a unique session ID (`YYYYMMDD-XXXXXX`), recorded with borrower, date range, and notes
- **Lending to contacts** — lend to system users, contact persons, organizations, or contact groups
- **Session history** — paginated list of all past lending and return sessions with filtering
- **Audit log view** — per-item lending activity log (lend, return, update, delete actions)
- **Session QR sticker** — generate a QR sticker PDF for a lending session for physical record-keeping
- Return workflow supports partial returns; returned items restore available inventory quantity
- Serial-number-level lending tracking integrated with batch SN management

### Contacts
- **Persons** — name, email, phone; associate with an organization
- **Organizations** — name, email, phone, URL, address, zip code, short info
- **Contact Groups** — named groups containing a mix of users, persons, and organizations
- Contacts are used as lending targets in the In/Out system and as project assignees
- Managed under **Settings → Contacts**

### Projects
- Create and manage projects with name, info/description, status, category, tags, start/end dates, and assigned users, persons, organizations, or groups
- **Bill of Materials (BOM)** — link inventory items (with optional specific batch) to a project with required and used quantities; track used/unused status; supports serial-number assignment
- **Project cost tracking** — add extra cost line items per project: *per-quantity* costs (e.g. labour per unit) and *overall* costs (e.g. one-off fees); combined with BOM actual cost for a full project cost estimate
- Available-for-BOM search excludes items already lent or assigned elsewhere
- Project attachments with separate upload limits by category (pictures, documents, schematics, 2D/3D files)
- Project reference URLs with optional title and description
- Link shared library files to projects
- **Dateline notifications** — configurable alerts (N days before end date) visible in the notification centre
- Project-level status tracking (active, completed, overdue; custom statuses supported)
- Per-user column visibility for the project list table
- Magic Parameters on projects (same parameter definitions as items)
- Manage project categories, statuses, persons, and groups via settings

### Kanban
- **Boards** — create personal or shared Kanban boards with custom columns (name, color, icon), per-board color/icon, and a pin/hide/show status list
- **Cards** — title, description (free text), priority (Low/Medium/High/Urgent), label color, category, due and start dates, key persons, and a Mark Done toggle
- **Tasks (checklist)** — per-card task lists with individual completion checkboxes, start/due dates, and inline edit/delete; task progress badge on board view
- **Card file uploads** — attach images and documents directly to cards; images open in a lightbox modal; enforces the Kanban upload settings (allowed types, max size, max files per batch); upload permission extends to view-shared users
- **Share Files on cards** — link files from the shared library (Item, Project, or Icon categories) to a card using the same browse-picker UI as items and projects; chips display with thumbnail preview
- **Board sharing** — share boards in edit mode (collaborators can create, edit, and delete cards/tasks) or view-only mode; public boards visible to all logged-in users
- **Real-time collaboration** — presence indicators show who else is viewing or editing the same board; card changes by other users sync automatically without a page reload
- **Categories** — per-board label categories with configurable names; used to color-tag cards
- **Move / duplicate cards across boards** — move a card to another board and column (needs edit access to both boards), or duplicate it (needs view access to the source and edit access to the destination); optional per-card icon
- **Keyboard-friendly** — drag-and-drop column/card reordering via SortableJS; collapse/expand task lists per card with state persisted in localStorage

### Shared File Library
- Central file library (`Settings → Share Files`) for uploading files once and linking them to multiple items, projects, or Kanban cards
- Categories: `item`, `project`, `icon`, `profile`, `sticker`
- Bulk delete and bulk download
- Files are stored in a dedicated share folder separate from item/project attachments
- Scan-and-register tool to import files dropped directly into the share folder on disk

### Reporting & Printing
- Low-stock report (items below minimum quantity or fully out of stock)
- Summary dashboard with total items, total inventory value, low-stock count, and category breakdown
- Print-ready item list (table or card view) respecting active search/filter
- Print-ready project list with customisable columns
- Single-item detail print view

### QR Codes & Sticker Labels
- Automatic QR code on every item linking to its detail page
- **Sticker template designer** — custom layout builder for QR/barcode stickers; supports items, locations, racks, drawer slots, and lending sessions
- Live sticker preview per entity
- PDF generation for sticker layouts
- Inline QR SVG endpoint for embedding in pages

### Import / Export
- Database backup download and restore (previous backup kept automatically)
- **Selective JSON export / import** for configuration data:
  - Magic Parameters (parameters, templates, units, string options — granular selection)
  - Locations, Racks, Categories, Footprints, Tags
  - Optional: include per-item parameter values in export

### User & Access Control
- **Role-Based Access Control (RBAC)** — create roles with granular permissions across:
  - Items: view, create, delete, and individual edit permissions per field (name, SKU/type, description, datasheet, uploads, price, quantity, location, category, footprint, tags, parameters, batches, serial numbers, lending)
  - Projects: view, create, edit, delete
  - Lending & Returns: view page, lend, return
  - Kanban: view & manage boards
  - Settings sections: backup/restore, location management, reports, project settings, magic parameters, contacts
  - Pages: notifications, visual storage
- Admin users bypass all permission checks
- Login-attempt limiting with configurable auto-unlock timeout; demo-user flag
- **Two-factor authentication (TOTP)** — each user can enable 2FA under General Settings with any authenticator app; eight single-use backup codes are issued at setup
- Rate limiting on login, 2FA, registration and password-check endpoints; session lifetime limit; Content-Security-Policy and related security headers (HSTS when served over HTTPS)
- Per-user profile photo upload with configurable source (upload / shared library / both)
- Configurable per-user flags: allow password reset, allow name/info changes, allow profile picture changes

### Plugins
- Server extensions live in `plugins/`; each is a small Python package discovered at startup
- Admin page (**Settings → Plugins**) to enable, disable and configure plugins from a settings form the plugin declares
- Ships with an example OAuth / SSO skeleton (`plugins/example_oauth/`) — a starting point, not a working login provider. See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md#plugins)

### Personalisation
- **Themes** — Light, Dark, Blue, Keqing; theme CSS files are auto-detected from `static/custom/theme/` so new themes can be added by dropping in a CSS file
- **Fonts** — built-in system fonts plus any font files placed in `static/custom/font/` (e.g. OpenDyslexic); selected per user in settings
- Per-user column visibility for the item list table and project list table

### Notifications
- Notification centre showing date-parameter alerts (due today or overdue) and duration-parameter windows
- Project dateline alerts (configurable N-days-before warning)

### Audit Log
- Every create / read / update / delete action is logged with user, entity type, entity ID, and timestamp
- In/Out module has a dedicated lending activity log view

### Settings — File Uploads
- Per-section upload limits configurable at `Settings → System → File Upload Settings`
- **Sections:** Item Uploads, Project Uploads (per attachment type), Kanban Card Uploads, Share Files Uploads
- **Controls per section:** Allowed file types (extension list), Max file size (MB), Max files per upload batch
- **Max files semantics:** `-1` = unlimited, `0` = new uploads disabled (existing files are never affected), `>0` = batch limit enforced on every upload request
- Share Files section defaults to a higher max-files limit (acts as a drive); all others default to 5

### Image Caching & Thumbnails
- Thumbnails are generated automatically on upload for image attachments (`png`, `jpg`, `jpeg`, `gif`, `webp`) on items, project pictures, and share-library files
- Thumbnails are stored under `uploads/thumbs/` mirroring the original file structure; they are deleted automatically when the original file is removed
- List views (item list, project detail image grid, share-files library) serve thumbnails (400 × 400 px max) so only small images are downloaded; full-resolution originals are only fetched when opening the lightbox preview
- All image responses include `Cache-Control: public, max-age=86400` so browsers and proxies cache them for 24 hours and avoid redundant downloads on page reload
- SVG files are served as-is (no raster thumbnail generated)
- If Pillow is not installed, thumbnail generation is silently skipped; the fallback route always serves the full-size original

### In/Out — Sound Effects
- The In/Out scanning workflow plays audio feedback when a barcode/QR is scanned
- Toggle in the scan interface settings panel
- Sound files must be present at `static/mp3/scanner.mp3`, `static/mp3/success.mp3`, and `static/mp3/error.mp3`

---

## API

See **[API.md](API.md)** for the full API reference, including:
- External API v1 (`/api/v1/`) — token-based, for ESP32 and third-party integrations
- Internal API — session-based endpoints used by the browser UI

---

## Quick Start

### System Requirements
- Python 3.11 or higher (for local setup)
- Modern web browser (Chrome, Firefox, Safari, Edge)
- Docker + Docker Compose (for containerised setup)

### Docker Setup (Recommended)

All core JS/CSS dependencies (Bootstrap, Bootstrap Icons, SortableJS) are bundled in the repository, so the image needs no network access at container startup or on restart.

```bash
# Clone the repository
git clone https://github.com/officialdanielamani/ElectroManager.git
cd ElectroManager

# Start the application
docker-compose up -d
```

Access at **http://localhost:5000** · Default login: `admin` / `admin123`
⚠️ **Change the default password immediately after first login.**

**Manual Docker build:**
```bash
docker build -t electromanager .
docker run -p 5000:5000 \
  -v ./uploads:/app/uploads \
  -v ./instance:/app/instance \
  -v ./static/custom:/app/static/custom \
  electromanager
```

#### Startup behaviour

Every time the container (or local server) starts, `startup/init.py` runs through these steps:

| Step | What happens |
|------|-------------|
| Create dirs | Ensures all required directories exist |
| **Verify core assets** | Checks that Bootstrap CSS/JS, Bootstrap Icons, SortableJS are on disk — **fatal** if any are missing |
| **Detect custom assets** | Scans `static/custom/` and logs what it finds — informational only, never blocks startup |
| Init database | Creates the SQLite database on first run, or upgrades an existing one to the current schema (see [Upgrading](#upgrading)); creates the built-in roles, default settings and the admin user if missing |

#### Custom assets <a name="custom-assets"></a>

`static/custom/` is bind-mounted as a Docker volume so you can add files without rebuilding the image:

```
./static/custom:/app/static/custom    # already in docker-compose.yml
```

Two dedicated subfolders — no manual registration needed:

| Folder | Purpose |
|--------|---------|
| `static/custom/font/` | Font files (`.woff2` / `.woff` / `.ttf` / `.otf`). Detected by `/api/available-fonts`; available in the user font picker. |
| `static/custom/theme/` | Theme CSS files with a `/* Theme Metadata */` header. Detected and listed in the theme picker under **Settings → Personalisation**. |

> Icon packs are intentionally not supported — the app uses the bundled Bootstrap Icons everywhere so QR templates and UI stay consistent across installs.

### Linux / Mac Setup

```bash
git clone https://github.com/officialdanielamani/ElectroManager.git
cd ElectroManager
chmod +x startup/start.sh
./startup/start.sh
```

### Windows Setup

```bat
git clone https://github.com/officialdanielamani/ElectroManager.git
cd ElectroManager
startup\start.bat
```

The startup script initialises (or upgrades) the database and launches the server. Install the Python dependencies first with `pip install -r requirements.txt`, or run `setup_linux.sh` / `setup_windows.bat`, which create a virtual environment and install them for you.

### Upgrading

Pull the new code (and rebuild the image with `docker-compose up -d --build` if you use Docker), then start the app as usual. Database changes are applied automatically at startup. Before changing a database that already holds data, the app saves a copy next to it as `instance/inventory.db.before-<revision>.bak`; to roll back, stop the app, restore that file over `inventory.db`, and run the previous version of the code.

---

## Configuration

Create a `.env` file (copy from `.env.example`) to override defaults:

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | `dev-secret-key-change-this` | Session encryption key — **change in production** |
| `DATABASE_URI` | `sqlite:///instance/inventory.db` | SQLAlchemy database URI |
| `UPLOAD_FOLDER` | `uploads` | Directory for file attachments |
| `MAX_CONTENT_LENGTH` | `16777216` | Global maximum upload size in bytes (16 MB) |
| `DEMO_MODE` | `false` | Enable demo mode (restricts certain operations) |
| `ADMIN_USERNAME` | `admin` | Initial admin username (first-run only) |
| `ADMIN_PASSWORD` | `admin123` | Initial admin password (first-run only) |
| `ADMIN_EMAIL` | `admin@example.com` | Initial admin email (first-run only) |
| `SESSION_LIFETIME_HOURS` | `8` | How long a login session lasts |
| `SESSION_COOKIE_SECURE` | `false` | Set to `true` when the app is served over HTTPS: cookies are then sent only over HTTPS and an HSTS header is added |

---

## File Structure

```
ElectroManager/
├── app.py                        # Flask application entry point
├── config.py                     # Configuration class
├── models.py                     # SQLAlchemy models
├── forms.py                      # WTForms definitions
├── helpers.py                    # Jinja2 filters and helpers
├── utils.py                      # Shared utilities (permissions, audit log, etc.)
├── extensions.py                 # Shared Flask extensions (CSRF, rate limiter)
├── importexport.py               # JSON import/export logic
├── qr_utils.py                   # QR code and sticker PDF generation
├── item_search.py                # Item list filtering (quick + advanced search)
├── item_stock.py                 # Stock figures in SQL — the one place stock is counted
├── db_migrate.py                 # Applies database migrations at startup
├── alembic.ini                   # Alembic configuration
├── API.md                        # API reference (external v1 + internal)
├── requirements.txt              # Python dependencies
├── requirements-dev.txt          # + test dependencies
├── pytest.ini                    # Test runner configuration
├── Dockerfile                    # Docker image
├── docker-compose.yml            # Docker Compose configuration
├── .env.example                  # Environment variable template
│
├── docs/
│   └── DEVELOPMENT.md            # Maintainer guide: architecture, workflows, known gaps
│
├── migrations/                   # Alembic environment
│   └── versions/                 # One file per schema change, applied in order
│
├── plugins/                      # Server extensions (see docs/DEVELOPMENT.md)
│   ├── base.py                   # PluginBase and the plugin registry
│   └── example_oauth/            # Example OAuth / SSO skeleton
│
├── tests/                        # pytest suite
│
├── .github/workflows/tests.yml   # CI: tests + Docker image check
│
├── startup/                      # Startup and initialisation scripts
│   ├── init.py                   # Unified startup (checks assets, inits DB)
│   ├── init_db.py                # Built-in roles, default settings, admin user
│   ├── create_admin.py           # Admin user creation
│   ├── docker.sh                 # Docker entrypoint script
│   └── start.sh                  # Local startup script
│
├── routes/                       # Flask blueprints (one per feature area)
│   ├── item.py                   # Item CRUD, list, search, print views, attachments
│   ├── batch.py                  # Batch management and serial numbers
│   ├── in_out.py                 # Lending & return sessions (In/Out)
│   ├── project.py                # Projects, BOM, cost items, project attachments
│   ├── kanban.py                 # Kanban boards, columns, cards, tasks, attachments
│   ├── location_rack.py          # Locations and racks management
│   ├── visual_storage.py         # Visual rack/drawer interface
│   ├── category.py               # Categories
│   ├── footprint_tag.py          # Footprints and tags
│   ├── magic_parameter.py        # Magic Parameters and templates
│   ├── contacts.py               # Contact persons, organizations, groups
│   ├── share.py                  # Shared file library
│   ├── user_role.py              # Users and roles
│   ├── auth.py                   # Login, logout, registration, two-factor auth
│   ├── settings.py               # Application settings
│   ├── notification.py           # Notification centre
│   ├── report.py                 # Reports
│   ├── backup.py                 # Backup and restore
│   ├── qr_template.py            # QR sticker template designer
│   ├── plugins.py                # Plugin admin pages
│   ├── api.py                    # Core internal REST API endpoints
│   ├── api_v1.py                 # External REST API v1 (/api/v1/)
│   └── __init__.py               # Blueprint registration
│
├── templates/                    # Jinja2 HTML templates
│   ├── base.html                 # Base layout
│   ├── items.html                # Item list
│   ├── item_detail.html          # Item detail view
│   ├── item_form.html            # Item create / edit form
│   ├── kanban.html               # Kanban board view (boards, cards, tasks, uploads)
│   ├── in_out*.html              # Lending / return pages
│   ├── project*.html             # Project pages
│   ├── visual_storage.html       # Visual rack map
│   ├── contacts*.html            # Contact management pages
│   ├── users.html / roles.html   # User and role management
│   ├── backup_restore.html       # Backup / restore UI
│   ├── settings*.html            # Settings pages
│   ├── *_print.html              # Print templates
│   ├── qr_template*.html         # QR sticker designer pages
│   └── [other templates]
│
├── static/
│   ├── css/
│   │   └── style.css             # Application stylesheet
│   ├── js/
│   │   ├── script.js             # Main application JS
│   │   ├── icon-picker.js        # Shared Bootstrap icon picker
│   │   ├── theme-loader.js       # Theme switching
│   │   ├── table-sorter.js       # Client-side table sorting
│   │   ├── md-editor.js          # Markdown editor helper
│   │   └── marked.min.js         # Markdown renderer
│   ├── mp3/                      # UI sound effects — scanner beep, success chime, error pop
│   │   ├── scanner.mp3           # Plays on QR/barcode scan (In/Out)
│   │   ├── success.mp3           # Plays on successful lend/return
│   │   └── error.mp3             # Plays on scan error
│   ├── icons/                    # Bootstrap Icons — bundled
│   ├── lib/                      # Bootstrap CSS/JS, SortableJS and other bundled libraries
│   └── custom/                   # ← User-provided: custom fonts + themes (bind-mounted in Docker)
│       ├── font/                 # Drop font files here (.woff2, .ttf, etc.)
│       └── theme/                # Drop theme CSS files here
│
├── uploads/                      # User file uploads (runtime, bind-mounted in Docker)
│   ├── items/                    # Item file attachments — organised by item UUID
│   ├── projects/                 # Project attachments — organised by project ID and type
│   ├── share/                    # Shared file library — organised by category
│   ├── thumbs/                   # Auto-generated thumbnails — mirrors the structure above
│   ├── userpicture/              # User profile photos uploaded directly
│   └── kanban/                   # Kanban card attachments — organised by card UUID
└── instance/
    └── inventory.db              # SQLite database (runtime, bind-mounted in Docker)
```

---

## Development

```bash
pip install -r requirements-dev.txt
pytest
```

The test suite runs against a throwaway SQLite database, so it never touches `instance/inventory.db`.
GitHub Actions runs it on every push and pull request, and also builds the Docker image and checks
that the container starts and reports healthy.

The schema is managed with [Alembic](https://alembic.sqlalchemy.org/). To change it, edit `models.py`,
then generate and review a migration with `alembic revision --autogenerate -m "describe the change"`.
`pytest` fails if `models.py` and the migrations disagree.

**[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)** is the maintainer guide: how the code is organised,
how stock is calculated, how to add a migration or a plugin, and what is known to be unfinished.

## Dependencies

**Python**

| Package | Version | Purpose |
|---------|---------|---------|
| Flask | 3.0.0 | Web framework |
| Flask-SQLAlchemy | 3.1.1 | ORM / database |
| Flask-Login | 0.6.3 | Session management |
| Flask-WTF | 1.2.1 | Form handling and CSRF |
| Flask-Limiter | ≥ 3.5.0 | Rate limiting |
| Alembic | ≥ 1.13.0 | Database migrations |
| pyotp | ≥ 2.9.0 | Two-factor authentication (TOTP) |
| Pillow | ≥ 10.0.0 | Image processing |
| qrcode | ≥ 7.4.2 | QR code generation |
| python-barcode | ≥ 0.15.1 | Barcode generation |
| WeasyPrint | ≥ 60.0 | HTML → PDF (stickers) |
| ReportLab | ≥ 4.0.0 | PDF generation |
| Markdown | 3.5.1 | Markdown parsing |
| Bleach | 6.1.0 | HTML sanitisation |

**JavaScript / CSS — core** (bundled in the repository, verified at every startup)

| Library | Version | Purpose |
|---------|---------|---------|
| Bootstrap | 5.3.0 | UI framework |
| Bootstrap Icons | 1.11.1 | Core icon set |
| SortableJS | 1.15.0 | Drag-and-drop sorting |

**Customisable assets** (optional, place under `static/custom/`, no rebuild needed)

| Example | How to add |
|---------|-----------|
| Custom theme | Drop a `.css` file into `static/custom/theme/` (see existing themes for the metadata header format) |
| Personalisation font | Drop font files into `static/custom/font/` — no CSS needed, `@font-face` is generated automatically |

---

## 📝 License

MIT License

---

## 🎵 Sound Effect Credits

Sound effects used in the In/Out scanning workflow are sourced from [Pixabay](https://pixabay.com/) under the Pixabay Content License (royalty-free):

| File | Title | Author |
|------|-------|--------|
| `scanner.mp3` | Store Scanner Beep | freesound_community |
| `error.mp3` | UI Error Pop | SoundShelfStudio |
| `success.mp3` | UI Success Chime | SoundShelfStudio |

---

*ElectroManager — track your components, manage your builds.*
