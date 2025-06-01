<p align="center">
  <img src="xris/static/img/logo.png" alt="XRIS Logo" width="120" />
</p>

# XRIS — X-Band Radar Information System

**XRIS** (X-Band Radar Information System) is a Django-based platform developed at MJIIT, Universiti Teknologi Malaysia. It ingests, processes, stores, and serves X-Band radar datasets (CSV, GeoTIFF, PNG, JPEG) with emphasis on:

* **Data Management & Analysis**: Tools for researchers and meteorologists to explore and analyze radar data.
* **Real-Time Live Radar Visualization**: Interactive map overlays with the latest radar frames.
* **User-Friendly Dashboards**: Intuitive interfaces, subscription tiers, and robust authentication.

---

## Table of Contents

1. [Key Features](#key-features)
2. [System Architecture](#system-architecture)
3. [Applications (Django Apps)](#applications-django-apps)
4. [User Interfaces](#user-interfaces)

   * [Super-Admin Panel](#super-admin-panel)
   * [User Portal](#user-portal)
5. [File & Folder Structure](#file--folder-structure)
6. [Technology Stack](#technology-stack)
7. [Local & Docker Deployment](#local--docker-deployment)

   * [Quick Start (Docker)](#quick-start-docker)
   * [Bare-Metal Deployment (UTM Pagoh)](#bare-metal-deployment-utm-pagoh)
8. [Environment Variables](#environment-variables)
9. [Celery Tasks & Automation](#celery-tasks--automation)
10. [Security & Hardening](#security--hardening)
11. [Development Workflow](#development-workflow)
12. [License](#license)

---

## Key Features

| **Area**           | **Highlights**                                  |
| ------------------ | ----------------------------------------------- |
| 🌐 **User Portal** | • Dashboard with stats & mini-charts (Chart.js) |

```
                                 • XMPR Data Explorer: filters, multi-select ZIP downloads, on-the-fly CSV analysis, PDF reports  
                                 • RainMap Archive: JPEG gallery, multi-select download, usage limits                                                                                                      |
```

\| 🛠 **Super-Admin Panel**         | • DaisyUI-themed Django Admin with Heroicons
• Inline preview/download for CSV/PNG/TIFF/JPEG
• Download log inlines (IP, user, timestamp)
• Singleton `ProjectConfig` model for site settings                                                                                                                  |
\| 📡 **Real-Time Radar Pipeline**  | • CSV → SSV → mesh → GeoTIFF & PNG conversion (Fortran + GDAL)
• Automatic insertion into PostgreSQL; RainMap JPEG ingestion
• Triggered every 2 minutes, with duplicate-run guard (Celery + Redis)                                                                                                 |
\| 📊 **Data Analysis & Reporting** | • In-browser rainfall matrix visualization (Alpine.js)
• Downloadable PDF reports (html2canvas + jsPDF)
• Per-file statistics (min, max, mean, std, distribution)                                                                                                               |
\| 🔒 **Auth & Subscriptions**      | • Django AllAuth (email/password, mandatory verification)
• Custom `User` model with avatar upload
• Stripe subscriptions (Free & Premium), billing portal, webhook handlers                                                                                                |
\| ⚙️ **GraphQL API**               | • Graphene-Django schema exposing paginated `latestXmprData` query for Live Radar viewer
• Apollo-compatible endpoint                                                                                                                                                          |
\| 🚀 **Container-Ready**           | • Docker Compose stack: Daphne (ASGI), Celery worker & beat, Flower, PostgreSQL 17, Redis, RabbitMQ
• Environment-variable-driven configuration                                                                                                                               |
\| 🛰 **Edge Deployment**           | • On-premise at **UTM Pagoh** server
• Public access via Cloudflare Tunnel (TLS, WAF)
• Nginx → Daphne reverse proxy, systemd services for all components                                                                                                      |

---

## System Architecture

```text
                              ┌───────────────┐
  ⏱ Celery Beat (2 min) ───▶ │ Celery Worker  │ ◀──┐
  (move_… + scan_…)            └───────┬────────┘    │
                                                       │
                              ┌────────────────────┐   │
                              │   PostgreSQL 17     │◀─┘
                              └────────────────────┘
                                              ▲
                                              │ Django ORM (ASGI)
🌐 HTTP/WebSocket Requests       ┌────────────────────┐
      ⇅ Nginx (HTTPS)           │      Django        │
                              │ (Daphne + Channels +│
                              │  AllAuth, GraphQL)  │
                              └────────────────────┘
                                              ▲
                                              │ Redis (Cache + Channels)
                                       ┌───────────────┐
                                       │    Browser     │
                                       │   (User Portal)│
                                       └───────────────┘
```

* **Daphne (ASGI)** serves HTTP & WebSocket (via Django Channels).
* **Celery** (worker + beat) handles background tasks (`move_and_process_files`, `scan_and_insert_by_file_key`) on a 2-minute schedule.
* **PostgreSQL 17** stores XMPR & RainMap records, subscription data, user profiles, logs.
* **Redis 7** acts as cache (pipeline locks, sessions) and Channels backend.
* **RabbitMQ 3** serves as the Celery broker.
* **Cloudflare Tunnel** provides TLS termination and optional WAF in production.

---

## Applications (Django Apps)

| **App**    | **Purpose**                                                               |
| ---------- | ------------------------------------------------------------------------- |
| **`main`** | • Site-wide pages: Landing, Dashboard, Live Radar, Profile, Activity Logs |

```
                   • Custom `SecurityMiddleware` for SQL injection detection, IP blocking, unauthorized access logging  
                   • `ProjectConfig` singleton for global site metadata                                                                                                                                        |
```

\| **`datasets`**      | • Models: `XmprData`, `XmprDownloadLog`
• XMPR Data Explorer view: date/year/month filters, pagination, multi-select ZIP download (streaming)
• CSV analysis endpoint (JSON) for on-the-fly statistics                                                                                                                                        |
\| **`processor`**     | • Models: `ProcessorXmprData`, `RainMapImage`, `RainMapDownloadLog`
• Celery tasks: `move_and_process_files`, `scan_and_insert_by_file_key`, `process_csv_file`
• RainMap Archive UI and download logic                                                                                                                                                |
\| **`subscriptions`** | • Models: `SubscriptionPackage`, `Subscription`
• Stripe integration: checkout, billing portal, webhook handling
• Subscription email notifications                                                                                                                                                                                                                  |
\| **`graphql`**       | • Graphene-Django schema exposing `latestXmprData(page, pageSize, date)` query for Live Radar
• Allows paginated fetching of radar frames via HTTP POST at `/graphql`                                                                                                                                    |
\| **`heroicons`**     | • Provides Heroicons template tags for UI icons                                                                                                                                                                                                                                                       |

---

## User Interfaces

### Super-Admin Panel

* **Theme**: DaisyUI-enhanced Django Admin with Heroicons, dark-mode friendly.
* **Features**:

  * Inline preview/download buttons for CSV, PNG, GeoTIFF, and JPEG files.
  * Download log inlines for each `XmprData` & `RainMapImage` (showing user, IP, timestamp).
  * `ProjectConfig` singleton enforces a single global instance (site name, short description, logo, favicon).
  * Audit trail: display `LogEntry` in user detail via inline (permission-based).

<div align="center">
  <img src="xris/static/img/admin_dashboard.png" alt="Admin Dashboard Example" width="80%" />
</div>

---

### User Portal

1. **Landing Page**

   * Hero section with title, subtitle, and action buttons (“Get Started Free” / “View Live Radar”).
   * “About XMPR” section explaining X-Band multiparameter radar concepts.
   * Image gallery carousel showcasing recent radar snapshots (controlled via Alpine.js).

2. **Dashboard (`/home`)**

   * Stat cards for subscription status, XMPR dataset count, XMPR download count, total downloaded size, RainMap count, recent activities.
   * Chart.js bar charts for download trends (last 7 days vs. last 30 days).
   * Lists of recent uploads/downloads (XMPR & RainMap).

3. **XMPR Data Explorer (`/datasets/xmpr_data`)**

   * Filterable and paginated table showing timestamp, CSV link, PNG preview, TIFF link, file size.
   * Multi-select checkboxes compute selected count and total size.
   * “Download Selected” (ZIP streaming) and “Analyze Selected” (AJAX → JSON → PDF report).
   * Alpine.js component manages selection state, size formatting, and limit validations.

4. **RainMap Archive (`/processor/rainmap_data`)**

   * Similar UX to XMPR Explorer: table of RainMap JPEGs with timestamp, preview, size.
   * Multi-select checkboxes with ZIP download for Premium users.

5. **Live Radar Map (`/main/live_radar`)**

   * MapLibre GL JS map centered on UTM Pagoh coordinates.
   * Alpine.js + GraphQL: fetches paginated radar frames (JSON: `id`, `time`, `png` URL).
   * Carousel of radar frames (10 per page) below the map; clicking a thumbnail toggles raster overlay.
   * Smooth map panning/zoom and responsive design.

6. **Subscription Page (`/subscriptions/`)**

   * Lists available packages (Free & Premium) with pricing and duration.
   * Stripe Checkout integration: create a Checkout Session and redirect the user.
   * Billing Portal button (Stripe portal) to manage payment method and cancellation.
   * Webhook handling for events: `checkout.session.completed`, `invoice.paid`, `customer.subscription.updated`, `invoice.payment_failed`, `customer.subscription.deleted`.

7. **Profile & Activity**

   * Profile form: update first/last name, email, avatar upload (live filename preview via JavaScript).
   * Activity Logs: paginated display of Django `LogEntry` for the current user, with date (naturaltime), action, object, and content type.

<div align="center">
  <img src="xris/static/img/user_dashboard.png" alt="User Dashboard Example" width="80%" />
</div>

---

## File & Folder Structure

```text
xris/                              # Project root
├── datasets/                      # XMPR models, views, admin, templates, GraphQL schema
├── processor/                     # Processing pipeline, Celery tasks, utilities, RainMap models, views, admin
├── main/                          # Core pages, custom middleware, forms, models, templates
├── subscriptions/                 # Subscription models, Stripe integration, webhook handlers, admin
├── graphql/                       # Graphene-Django schema (if separated from datasets/graphql)
├── templates/                     # Global templates (base.html, includes, partials)
├── static/                        # Collected static files (CSS, JS, images, Heroicons)
├── assets/                        # Uncollected custom assets (SCSS, raw icons)
├── media/                         # Uploaded & processed media files
│   ├── converted/                 # CSV → SSV → mesh → GeoTIFF/PNG outputs
│   ├── csv/                       # Raw CSV uploads
│   ├── images/                    # Processed images (PNG, TIFF)
│   │   ├── png/
│   │   └── tif/
│   ├── rainmaps/                  # RainMap JPEGs
│   └── temp/                      # Temporary working directory for Celery tasks
├── docker/                        # Docker-related files
│   ├── Dockerfile                 # Production multi-stage build
│   └── docker-compose.yml         # Services: web, db, redis, rabbitmq, flower
├── polar2mesh/                    # Native Fortran binary + LUTs for polar2mesh conversion
├── xris/                          # Django project directory
│   ├── __init__.py
│   ├── asgi.py                    # ASGI application (Daphne + Channels)
│   ├── settings.py                # All settings: environment, Redis, Channels, Celery, Stripe
│   ├── urls.py                    # URL routes, static/media serving
│   └── schema.py                  # Graphene GraphQL schema for `latestXmprData`
├── manage.py                      # Django management script
├── README.md                      # This file (enhanced)
├── requirements.txt               # Python dependencies
└── .env.sample                    # Sample environment variables
```

---

## Technology Stack

* **Backend**

  * **Django 5.2 (ASGI)** with **Daphne** and **Channels** for WebSocket support
  * **Graphene-Django** for GraphQL API
  * **PostgreSQL 17** as the relational database
  * **Redis 7** for caching, session storage, Channels layer, pipeline locks
  * **RabbitMQ 3** as the Celery broker

* **Frontend**

  * **Tailwind CSS** for utility-first styling
  * **Alpine.js (v3)** for lightweight component interactivity
  * **MapLibre GL JS** for vector map and raster overlays (Live Radar)
  * **Chart.js** for bar charts (download trends)
  * **html2canvas** + **jsPDF** for PDF report generation

* **Task Queue**

  * **Celery 5** (worker + beat) for background tasks
  * **Flower** for real-time task monitoring (port 5555)

* **Authentication & Billing**

  * **Django AllAuth** for email/password login and signup (mandatory email verification)
  * **Custom `User`** model (email as `USERNAME_FIELD`, avatar upload)
  * **Stripe Subscriptions API** (Free & Premium tiers) with webhook handlers

* **Security & Performance**

  * Custom **SecurityMiddleware** to detect SQL injection, block IPs, and log unauthorized access
  * CSRF and CORS configured via `HOST_URL`
  * HSTS, X-Frame-Options, X-Content-Type-Options enforced
  * **Redis-backed caching** for pipeline locking (2 min TTL), session caching, and query caching
  * File size & count limits (100 files / 500 MB per download; 100 MB upload limit)

* **Containerization & CI/CD**

  * **Docker Compose** for local & production stacks (web, db, redis, rabbitmq, flower)
  * **GitHub Actions** sample workflow for linting (pre-commit), tests (pytest), and build/push images

---

## Local & Docker Deployment

### Quick Start (Docker)

1. **Clone the repository**

   ```bash
   git clone https://github.com/utm-mjiit/xris.git
   cd xris
   ```

2. **Copy `.env.sample` → `.env`**

   ```bash
   cp .env.sample .env
   ```

   • Set `DJANGO_SECRET_KEY`, database credentials, Redis, Stripe keys, AWS (if needed), and `HOST_URL`.

3. **Build & start services**

   ```bash
   docker compose up --build -d
   ```

4. **Create a superuser (first time only)**

   ```bash
   docker compose exec web python manage.py createsuperuser
   ```

5. **Access**

   * **Web (Daphne)**: [http://localhost:8000](http://localhost:8000)
   * **Flower (Celery monitor)**: [http://localhost:5555](http://localhost:5555)

**Docker Compose Services**:

| Service      | Port(s)      | Description                                  |
| ------------ | ------------ | -------------------------------------------- |
| **web**      | 8000         | Daphne ASGI server (proxied by Nginx)        |
| **db**       | 5435         | PostgreSQL with persistent volume (`pgdata`) |
| **redis**    | 6379         | Cache & Channels layer                       |
| **rabbitmq** | 5672 / 15672 | Celery broker + management UI                |
| **flower**   | 5555         | Celery task monitoring                       |

---

### Bare-Metal Deployment (UTM Pagoh)

1. **Systemd Units**

   * `web.service` (Daphne + Gunicorn or standalone Daphne)
   * `celery.service` (Celery worker)
   * `celerybeat.service` (Celery beat scheduler)
   * `cloudflared.service` (Cloudflare Tunnel)

2. **Nginx Configuration**

   * Reverse-proxy traffic from HTTPS to `http://127.0.0.1:8000` (Daphne).
   * Enforce HSTS, X-Frame-Options, X-Content-Type-Options, and Content Security Policy as needed.

3. **Cloudflare Tunnel**

   * Run `cloudflared tunnel --url http://localhost:8000` as a systemd service.
   * Provides TLS termination, WAF, optional IP restriction for the public endpoint.

4. **Logrotate**

   * Rotate Django logs (e.g., `/var/log/xris/*.log`) on a daily or weekly schedule.

5. **PostgreSQL**

   * Install v17, configure user and database per `.env` values.
   * Listen on port `5435` (or standard `5432` if preferred).

6. **Redis**

   * Bind to `localhost` for caching.

7. **RabbitMQ**

   * Create a dedicated user with a strong password, configure vhost if needed.

8. **File Permissions**

   * Ensure `media/` and `static/` directories are writable by the Django process user (e.g., `www-data`).

---

## Environment Variables

Copy `.env.sample` to `.env` and fill in values. Below is a summary of available variables:

| **Variable**            | **Default**                     | **Description**                                                       |
| ----------------------- | ------------------------------- | --------------------------------------------------------------------- |
| `DJANGO_SECRET_KEY`     | *required*                      | Django cryptographic secret key                                       |
| `DEBUG`                 | `False`                         | Set to `True` for development; `False` for production                 |
| `HOST_URL`              | `http://localhost:8000`         | Base URL used for Stripe redirects, CSRF trusted origins, email links |
| `DATABASE_NAME`         | `xris`                          | PostgreSQL database name                                              |
| `DATABASE_USER`         | `postgres`                      | PostgreSQL user                                                       |
| `DATABASE_PASSWORD`     | `postgres`                      | PostgreSQL password                                                   |
| `DATABASE_HOST`         | `127.0.0.1` or `db` (Docker)    | PostgreSQL host (service name in Docker Compose)                      |
| `DATABASE_PORT`         | `5432` or `5435` (Docker)       | PostgreSQL port                                                       |
| `REDIS_HOST`            | `localhost` or `redis` (Docker) | Redis host (service name in Docker Compose)                           |
| `REDIS_PORT`            | `6379`                          | Redis port                                                            |
| `REDIS_DB`              | `0`                             | Redis database index                                                  |
| `EMAIL_HOST_USER`       | –                               | SMTP username (e.g., Gmail address)                                   |
| `EMAIL_HOST_PASSWORD`   | –                               | SMTP password                                                         |
| `EMAIL_FROM`            | –                               | “From” address used in outgoing emails                                |
| `STRIPE_SECRET_KEY`     | –                               | Live or Test Stripe secret key                                        |
| `STRIPE_WEBHOOK_SECRET` | –                               | Stripe webhook signing secret                                         |
| `POLAR2MESH_PATH`       | `polar2mesh/polar2mesh`         | Relative path to the `polar2mesh` binary                              |
| `S3_BUCKET`             | *optional*                      | AWS S3 bucket name (if using S3 for media storage)                    |
| `AWS_ACCESS_KEY_ID`     | *optional*                      | AWS access key ID (for S3)                                            |
| `AWS_SECRET_ACCESS_KEY` | *optional*                      | AWS secret access key (for S3)                                        |
| `REGION`                | *optional*                      | AWS region (for S3)                                                   |

---

## Celery Tasks & Automation

| **Task**                     | **Schedule / Trigger**                  | **Functionality**                                  |
| ---------------------------- | --------------------------------------- | -------------------------------------------------- |
| **`move_and_process_files`** | Scheduled every 2 minutes (Celery beat) | • Move raw CSVs from `/media/csv` to a temp folder |

```
                                                                  • Convert CSV → SSV (TranslateFormat) → mesh via `polar2mesh` → GeoTIFF (GDAL) + PNG (NumPy + `ascii2img`)  
                                                                  • Store outputs under `media/converted/` (organized by date)  
                                                                  • Log successes/failures—returns a summary list                                                                        |
```

\| **`scan_and_insert_by_file_key`**         | Chained after `move_and_process_files`                 | • Scan processed files by date subfolders
• Insert new `DatasetXmprData` & `ProcessorXmprData` records if absent
• Ingest RainMap JPEGs into `RainMapImage` table (skip duplicates)                                                                                                    |
\| **`process_csv_file(csv_relative_path)`**  | Invoked by `move_and_process_files` loop               | • Skip CSVs with < 10 data rows
• Convert CSV → SSV (TranslateFormat)
• Run `polar2mesh` to generate mesh file
• Convert mesh → GeoTIFF (GDAL)
• Convert mesh → color PNG (NumPy + `ascii2img`)
• Insert into `ProcessorXmprData` if new
• Cleanup temp files (via `file_delete`)                                                                                            |
\| **`trigger_xmpr_pipeline(force=False)`**  | Called in `/main/live_radar` & `/main/home` views      | • Uses Redis key `last_xmpr_pipeline_run` (120 s TTL) to prevent re-runs
• Acquires Redis lock `xmpr_pipeline_lock` (120 s TTL)
• Dispatches Celery task chain: `move_and_process_files` → `scan_and_insert_by_file_key`
• Returns `True` if tasks were dispatched, `False` otherwise                                                                     |
\| **`trigger_subscription_update`**         | Called in Dashboard view on each page load             | • Checks Stripe subscription statuses (via webhook updates)
• Marks expired subscriptions and sends notification emails
• Ensures user’s subscription state is kept up to date                                                                               |

* **Flower**: Access at `http://<host>:5555` for real-time task monitoring.

---

## Security & Hardening

1. **Custom `SecurityMiddleware`**

   * Detects SQL-injection patterns in request URLs (e.g., `SELECT`, `DROP`, `= =`, `'`, `--`)
   * Tracks suspicious attempts per IP (window of 1 hour) and blocks IPs for escalating durations (24 h, 48 h, 72 h)
   * Emits `unauthorized_access` signal for logging (IP, reverse DNS, location via `ipinfo.io`, user agent details, URL, reason)
   * On 403/404 responses (except for root), redirects to home and logs the event

2. **HTTP Security Headers**

   * **HSTS**: `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload`
   * **X-Frame-Options**: `DENY`
   * **X-Content-Type-Options**: `nosniff`
   * **Content-Security-Policy**: Recommended to configure in Nginx for stricter policies

3. **CSRF & CORS**

   * `CSRF_TRUSTED_ORIGINS` automatically populated from `HOST_URL`
   * `CorsMiddleware` restricts allowed methods and headers as required

4. **Authentication & Access Control**

   * All user downloads (XMPR, RainMap) require an **active Premium subscription**
   * Email verification is mandatory before login (`ACCOUNT_EMAIL_VERIFICATION = 'mandatory'`)
   * Celery pipeline triggers are rate-limited to once per 2 minutes via Redis

5. **Uploads & Limits**

   * `DATA_UPLOAD_MAX_MEMORY_SIZE` & `FILE_UPLOAD_MAX_MEMORY_SIZE` set to 100 MB
   * Form field limit: `DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000`
   * Download limits: maximum of 100 files or 500 MB total per batch

6. **Cloudflare Tunnel (Production)**

   * Provides TLS termination, IP whitelisting (optional), OWASP WAF, DDoS protection
   * Tunnel runs as a systemd service, mapping the public hostname to `localhost:8000`

---

## Development Workflow

```bash
# 1. Clone & Activate Virtual Environment
git clone git@github.com:saislamb97/xris-app.git
cd xris
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate

# 2. Install Dependencies
pip install -r requirements.txt

# 3. Copy & Configure Environment Variables
cp .env.sample .env
# Open .env and update required values:
# DJANGO_SECRET_KEY, DATABASE_*, REDIS_*, STRIPE_*, EMAIL_*, HOST_URL, etc.

# 4. Apply Migrations & Create Superuser
python manage.py migrate
python manage.py createsuperuser

# 5. Run Development Server (Daphne + Channels)
python manage.py runserver 0.0.0.0:8000

# 6. Start Celery (in separate terminals or via Docker Compose)
#    Worker
celery -A xris worker --loglevel=info
#    Beat
celery -A xris beat --scheduler django --loglevel=info
#    Flower (monitor)
celery -A xris flower --port=5555 --address=0.0.0.0

# 7. Linting & Formatting (if pre-commit is configured)
pre-commit run --all-files

# 8. Tests
pytest -q

# 9. GraphQL Playground
#    Visit: http://localhost:8000/graphql (via browser, GET)
```

* **Hot Reload**: Consider using `runserver_plus` (from `django-extensions`) for autoreload support.
* **GraphQL Playground**: Use tools like Altair or GraphiQL by navigating to `/graphql`.

---

## License

This project is © 2025 **XRIS / UTM Pagoh** and released under the [UTM License](LICENSE).

---

<p align="center">
  <em>Built with ♥ for researchers and engineers at <abbr title="Universiti Teknologi Malaysia">UTM</abbr></em>
</p>
