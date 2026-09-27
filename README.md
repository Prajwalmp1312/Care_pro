# CareConnect Health 

CareConnect is a unified healthcare and nutrition application:

- The React/Vite web application serves the CareConnect dashboard and integrated Meal Planner.
- One FastAPI service owns healthcare, authentication, nutrition, saved meal plans, weekly scheduling, cycle tracking, chat, and ingredient detection.
- One MySQL `careconnect_pro` schema stores application data.

Only two application servers are required: the web server and FastAPI. MySQL remains the database process.

## Quick start

The recommended way to run the complete application is Docker Desktop:

```powershell
Copy-Item .env.example .env
# Edit .env and replace MYSQL_ROOT_PASSWORD and CARECONNECT_SECRET_KEY.
docker compose up --build
```

When the containers are healthy, open `http://localhost:3000`. The API health
check is available at `http://localhost:8000/api/health` and interactive API
documentation at `http://localhost:8000/docs`.

For frontend or backend development with hot reload, follow
[Run locally](#run-locally).

## Architecture

```text
Browser: React/Vite UI on port 3000
        |
        `-- /api/* --> CareConnect FastAPI on port 8000
                       - authentication and users
                       - records, prescriptions, appointments
                       - messaging, notifications, and RAG
                       - /api/meal-planner/* nutrition routes
                       - shared patient authentication and context

MySQL: careconnect_pro
```

## Functionality

CareConnect includes patient, clinician, and administrator accounts; Google sign-in; clinician approval; medical-record extraction and version history; prescriptions; appointments; messaging; notifications; administration; AI summaries; RAG; and health chat.

The security foundation adds revocable server-side sessions, inactive-account
enforcement, role-scoped patient access, request throttling, security audit
events, hardened download authorization, and bounded uploads validated by file
extension and content signature. The clinical organization layer adds a
controlled record-category vocabulary, tags and clinical source dates,
role-scoped cross-resource search, category filters, and the patient health
timeline.

The security graph and its datastore `PROTECTED_BY` and
privileged-capability `PROTECTS` declarations are maintained in
[`security/agent-sbom.json`](security/agent-sbom.json).

Production deployments must use a non-root MySQL application account and set
`DB_SSL_CA` to a trusted CA certificate. Backend startup fails closed when
either requirement is missing.

On the first backend start after this update, SQLAlchemy creates the session and
security-audit tables and the startup migration adds classification columns and
indexes to existing medical records. Tokens issued by older releases do not
have a server-side session identifier, so users must sign in again once after
the update.

The integrated Meal Planner includes:

- safety-first mood, diet, cuisine, allergy, intolerance, dislike, budget, cooking-time, serving, and pantry preferences;
- Gemini meal generation with deterministic server-side allergen/diet validation and a safe fallback;
- Gemini image ingredient recognition with patient confirmation when configured;
- complete saved recipes, meal locking/swapping, weekly scheduling, grocery aggregation, completion tracking, private feedback, and owner-only deletion;
- nutrition profile, goals, activity level, and estimated calorie/macronutrient targets;
- menstrual-cycle settings, journal, dashboard, and pattern summaries;
- meal chat, voice mood detection, and CareConnect-aware authentication.

Clinicians can publish weekly consultation hours and choose 15, 30, 45, or
60-minute appointment slots. Patients see those hours and can select only open
future slots. Voice and typed prescriptions share one structured, reviewable
prescription workflow.

Each new prescription is linked into the clinician-patient conversation as a
structured message card. Connected clinicians can open a comprehensive patient
profile containing medical summaries, records, prescriptions, appointments,
current body-composition data, and longitudinal measurements. Administrators
can update demographics, status, vitals, and body composition; every update
archives the previous state in immutable profile history.

Approved video appointments use a consent-gated launch into
[Comm360](https://comm360.feeltiptop.com/). CareConnect enforces participant
access and a limited appointment window, records each authorized launch, and
does not place patient names, email addresses, or clinical details in the
external URL. Override the provider root with `COMM360_BASE_URL` when needed.
Appointment launch windows use `APPOINTMENT_TIMEZONE` (default
`America/Los_Angeles`); set it to the clinic's IANA time-zone name before
deployment.

Patient SOS uses a one-time safety disclosure followed by a one-tap alert.
CareConnect records consent, operational ownership, staff check-ins, escalation
levels, review deadlines, and response history. This workflow coordinates
notifications only; it does not automatically dispatch emergency services.
SOS records and response events are retained rather than deleted through the
application.
The FastAPI process checks deadlines in the background, while the staff
operations dashboard refreshes every 15 seconds. An administrator must still
define supported response hours, staffing coverage, and the external escalation
procedure before production use.
Repeated SOS activation escalates the existing open response instead of
creating competing unowned alerts.
If a patient activates SOS accidentally, the persistent false-alarm control
closes CareConnect monitoring, immediately notifies the response team, and
records the patient-confirmed outcome in the retained response history. It
does not delete the SOS record or cancel emergency services contacted outside
CareConnect.

Approved appointments automatically receive durable in-app reminder schedules
for 24 hours and 1 hour before the visit. A background monitor delivers each
reminder once, survives application restarts, and cancels pending reminders
when the appointment is no longer active.

Clinicians manage consultation availability from **Profile & Schedule** rather
than the Appointments page. Each weekday can contain multiple bookable
sessions plus labeled lunch, break, or administrative blocks. Breaks are
validated inside working hours and automatically removed from the appointment
slots offered to patients.

The Messages area contains conversations only. Patients use **Find Care** for
clinician discovery and request tracking, while clinicians use **Patient
Requests** to accept or decline new messaging connections.

Clinical summaries and AI report comparisons can be downloaded as a polished
PDF or an editable Word document. Both formats preserve the same role-based
authorization as the on-screen records, include clinical disclaimers, and are
returned with no-store download headers. Install the Python dependencies from
`services/careconnect/requirements.txt` before using document exports.

## Unified login flow

1. A patient signs in to CareConnect and receives the normal patient JWT.
2. Opening the Meal Planner calls `POST /api/meal-planner/careconnect/session` on the same FastAPI server.
3. FastAPI creates or loads the patient-owned nutrition profile in `careconnect_pro`.
4. All Meal Planner requests reuse the CareConnect JWT; there is no second user account, token, database, or internal HTTP call.

## Prerequisites

Choose one setup:

- **Docker setup (recommended):** Docker Desktop with Docker Compose.
- **Local development:** Python 3.11, Node.js 20+, npm, and MySQL 8.x.

Tesseract OCR is included in the backend Docker image. For local development,
install Tesseract separately if scanned-image OCR is required. Gemini and
Google sign-in credentials are optional; deterministic fallbacks remain
available without them.

## Run with Docker

Run every command in this section from the repository root:

```powershell
cd C:\TipTop\careconnect-suite
```

### 1. Create the Docker environment file

Copy the root template:

```powershell
Copy-Item .env.example .env
```

Open `.env` and replace these required values:

```env
MYSQL_ROOT_PASSWORD=a-strong-database-password
CARECONNECT_SECRET_KEY=a-long-random-careconnect-secret
```

Optional settings include:

```env
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
GOOGLE_CLIENT_ID=
DEFAULT_ADMIN_EMAIL=
DEFAULT_ADMIN_PASSWORD=
```

`GEMINI_API_KEY` enables live meal generation, meal chat, health tips, and
ingredient recognition. Without it, the application uses its safe fallback
workflows.

### 2. Build and start the application


```powershell
docker compose up --build
```

The first build downloads the MySQL, Python, Node, and Nginx dependencies and
can take several minutes. Leave this terminal running. To start in the
background instead, use:

```powershell
docker compose up --build -d
docker compose ps
```

### 3. Open and verify the application


- Web application: `http://localhost:3000`
- FastAPI documentation: `http://localhost:8000/docs`
- Health endpoint: `http://localhost:8000/api/health`

View logs when troubleshooting:

```powershell
docker compose logs -f careconnect web mysql
```

### 4. Stop the application

```powershell
docker compose down
```

This preserves MySQL and uploaded-file volumes. To intentionally erase all
Docker-managed application data and start clean, use `docker compose down -v`.
That command is destructive.

## Run locally

Use Python 3.11 (preferred, matching the backend Docker image) or Python 3.12.
Python 3.14 is not currently supported by every Chroma/Google/Protobuf
dependency and disables record-aware RAG at runtime.

Run the following commands from PowerShell. Keep the backend and frontend in
separate terminals.

### 1. Create the MySQL database

Start MySQL 8, then run:


```powershell
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS careconnect_pro CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

You can also execute [db/init.sql](db/init.sql) using MySQL Workbench.

### 2. Configure and start FastAPI

From the repository root:

```powershell
cd services/careconnect
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

If Python 3.11 is not installed, use `py -3.12 -m venv .venv`. Do not reuse a
virtual environment copied from another computer or Windows user; its
interpreter paths are machine-specific.

Edit `services/careconnect/.env` and set at least:

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your-mysql-password
DB_NAME=careconnect_pro
SECRET_KEY=replace-with-a-long-random-secret
ENVIRONMENT=development
FRONTEND_URL=http://localhost:3000
ALLOWED_ORIGINS=http://localhost:3000
```

Then start the API:

```powershell
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

On startup, FastAPI creates missing tables and applies additive schema updates.
Verify `http://localhost:8000/api/health` before starting the web application.

If PowerShell blocks virtual-environment activation, run commands through the
environment's interpreter instead:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### 3. Configure and start the React application

Open a second PowerShell terminal at the repository root:

```powershell
cd apps/web
npm ci
npm run dev
```

Vite serves `http://localhost:3000` and proxies all `/api` requests to FastAPI.

### 4. Stop local services

Press `Ctrl+C` in the frontend and backend terminals. Stop MySQL separately if
it is not managed as a Windows service.

## Environment-file reference

Docker and local development intentionally use different variable names for
their database password and JWT secret:

| Purpose | Docker root `.env` | Local `services/careconnect/.env` |
| --- | --- | --- |
| MySQL password | `MYSQL_ROOT_PASSWORD` | `DB_PASSWORD` |
| JWT signing secret | `CARECONNECT_SECRET_KEY` | `SECRET_KEY` |
| Gemini key | `GEMINI_API_KEY` | `GEMINI_API_KEY` |
| Gemini model | `GEMINI_MODEL` | `GEMINI_MODEL` |

Do not commit either populated `.env` file.

## First Meal Planner use

The first time a patient opens Meal Planner, FastAPI creates linked nutrition settings with conservative defaults. Patients manage weight, height, goals, allergies, and meal preferences from the single CareConnect profile; Meal Planner reads those shared settings automatically.


## Mobile application

The native Expo application lives in `apps/mobile` and runs alongside the existing web app. It uses the same FastAPI authentication, permissions, records, appointments, notifications, and database. See `apps/mobile/README.md` for emulator, physical-device, and build instructions.

Production preparation, external approval gates, clinical/privacy working
documents, and the release runbook are tracked in
[`MARKET_READINESS.md`](MARKET_READINESS.md) and
[`docs/market-readiness`](docs/market-readiness). These gates intentionally
remain open until legal, clinical, security, infrastructure, and app-store
owners attach review evidence.

## Project layout

```text
careconnect-suite/
|-- apps/web/                         # Combined React UI
|   `-- src/meal-planner/             # Meal Planner screens
|-- services/careconnect/             # Unified FastAPI backend
|   |-- main.py
|   `-- meal_planner.py               # Integrated nutrition routes
|-- db/init.sql
|-- docker-compose.yml
|-- .env.example
`-- README.md
```

## Verify the installation

Run the backend test suite:

```powershell
cd services/careconnect
.\.venv\Scripts\python.exe -m unittest discover tests -v
```

Run the production frontend build:

```powershell
cd apps/web
npm run build
```

Check a running backend from PowerShell:

```powershell
Invoke-RestMethod http://localhost:8000/api/health
```



The application now uses one FastAPI service, one React application, one MySQL
schema, and one CareConnect profile per user. No separate Meal Planner server,
login, token, or profile process is required.
