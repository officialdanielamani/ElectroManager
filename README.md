# Inventory Manager

A powerful, feature-rich web-based inventory management system built with Flask. Designed for businesses and organizations that need to efficiently track, organize, and manage physical inventory across multiple locations and storage racks.

### ⚠️ **Not for Production Usage, the app is highly experemental**

## Overview

Inventory Manager is a full-featured inventory management solution that combines ease of use with powerful functionality. Whether you're managing a small warehouse or a large-scale operation, this application provides the tools you need to maintain complete visibility over your inventory in real-time.

The application runs entirely within a web browser, making it accessible from any device on your network without requiring client-side installations.

## ✨ Key Features

### Core Inventory Management
- **Comprehensive Item Management** - Create, edit, and track items with detailed information including descriptions with markdown support
- **Inventory with Locations and Racks** - Organize inventory hierarchically by location and storage rack with visual representation
- **Item Categorization and Tagging** - Categorize items and apply custom tags for better organization and filtering
- **Multi-View Display** - View your inventory items in table format or card view based on preference

### Storage & Organization
- **Visual Storage Rack Management** - See a visual representation of your storage racks and locate items at a glance
- **Location Management** - Organize items across multiple physical locations
- **Magic Parameters** - Define custom item attributes dynamically without database schema changes
- **Item Attributes** - Flexible attribute system for storing unique product specifications

### Advanced Features
- **Role-Based Access Control (RBAC)** - Fine-grained permission management with customizable user roles
- **Search and Locate** - Powerful search functionality to locate items and visualize their storage location
- **Item Descriptions with Markdown** - Use markdown formatting for rich item descriptions

## Quick Start

### System Requirements
- Python 3.11 or higher
- 2GB disk space for application and database to be safe
- Modern web browser (Chrome, Firefox, Safari, Edge)
- For Windows: Windows 7 or higher
- For Linux/Mac: Any distribution with Python 3.11+

### Windows Setup

1. **Clone or extract the application** to your desired location
2. **Run the setup script**:
   ```bash
   setup_windows.bat
   ```
3. The script will automatically:
   - Check for Python installation
   - Create a virtual environment
   - Install dependencies
   - Initialize the database
   - Start the application

4. **Access the application**:
   - Open your browser to `http://localhost:5000`
   - Default login: `admin` / `admin123`
   - ⚠️ **Change the default password immediately!**

### Linux/Mac Setup

1. **Clone or extract the application**:
   ```bash
   tar -xzf inventory-manager-final.tar.gz
   cd inventory-manager
   ```

2. **Run the setup script**:
   ```bash
   chmod +x setup_linux.sh
   ./setup_linux.sh
   ```

3. The script will:
   - Check system dependencies
   - Create a Python virtual environment
   - Install required packages
   - Initialize the database
   - Start the Flask development server

4. **Access the application**:
   - Open your browser to `http://localhost:5000`
   - Default login: `admin` / `admin123`
   - ⚠️ **Change the default password immediately!**

### Docker Setup

**Docker Compose (Recommended)**:

1. **Install Docker and Docker Compose** if not already installed
2. **Run the application**:
   ```bash
   docker-compose up -d
   ```
3. Access at `http://localhost:5000`

**Manual Docker Build**:

```bash
docker build -t inventory-manager .
docker run -p 5000:5000 -v inventory-data:/app/instance inventory-manager
```

## File Structure

