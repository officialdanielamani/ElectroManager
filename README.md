# ElectroManager

A web-based inventory management system built with Flask, designed for individuals and small teams that need to track, organize, and manage physical inventory — especially electronic components — across multiple locations and storage racks.

### ⚠️ **Not for Production Usage — the app is highly experimental**

---

## Overview

ElectroManager runs entirely in a web browser, making it accessible from any device on your network without client-side installations. It combines detailed component tracking (batches, serial numbers, datasheets) with project management and a flexible permission system, all backed by a local SQLite database.

---

## ✨ Features

### Item Management
- Create, edit, and delete items with name, SKU, type/model, description (Markdown supported), and datasheet URLs
- **Batch system** — each item's stock is split into independent batches with their own quantity, price per unit, purchase date, note, and optional label
- **Serial number tracking** — enable per-batch SN tracking (up to 100 units); generate, edit, and transfer individual serial numbers; inline editing of SN, info, and lend-to fields; ISN remap
- **Lending tracking** — mark items or individual serial numbers as lent to a person; available quantity is calculated after deducting lent and project-allocated stock
- **Pre-create batches** on the new-item form — add initial batches before saving the item
- **"Save and Create New"** button — save the current item and immediately open a fresh form to enter the next one
- Minimum quantity threshold with low-stock warnings (per item, toggleable)
- Attach files (PDFs, images, documents) directly to items
- Multiple datasheet URLs per item

### Organization
- **Categories** — name, description, color; quick-add modal directly from item form
- **Footprints** — physical package types (DIP, QFP, etc.) with color coding
- **Tags** — multi-tag support with custom colors for flexible cross-category labeling
- **Magic Parameters** — define reusable custom attributes (numeric, date, string) with configurable units and predefined string options; apply parameter templates to items in bulk
- Item filtering by category and stock status (OK / Low / No Stock)
- Full-text search across name, SKU, and description

### Storage Locations
- **General locations** — named storage areas with description and color
- **Rack / Drawer system** — define racks as row × column grids; each drawer tracks which item lives there
- **Visual storage view** — graphical rack map with per-drawer item preview and pagination
- Mark individual drawers as unavailable
- Bulk-move drawer contents to another drawer or location
- Prefill location/drawer on item creation from the visual storage view

### Projects
- Create and manage projects with name, info/description, status, category, tags, start/end dates, and assigned persons or groups
- **Bill of Materials (BOM)** — link inventory items to a project with quantity or specific serial numbers; track used/unused status
- Available-for-BOM search excludes items already lent or assigned elsewhere
- Project attachments with separate upload limits by category (pictures, documents, schematics, 2D/3D files)
- Project reference URLs
- **Dateline notifications** — configurable alerts (N days before end date) visible in the notification centre
- Project-level status tracking (active, completed, overdue)
- Per-user column visibility for the project list table
- Manage project categories, statuses, persons, and groups via settings

### Reporting & Printing
- Low-stock report (items below minimum quantity or fully out of stock)
- Summary dashboard with total items, total inventory value, low-stock count, and category breakdown
- Print-ready item list (table or card view) respecting active search/filter
- Print-ready project list with customisable columns
- Single-item detail print view

### QR Codes & Sticker Labels
- Automatic QR code on every item linking to its detail page
- **Sticker template designer** — custom layout builder for QR/barcode stickers
- Live sticker preview per item
- PDF generation for single sticker layouts

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
  - Settings sections: backup/restore, location management, reports, project settings, magic parameters
  - Pages: notifications, visual storage
- Admin users bypass all permission checks
- Login-attempt limiting with automatic unlock; demo-user flag
- Per-user profile photo upload

### Personalisation
- **Themes** — Light, Dark, Blue, Keqing (automatically detected from `static/css/themes/`)
- **Fonts** — system fonts plus any font files placed in `static/fonts/`
- **Custom icon libraries & fonts** — drop `.css` or font files into `static/custom/`; they are auto-loaded on the next startup without rebuilding the image
- Per-user table column visibility for item and project lists

### Notifications
- Notification centre showing date-parameter alerts (due today or overdue) and duration-parameter windows
- Project dateline alerts

### Audit Log
- Every create / read / update / delete action is logged with user, entity type, entity ID, and timestamp