```
inventory-manager/
├── app.py                    # Main Flask application entry point
├── config.py                 # Configuration settings
├── models.py                 # Database models (SQLAlchemy)
├── forms.py                  # WTForms form definitions
├── requirements.txt          # Python dependencies
├── init_db.py               # Database initialization script
├── create_admin.py          # Admin user creation utility
├── Dockerfile               # Docker containerization
├── docker-compose.yml       # Docker Compose configuration
├── setup_windows.bat        # Windows setup script
├── setup_linux.sh          # Linux/Mac setup script
├── startup.sh              # Application startup script
├── verinfo.md              # Just an information notes
│
├── routes/                  # Modular route handlers
│   ├── auth.py             # Authentication and login
│   ├── item.py             # Item management
│   ├── location_rack.py    # Location and rack management
│   ├── category.py         # Item categories
│   ├── footprint_tag.py    # Tags and footprints
│   ├── magic_parameter.py  # Magic parameters system
│   ├── user_role.py        # User and role management
│   ├── backup.py           # Backup and restore functionality
│   ├── print.py            # Print templates and generation
│   ├── qr_template.py      # QR code template management
│   ├── visual_storage.py   # Visual storage management
│   ├── settings.py         # Application settings
│   ├── notification.py     # Notification system
│   ├── report.py           # Reporting features
│   ├── api.py              # REST API endpoints
│   └── __init__.py         # Routes module initialization
│
├── templates/              # Jinja2 HTML templates
│   ├── base.html           # Base template with layout
│   ├── index.html          # Home page
│   ├── login.html          # Login page
│   ├── items.html          # Item list page
│   ├── item_detail.html    # Item detail view
│   ├── item_form.html      # Item creation/edit form
│   ├── location_management.html  # Location management
│   ├── rack_management.html      # Rack management
│   ├── visual_storage.html       # Visual storage view
│   ├── users.html          # User management
│   ├── roles.html          # Role management
│   ├── backup_restore.html # Backup/restore interface
│   ├── settings*.html      # Various settings pages
│   ├── *_print.html        # Print templates
│   ├── qr_template*.html   # QR code template pages
│   └── [other templates]   # Additional page templates
│
├── static/                      # Static assets
│   ├── css/                     # Stylesheets
│   │   ├── style.css            # Main stylesheet
│   │   └── themes/              # Theme files
│   ├── js/                      # JavaScript files
│   │   ├── script.js            # Main JavaScript
│   │   └── table-sorter.js      # Table sorting functionality
│   └── fonts/                   # Fonts files
│       └── your-fonts.woff2     # Custom fonts
│
├── uploads/                # User-uploaded files (generated at runtime)
├── instance/               # Instance-specific files
│   └── inventory.db        # SQLite database (generated at runtime)
│
└── .env.example           # Environment variables example
```

## 🔧 Configuration

Create a `.env` file in the root directory for custom configuration:

| Variable | Default | Description | Type |
|----------|---------|-------------|------|
| `SECRET_KEY` | `dev-secret-key-change-this` | Secret key for session encryption (change in production!) | String |
| `DATABASE_URI` | `sqlite:///inventory.db` | Database connection string | String |
| `UPLOAD_FOLDER` | `uploads` | Directory for user uploads and attachments | String |
| `MAX_CONTENT_LENGTH` | `16777216` | Maximum upload size in bytes (10MB default) | Integer |
| `DEMO_MODE` | `false` | Enable demo mode (disable certain parts) | Boolean |
| `ADMIN_USERNAME` | `admin` | Default admin username on first setup | String |
| `ADMIN_PASSWORD` | `admin123` | Default admin password on first setup | String |
| `ADMIN_EMAIL` | `admin@example.com` | Default admin email on first setup | String |

### Example `.env` file

```env
# Security
SECRET_KEY=your-super-secret-key-change-this-9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d

# Database
DATABASE_URI=sqlite:///instance/inventory.db

# File Uploads
UPLOAD_FOLDER=uploads
MAX_CONTENT_LENGTH=16777216

# Demo Mode
DEMO_MODE=false

# Initial Admin Credentials (only used on first setup)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
ADMIN_EMAIL=admin@example.com
```

### Experimental Features

- **Custom Print Templates** - Design custom layouts for item information and lists
- **QR Template Creator** - Build and customize QR code templates
- **QR Code Printing** - Advanced QR code printing features

## Future Plans

The following features are planned for upcoming releases:

- **Basic Project Management** - Manage inventory-related projects
- **Item Management Revamp** - Enhanced item interface with detailed logging
- **Auto Backup System** - Automatic scheduled backups with system version tracking
- **Accessibility Improvements** - Extended theme customization including fonts and colors
- **Branding Customization** - Add company logo and customize server name
- **REST API with RBAC** - Full-featured API for external application integration with role-based access control


## Dependencies

- **Flask** 3.0.0 - Web framework
- **Flask-SQLAlchemy** 3.1.1 - ORM and database
- **Flask-Login** 0.6.3 - User session management
- **Flask-WTF** 1.2.1 - Form validation
- **Pillow** 10.0.0+ - Image processing
- **python-qrcode** 7.4.2+ - QR code generation
- **python-barcode** 0.15.1+ - Barcode generation
- **WeasyPrint** 60.0+ - HTML to PDF conversion
- **ReportLab** 4.0.0+ - PDF generation
- **Markdown** 3.5.1 - Markdown parsing
- **Bleach** 6.1.0 - HTML sanitization

See `requirements.txt` for complete dependency list.


## 📝 License

MIT License

---

**Inventory Manager** - Manage your inventory efficiently and effectively.

*Last Updated: 2025*