### REST API
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/search-item` | Search items (supports location/rack filters) |
| GET | `/api/drawer/<rack_uuid>/<drawer_id>` | Items in a specific drawer |
| POST | `/api/drawer/toggle-availability` | Mark a drawer available/unavailable |
| POST | `/api/drawer/move-items` | Bulk-move drawer contents |
| GET | `/api/available-fonts` | List available fonts |

---

## Quick Start

### System Requirements
- Python 3.11 or higher (for local setup)
- Modern web browser (Chrome, Firefox, Safari, Edge)
- Docker + Docker Compose (for containerised setup)

### Docker Setup (Recommended)

All JS/CSS dependencies (Bootstrap, Bootstrap Icons, SortableJS) are downloaded **once** during the image build and baked in — no internet access is needed at runtime or on container restart.

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

#### Custom icons and fonts (Docker)

Mount the `static/custom` volume (already included in `docker-compose.yml`):
```
./static/custom:/app/static/custom
```
Drop any `.css` or font file (`.woff2`, `.woff`, `.ttf`, `.otf`) into the `./static/custom/` folder on the host. The application detects and loads them automatically on the next startup — no rebuild required.

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

The startup script will create a virtual environment, install Python dependencies, download JS/CSS libraries, initialise the database, and launch the server.

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
├── importexport.py               # JSON import/export logic
├── qr_utils.py                   # QR code and sticker PDF generation
├── requirements.txt              # Python dependencies
├── js-requirements.json          # JS/CSS library manifest (Bootstrap, etc.)
├── Dockerfile                    # Docker image (deps baked in at build time)
├── docker-compose.yml            # Docker Compose configuration
├── .env.example                  # Environment variable template
│
├── startup/                      # Startup and initialisation scripts
│   ├── init.py                   # Unified startup (downloads deps, inits DB)
│   ├── init_db.py                # Database schema creation
│   ├── create_admin.py           # Admin user creation
│   ├── docker.sh                 # Docker entrypoint script
│   └── start.sh                  # Local startup script
│
├── routes/                       # Flask blueprints (one per feature area)
│   ├── item.py                   # Item CRUD, search, parameters, attachments
│   ├── batch.py                  # Batch management and serial numbers
│   ├── project.py                # Projects, BOM, project attachments
│   ├── location_rack.py          # Locations and racks management
│   ├── visual_storage.py         # Visual rack/drawer interface
│   ├── category.py               # Categories
│   ├── footprint_tag.py          # Footprints and tags
│   ├── magic_parameter.py        # Magic Parameters and templates
│   ├── user_role.py              # Users and roles
│   ├── settings.py               # Application settings
│   ├── notification.py           # Notification centre
│   ├── report.py                 # Reports
│   ├── backup.py                 # Backup and restore
│   ├── print_routes.py           # Print views
│   ├── qr_template.py            # QR sticker template designer
│   ├── api.py                    # REST API endpoints
│   └── __init__.py               # Blueprint registration
│
├── templates/                    # Jinja2 HTML templates
│   ├── base.html                 # Base layout
│   ├── items.html                # Item list
│   ├── item_detail.html          # Item detail view
│   ├── item_form.html            # Item create / edit form
│   ├── project*.html             # Project pages
│   ├── visual_storage.html       # Visual rack map
│   ├── users.html / roles.html   # User and role management
│   ├── backup_restore.html       # Backup / restore UI
│   ├── settings*.html            # Settings pages
│   ├── *_print.html              # Print templates
│   ├── qr_template*.html         # QR sticker designer pages
│   └── [other templates]
│
├── static/
│   ├── css/
│   │   ├── style.css             # Application stylesheet
│   │   ├── fontawesome.min.css   # Font Awesome (bundled)
│   │   └── themes/               # Theme files (light, dark, blue, keqing, …)
│   ├── js/
│   │   ├── script.js             # Main application JS
│   │   ├── theme-loader.js       # Theme switching
│   │   └── table-sorter.js       # Client-side table sorting
│   ├── fonts/
│   │   └── fontawesome/          # Font Awesome WOFF2 files (bundled)
│   ├── icons/                    # Bootstrap Icons (downloaded at build time)
│   ├── lib/                      # Bootstrap CSS/JS + SortableJS (downloaded at build time)
│   └── custom/                   # ← Drop custom CSS/font files here to auto-load
│
├── uploads/                      # User file uploads (runtime, bind-mounted in Docker)
└── instance/
    └── inventory.db              # SQLite database (runtime, bind-mounted in Docker)
```

---

## Dependencies

**Python**

| Package | Version | Purpose |
|---------|---------|---------|
| Flask | 3.0.0 | Web framework |
| Flask-SQLAlchemy | 3.1.1 | ORM / database |
| Flask-Login | 0.6.3 | Session management |
| Flask-WTF | 1.2.1 | Form handling and CSRF |
| Pillow | ≥ 10.0.0 | Image processing |
| qrcode | ≥ 7.4.2 | QR code generation |
| python-barcode | ≥ 0.15.1 | Barcode generation |
| WeasyPrint | ≥ 60.0 | HTML → PDF (stickers) |
| ReportLab | ≥ 4.0.0 | PDF generation |
| Markdown | 3.5.1 | Markdown parsing |
| Bleach | 6.1.0 | HTML sanitisation |

**JavaScript / CSS** (downloaded at Docker build time or first local startup)

| Library | Version | Purpose |
|---------|---------|---------|
| Bootstrap | 5.3.0 | UI framework |
| Bootstrap Icons | 1.11.1 | Icon set |
| Font Awesome | 7.1.0 | Icon set (bundled) |
| SortableJS | 1.15.0 | Drag-and-drop sorting |

---

## 📝 License

MIT License

---

*ElectroManager — track your components, manage your builds.*
