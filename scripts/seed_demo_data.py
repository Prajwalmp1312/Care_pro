"""Create a coherent, fictional CareConnect dataset for local testing.

The seeder owns only accounts whose email address starts with ``demo.`` and
ends with ``@careconnect.test``. Re-running it removes and recreates that
namespace, so the result is predictable without changing normal application
accounts.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import textwrap
import types
import urllib.error
import urllib.request
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICE_DIR = REPO_ROOT / "services" / "careconnect"
sys.path.insert(0, str(SERVICE_DIR))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv  # noqa: E402

load_dotenv(SERVICE_DIR / ".env", override=False)
load_dotenv(REPO_ROOT / ".env", override=False)

try:  # noqa: E402
    import bcrypt as bcrypt_module
except (ImportError, ModuleNotFoundError):
    # Some copied Windows virtual environments contain pure-Python packages
    # but not the interpreter-specific bcrypt extension. Keep database.py
    # importable; password_hash() below uses the running development API only
    # as a local fallback in that unusual environment.
    bcrypt_module = None
    bcrypt_stub = types.ModuleType("bcrypt")

    def _bcrypt_unavailable(*_args, **_kwargs):
        raise RuntimeError("The bcrypt native extension is unavailable")

    bcrypt_stub.hashpw = _bcrypt_unavailable
    bcrypt_stub.gensalt = _bcrypt_unavailable
    bcrypt_stub.checkpw = _bcrypt_unavailable
    sys.modules["bcrypt"] = bcrypt_stub

# PyMySQL treats cryptography as optional for the normal MariaDB password
# exchange. A copied virtual environment can contain an incompatible native
# cryptography build, which raises AttributeError instead of ImportError during
# discovery; hide only that broken optional package so PyMySQL can use its
# standard pure-Python authentication path.
try:
    from cryptography.hazmat.primitives import hashes as _crypto_probe  # noqa: F401
except Exception:
    for module_name in [
        name for name in sys.modules if name == "cryptography" or name.startswith("cryptography.")
    ]:
        sys.modules.pop(module_name, None)
    sys.modules["cryptography"] = None

from sqlalchemy import or_, text  # noqa: E402

from database import (  # noqa: E402
    SessionLocal,
    engine,
    ensure_existing_schema_columns,
    ensure_messages_is_edited_column,
)
from models import (  # noqa: E402
    Admin,
    AdminAuditLog,
    Appointment,
    AppointmentReminder,
    ChatAttachment,
    Clinician,
    ClinicianJoinRequest,
    EmergencyAlert,
    EmergencyAlertEvent,
    MedicalRecord,
    MedicalRecordVersion,
    Message,
    MessageRequest,
    Notification,
    Patient,
    PatientProfileHistory,
    Prescription,
    SecurityAuditEvent,
    UserConsent,
    UserSession,
    VideoConsultationEvent,
    Base,
)


DEMO_DOMAIN = "@careconnect.test"
DEMO_PASSWORD = os.getenv("CARECONNECT_DEMO_PASSWORD", "CareConnectDemo!2026")
UPLOAD_DIR = SERVICE_DIR / "uploads" / "demo-seed"
CONSENT_VERSION = "2026-07"

PATIENTS = [
    {
        "key": "aisha",
        "name": "Aisha Patel",
        "email": f"demo.aisha{DEMO_DOMAIN}",
        "gender": "female",
        "age": 34,
        "blood_type": "O+",
        "phone": "(555) 010-1001",
        "address": "1847 Cedar Lane, Brookfield, CA 90210",
        "emergency_contact": "Rohan Patel · (555) 010-1901",
        "status": "stable",
        "alerts": 0,
        "weight_kg": 64.8,
        "height_cm": 165.0,
        "body_fat_percentage": 26.1,
        "muscle_mass_kg": 24.7,
        "waist_cm": 76.0,
        "systolic_bp": 118,
        "diastolic_bp": 76,
        "created_days_ago": 118,
    },
    {
        "key": "daniel",
        "name": "Daniel Brooks",
        "email": f"demo.daniel{DEMO_DOMAIN}",
        "gender": "male",
        "age": 58,
        "blood_type": "A+",
        "phone": "(555) 010-1002",
        "address": "92 Harbor View Drive, Brookfield, CA 90210",
        "emergency_contact": "Nora Brooks · (555) 010-1902",
        "status": "attention",
        "alerts": 2,
        "weight_kg": 91.2,
        "height_cm": 178.0,
        "body_fat_percentage": 29.4,
        "muscle_mass_kg": 31.8,
        "waist_cm": 104.0,
        "systolic_bp": 142,
        "diastolic_bp": 88,
        "created_days_ago": 76,
    },
    {
        "key": "sofia",
        "name": "Sofia Ramirez",
        "email": f"demo.sofia{DEMO_DOMAIN}",
        "gender": "female",
        "age": 42,
        "blood_type": "B+",
        "phone": "(555) 010-1003",
        "address": "311 Magnolia Avenue, Lakeside, CA 92040",
        "emergency_contact": "Elena Ramirez · (555) 010-1903",
        "status": "stable",
        "alerts": 0,
        "weight_kg": 68.5,
        "height_cm": 168.0,
        "body_fat_percentage": 27.8,
        "muscle_mass_kg": 25.4,
        "waist_cm": 79.0,
        "systolic_bp": 116,
        "diastolic_bp": 74,
        "created_days_ago": 42,
    },
    {
        "key": "marcus",
        "name": "Marcus Lee",
        "email": f"demo.marcus{DEMO_DOMAIN}",
        "gender": "male",
        "age": 29,
        "blood_type": "O-",
        "phone": "(555) 010-1004",
        "address": "740 Willow Street, Lakeside, CA 92040",
        "emergency_contact": "Grace Lee · (555) 010-1904",
        "status": "stable",
        "alerts": 0,
        "weight_kg": 79.6,
        "height_cm": 183.0,
        "body_fat_percentage": 17.2,
        "muscle_mass_kg": 36.9,
        "waist_cm": 84.0,
        "systolic_bp": 122,
        "diastolic_bp": 78,
        "created_days_ago": 24,
    },
    {
        "key": "evelyn",
        "name": "Evelyn Carter",
        "email": f"demo.evelyn{DEMO_DOMAIN}",
        "gender": "female",
        "age": 71,
        "blood_type": "A-",
        "phone": "(555) 010-1005",
        "address": "18 Sunrise Court, Seaview, CA 92109",
        "emergency_contact": "Thomas Carter · (555) 010-1905",
        "status": "critical",
        "alerts": 3,
        "weight_kg": 72.3,
        "height_cm": 160.0,
        "body_fat_percentage": 34.2,
        "muscle_mass_kg": 21.1,
        "waist_cm": 96.0,
        "systolic_bp": 166,
        "diastolic_bp": 94,
        "created_days_ago": 13,
    },
    {
        "key": "noah",
        "name": "Noah Williams",
        "email": f"demo.noah{DEMO_DOMAIN}",
        "gender": "male",
        "age": 12,
        "blood_type": "AB+",
        "phone": "(555) 010-1006",
        "address": "506 Garden Walk, Seaview, CA 92109",
        "emergency_contact": "Amelia Williams (parent) · (555) 010-1906",
        "status": "stable",
        "alerts": 0,
        "weight_kg": 44.1,
        "height_cm": 154.0,
        "body_fat_percentage": 18.0,
        "muscle_mass_kg": 18.6,
        "waist_cm": 67.0,
        "systolic_bp": 108,
        "diastolic_bp": 66,
        "created_days_ago": 5,
    },
]

CLINICIANS = [
    {
        "key": "maya",
        "name": "Dr. Maya Chen",
        "email": f"demo.maya.chen{DEMO_DOMAIN}",
        "gender": "female",
        "specialization": "Family Medicine",
        "license_number": "DEMO-CA-FM-1042",
        "phone": "(555) 010-2101",
        "department": "Primary Care",
        "years_of_experience": 12,
        "duration": 30,
        "days": ["monday", "wednesday", "friday"],
        "start": "09:00",
        "end": "16:00",
        "breaks": [
            {"label": "Lunch", "start": "12:00", "end": "12:45"},
            {"label": "Break", "start": "14:30", "end": "14:45"},
        ],
        "approval_status": "approved",
        "created_days_ago": 135,
    },
    {
        "key": "liam",
        "name": "Dr. Liam Anderson",
        "email": f"demo.liam.anderson{DEMO_DOMAIN}",
        "gender": "male",
        "specialization": "Cardiology",
        "license_number": "DEMO-CA-CD-2088",
        "phone": "(555) 010-2102",
        "department": "Cardiovascular Medicine",
        "years_of_experience": 18,
        "duration": 30,
        "days": ["tuesday", "thursday", "friday"],
        "start": "08:30",
        "end": "14:30",
        "breaks": [
            {"label": "Lunch", "start": "11:30", "end": "12:00"},
        ],
        "approval_status": "approved",
        "created_days_ago": 96,
    },
    {
        "key": "priya",
        "name": "Dr. Priya Nair",
        "email": f"demo.priya.nair{DEMO_DOMAIN}",
        "gender": "female",
        "specialization": "Neurology",
        "license_number": "DEMO-CA-NE-3165",
        "phone": "(555) 010-2103",
        "department": "Neurosciences",
        "years_of_experience": 10,
        "duration": 45,
        "days": ["monday", "tuesday", "thursday"],
        "start": "10:00",
        "end": "17:00",
        "breaks": [
            {"label": "Lunch", "start": "13:00", "end": "14:00"},
        ],
        "approval_status": "approved",
        "created_days_ago": 39,
    },
    {
        "key": "james",
        "name": "Dr. James Wilson",
        "email": f"demo.james.wilson{DEMO_DOMAIN}",
        "gender": "male",
        "specialization": "Orthopedics",
        "license_number": "DEMO-CA-OR-4117",
        "phone": "(555) 010-2104",
        "department": "Musculoskeletal Care",
        "years_of_experience": 15,
        "duration": 30,
        "days": ["tuesday", "wednesday", "saturday"],
        "start": "08:00",
        "end": "13:00",
        "breaks": [
            {"label": "Break", "start": "10:15", "end": "10:30"},
        ],
        "approval_status": "approved",
        "created_days_ago": 21,
    },
    {
        "key": "helen",
        "name": "Dr. Helen Ross",
        "email": f"demo.helen.ross{DEMO_DOMAIN}",
        "gender": "female",
        "specialization": "Emergency Medicine",
        "license_number": "DEMO-CA-EM-5190",
        "phone": "(555) 010-2105",
        "department": "Urgent Care",
        "years_of_experience": 8,
        "duration": 30,
        "days": ["monday", "thursday"],
        "start": "12:00",
        "end": "18:00",
        "breaks": [
            {"label": "Lunch", "start": "15:00", "end": "15:30"},
        ],
        "approval_status": "pending",
        "created_days_ago": 3,
    },
]

ADMIN_EMAIL = f"demo.admin{DEMO_DOMAIN}"
DEMO_EMAILS = [item["email"] for item in PATIENTS + CLINICIANS] + [ADMIN_EMAIL]


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def appointment_timezone() -> ZoneInfo:
    name = os.getenv("APPOINTMENT_TIMEZONE", "America/Los_Angeles").strip()
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def local_now() -> datetime:
    return datetime.now(appointment_timezone())


def iso_date(days_from_today: int) -> str:
    return (local_now().date() + timedelta(days=days_from_today)).isoformat()


def next_weekday(weekday: int, weeks_ahead: int = 0) -> date:
    today = local_now().date()
    offset = (weekday - today.weekday()) % 7
    if offset == 0:
        offset = 7
    return today + timedelta(days=offset + (weeks_ahead * 7))


def consultation_hours(item: dict[str, Any]) -> str:
    value = {
        day: (
            [{"start": item["start"], "end": item["end"]}]
            if day in item["days"]
            else []
        )
        for day in [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ]
    }
    return json.dumps(value)


def consultation_breaks(item: dict[str, Any]) -> str:
    value = {
        day: item.get("breaks", []) if day in item["days"] else []
        for day in [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ]
    }
    return json.dumps(value)


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True)


def ensure_multi_medicine_column() -> None:
    with engine.begin() as connection:
        exists = connection.execute(
            text(
                "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='prescriptions' "
                "AND COLUMN_NAME='medicines_json'"
            )
        ).scalar()
        if not exists:
            connection.execute(
                text(
                    "ALTER TABLE prescriptions "
                    "ADD COLUMN medicines_json LONGTEXT NULL"
                )
            )


def ensure_meal_planner_schema() -> None:
    statements = [
        """
        CREATE TABLE IF NOT EXISTS meal_planner_profiles (
          patient_id INT PRIMARY KEY,
          username VARCHAR(255) UNIQUE NOT NULL,
          weight DECIMAL(6,2) NOT NULL DEFAULT 70,
          weight_unit VARCHAR(3) NOT NULL DEFAULT 'kg',
          purpose VARCHAR(255) NOT NULL DEFAULT 'Improve Health',
          profile_completed BOOLEAN NOT NULL DEFAULT FALSE,
          track_menstrual_cycle BOOLEAN NOT NULL DEFAULT FALSE,
          last_period_date DATE NULL,
          cycle_length INT NOT NULL DEFAULT 28,
          menstrual_preferences JSON NULL,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          CONSTRAINT fk_meal_profile_patient FOREIGN KEY (patient_id)
            REFERENCES patients(id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS saved_meal_plans (
          id INT AUTO_INCREMENT PRIMARY KEY,
          patient_id INT NOT NULL,
          meal_plan_name VARCHAR(255) DEFAULT 'My Meal Plan',
          mood_context VARCHAR(50) NOT NULL,
          breakfast_name VARCHAR(255) NOT NULL,
          breakfast_calories INT NOT NULL,
          lunch_name VARCHAR(255) NOT NULL,
          lunch_calories INT NOT NULL,
          dinner_name VARCHAR(255) NOT NULL,
          dinner_calories INT NOT NULL,
          snack_name VARCHAR(255) NOT NULL,
          snack_calories INT NOT NULL,
          total_calories INT NOT NULL,
          date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          INDEX idx_saved_plan_patient (patient_id),
          CONSTRAINT fk_saved_plan_patient FOREIGN KEY (patient_id)
            REFERENCES patients(id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS meal_planner_reviews (
          id INT AUTO_INCREMENT PRIMARY KEY,
          patient_id INT NOT NULL,
          name VARCHAR(255) NOT NULL,
          content TEXT NOT NULL,
          rating INT NOT NULL,
          photo_url VARCHAR(500) NULL,
          photo_filename VARCHAR(255) NULL,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          CONSTRAINT fk_meal_review_patient FOREIGN KEY (patient_id)
            REFERENCES patients(id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS menstrual_cycle_logs (
          id INT AUTO_INCREMENT PRIMARY KEY,
          patient_id INT NOT NULL,
          period_start_date DATE NULL,
          period_end_date DATE NULL,
          cravings JSON NULL,
          symptoms JSON NULL,
          notes TEXT NULL,
          log_date DATE NOT NULL,
          mood VARCHAR(50) NULL,
          energy_level VARCHAR(50) NULL,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          UNIQUE KEY unique_patient_log_date (patient_id, log_date),
          CONSTRAINT fk_cycle_log_patient FOREIGN KEY (patient_id)
            REFERENCES patients(id) ON DELETE CASCADE
        )
        """,
    ]
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def ensure_application_schema() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_messages_is_edited_column()
    ensure_existing_schema_columns()
    ensure_multi_medicine_column()
    ensure_meal_planner_schema()


def is_production() -> bool:
    return os.getenv("ENVIRONMENT", "development").strip().lower() == "production"


def password_hash(db) -> str:
    configured_hash = os.getenv("CARECONNECT_DEMO_PASSWORD_HASH", "").strip()
    if configured_hash:
        return configured_hash
    if bcrypt_module is not None:
        return bcrypt_module.hashpw(
            DEMO_PASSWORD.encode("utf-8")[:72],
            bcrypt_module.gensalt(),
        ).decode("utf-8")

    # Local compatibility fallback: ask the already-running development API
    # to create exactly one temporary account, then reuse its bcrypt hash.
    # The plaintext password never enters the database or command output.
    # email-validator rejects special-use TLDs during registration, so the
    # temporary bootstrap account uses the reserved example.com domain.
    temporary_email = "demo.careconnect.seed@example.com"
    db.query(Patient).filter(Patient.email == temporary_email).delete(
        synchronize_session=False
    )
    db.commit()
    payload = json.dumps(
        {
            "name": "Demo Seeder Temporary Account",
            "email": temporary_email,
            "password": DEMO_PASSWORD,
            "role": "patient",
            "gender": "prefer_not_to_say",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        os.getenv(
            "CARECONNECT_DEMO_API_URL",
            "http://127.0.0.1:8000/api/auth/register",
        ),
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status not in {200, 201}:
                raise RuntimeError(
                    f"Demo password bootstrap returned HTTP {response.status}"
                )
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(
            "bcrypt is unavailable in this Python environment and the local "
            "FastAPI registration endpoint could not be reached. Activate the "
            "backend Python 3.11 environment, or set CARECONNECT_DEMO_PASSWORD_HASH."
        ) from exc
    db.expire_all()
    temporary = (
        db.query(Patient).filter(Patient.email == temporary_email).first()
    )
    if not temporary or not temporary.hashed_password:
        raise RuntimeError("Could not retrieve the temporary demo password hash")
    value = temporary.hashed_password
    db.delete(temporary)
    db.commit()
    return value


def write_simple_pdf(path: Path, title: str, lines: list[str]) -> None:
    """Write a small dependency-free PDF suitable for download/view testing."""

    def escape(value: str) -> str:
        ascii_value = value.encode("ascii", "replace").decode("ascii")
        return ascii_value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    wrapped: list[str] = []
    for line in lines:
        wrapped.extend(textwrap.wrap(str(line), width=88) or [""])
    commands = [
        "BT",
        "/F1 16 Tf",
        "54 742 Td",
        f"({escape(title)}) Tj",
        "0 -28 Td",
        "/F1 10 Tf",
    ]
    for line in wrapped[:48]:
        commands.extend([f"({escape(line)}) Tj", "0 -14 Td"])
    commands.append("ET")
    stream = "\n".join(commands).encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n"
        + stream
        + b"\nendstream",
    ]
    chunks = [b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"]
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(sum(len(chunk) for chunk in chunks))
        chunks.append(
            f"{number} 0 obj\n".encode("ascii") + obj + b"\nendobj\n"
        )
    xref_offset = sum(len(chunk) for chunk in chunks)
    chunks.append(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    chunks.append(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        chunks.append(f"{offset:010d} 00000 n \n".encode("ascii"))
    chunks.append(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join(chunks))


def delete_demo_rows(db) -> None:
    patient_emails = [item["email"] for item in PATIENTS]
    clinician_emails = [item["email"] for item in CLINICIANS]
    patients = db.query(Patient).filter(Patient.email.in_(patient_emails)).all()
    patient_ids = [item.id for item in patients]
    appointments = (
        db.query(Appointment)
        .filter(
            or_(
                Appointment.patient_email.in_(patient_emails),
                Appointment.clinician_email.in_(clinician_emails),
            )
        )
        .all()
    )
    appointment_ids = [item.id for item in appointments]
    alerts = (
        db.query(EmergencyAlert)
        .filter(EmergencyAlert.patient_email.in_(patient_emails))
        .all()
    )
    alert_ids = [item.id for item in alerts]
    records = (
        db.query(MedicalRecord)
        .filter(MedicalRecord.patient_email.in_(patient_emails))
        .all()
    )
    record_ids = [item.id for item in records]
    messages = (
        db.query(Message)
        .filter(
            or_(
                Message.sender_email.in_(DEMO_EMAILS),
                Message.recipient_email.in_(DEMO_EMAILS),
            )
        )
        .all()
    )
    message_ids = [item.id for item in messages]

    if appointment_ids:
        db.query(AppointmentReminder).filter(
            AppointmentReminder.appointment_id.in_(appointment_ids)
        ).delete(synchronize_session=False)
        db.query(VideoConsultationEvent).filter(
            VideoConsultationEvent.appointment_id.in_(appointment_ids)
        ).delete(synchronize_session=False)
    if alert_ids:
        db.query(EmergencyAlertEvent).filter(
            EmergencyAlertEvent.alert_id.in_(alert_ids)
        ).delete(synchronize_session=False)
    if record_ids:
        db.query(MedicalRecordVersion).filter(
            MedicalRecordVersion.record_id.in_(record_ids)
        ).delete(synchronize_session=False)
    if message_ids:
        db.query(ChatAttachment).filter(
            ChatAttachment.message_id.in_(message_ids)
        ).delete(synchronize_session=False)

    db.query(ChatAttachment).filter(
        or_(
            ChatAttachment.sender_email.in_(DEMO_EMAILS),
            ChatAttachment.recipient_email.in_(DEMO_EMAILS),
        )
    ).delete(synchronize_session=False)
    db.query(Message).filter(
        or_(
            Message.sender_email.in_(DEMO_EMAILS),
            Message.recipient_email.in_(DEMO_EMAILS),
        )
    ).delete(synchronize_session=False)
    db.query(Notification).filter(
        Notification.user_email.in_(DEMO_EMAILS)
    ).delete(synchronize_session=False)
    db.query(UserConsent).filter(
        UserConsent.user_email.in_(DEMO_EMAILS)
    ).delete(synchronize_session=False)
    db.query(UserSession).filter(UserSession.user_email.in_(DEMO_EMAILS)).delete(
        synchronize_session=False
    )
    db.query(SecurityAuditEvent).filter(
        or_(
            SecurityAuditEvent.actor_email.in_(DEMO_EMAILS),
            SecurityAuditEvent.patient_email.in_(patient_emails),
        )
    ).delete(synchronize_session=False)
    db.query(AdminAuditLog).filter(
        or_(
            AdminAuditLog.admin_email.in_(DEMO_EMAILS),
            AdminAuditLog.target_email.in_(DEMO_EMAILS),
        )
    ).delete(synchronize_session=False)
    db.query(MedicalRecord).filter(
        MedicalRecord.patient_email.in_(patient_emails)
    ).delete(synchronize_session=False)
    db.query(Prescription).filter(
        or_(
            Prescription.patient_email.in_(patient_emails),
            Prescription.clinician_email.in_(clinician_emails),
        )
    ).delete(synchronize_session=False)
    db.query(MessageRequest).filter(
        or_(
            MessageRequest.patient_email.in_(patient_emails),
            MessageRequest.clinician_email.in_(clinician_emails),
        )
    ).delete(synchronize_session=False)
    db.query(Appointment).filter(
        or_(
            Appointment.patient_email.in_(patient_emails),
            Appointment.clinician_email.in_(clinician_emails),
        )
    ).delete(synchronize_session=False)
    db.query(EmergencyAlert).filter(
        EmergencyAlert.patient_email.in_(patient_emails)
    ).delete(synchronize_session=False)
    if patient_ids:
        db.query(PatientProfileHistory).filter(
            PatientProfileHistory.patient_id.in_(patient_ids)
        ).delete(synchronize_session=False)
        for table_name in (
            "menstrual_cycle_logs",
            "meal_planner_reviews",
            "saved_meal_plans",
            "meal_planner_profiles",
        ):
            for patient_id in patient_ids:
                db.execute(
                    text(f"DELETE FROM {table_name} WHERE patient_id=:patient_id"),
                    {"patient_id": patient_id},
                )
    db.query(ClinicianJoinRequest).filter(
        ClinicianJoinRequest.email.like(f"demo.%{DEMO_DOMAIN}")
    ).delete(synchronize_session=False)
    db.query(Patient).filter(Patient.email.in_(patient_emails)).delete(
        synchronize_session=False
    )
    db.query(Clinician).filter(Clinician.email.in_(clinician_emails)).delete(
        synchronize_session=False
    )
    db.query(Admin).filter(Admin.email == ADMIN_EMAIL).delete(
        synchronize_session=False
    )
    db.flush()


def seed_accounts(db, password_hash: str):
    now = utc_now()
    patients: dict[str, Patient] = {}
    for item in PATIENTS:
        patient = Patient(
            name=item["name"],
            email=item["email"],
            hashed_password=password_hash,
            role="patient",
            gender=item["gender"],
            is_active=True,
            email_verified=True,
            created_at=now - timedelta(days=item["created_days_ago"]),
            age=item["age"],
            blood_type=item["blood_type"],
            phone=item["phone"],
            address=item["address"],
            emergency_contact=item["emergency_contact"],
            last_visit=now - timedelta(days=7 + item["created_days_ago"] % 18),
            status=item["status"],
            alerts=item["alerts"],
            weight_kg=item["weight_kg"],
            height_cm=item["height_cm"],
            body_fat_percentage=item["body_fat_percentage"],
            muscle_mass_kg=item["muscle_mass_kg"],
            waist_cm=item["waist_cm"],
            systolic_bp=item["systolic_bp"],
            diastolic_bp=item["diastolic_bp"],
        )
        db.add(patient)
        patients[item["key"]] = patient

    clinicians: dict[str, Clinician] = {}
    for item in CLINICIANS:
        approved = item["approval_status"] == "approved"
        clinician = Clinician(
            name=item["name"],
            email=item["email"],
            hashed_password=password_hash,
            role="clinician",
            gender=item["gender"],
            is_active=True,
            email_verified=True,
            created_at=now - timedelta(days=item["created_days_ago"]),
            specialization=item["specialization"],
            license_number=item["license_number"],
            phone=item["phone"],
            department=item["department"],
            years_of_experience=item["years_of_experience"],
            consultation_hours=consultation_hours(item),
            consultation_breaks=consultation_breaks(item),
            consultation_duration_minutes=item["duration"],
            approval_status=item["approval_status"],
            approved_by=ADMIN_EMAIL if approved else None,
            approved_at=now - timedelta(days=max(item["created_days_ago"] - 2, 1))
            if approved
            else None,
        )
        db.add(clinician)
        clinicians[item["key"]] = clinician

    admin = Admin(
        name="Morgan Reed",
        email=ADMIN_EMAIL,
        hashed_password=password_hash,
        role="admin",
        is_active=True,
        email_verified=True,
        created_at=now - timedelta(days=180),
        access_level="full",
        department="Clinical Operations",
        phone="(555) 010-3001",
    )
    db.add(admin)
    db.flush()
    return patients, clinicians, admin


def seed_profile_history(db, patients: dict[str, Patient]) -> None:
    now = utc_now()
    reasons = [
        "Initial intake measurement",
        "Quarterly wellness review",
        "Care-plan follow-up",
        "Latest admin-verified measurement",
    ]
    ages = [180, 120, 60, 30]
    for item in PATIENTS:
        patient = patients[item["key"]]
        for index, days_ago in enumerate(ages):
            progress = index / max(len(ages) - 1, 1)
            weight_offset = (1.8 - (3.1 * progress)) if item["key"] == "daniel" else (
                0.8 - (1.0 * progress)
            )
            systolic_offset = (
                int(10 - (8 * progress))
                if item["key"] == "daniel"
                else int(4 - (3 * progress))
            )
            db.add(
                PatientProfileHistory(
                    patient_id=patient.id,
                    name=patient.name,
                    age=max((patient.age or 1) - (1 if days_ago > 150 else 0), 1),
                    gender=patient.gender,
                    blood_type=patient.blood_type,
                    phone=patient.phone,
                    address=patient.address,
                    emergency_contact=patient.emergency_contact,
                    status=(
                        "attention"
                        if item["key"] in {"daniel", "evelyn"}
                        else patient.status
                    ),
                    alerts=max((patient.alerts or 0) - (1 if index < 3 else 0), 0),
                    weight_kg=round((patient.weight_kg or 0) + weight_offset, 1),
                    height_cm=patient.height_cm,
                    body_fat_percentage=round(
                        (patient.body_fat_percentage or 0) + weight_offset * 0.35,
                        1,
                    ),
                    muscle_mass_kg=round(
                        (patient.muscle_mass_kg or 0) - weight_offset * 0.08,
                        1,
                    ),
                    waist_cm=round((patient.waist_cm or 0) + weight_offset * 0.9, 1),
                    systolic_bp=(patient.systolic_bp or 0) + systolic_offset,
                    diastolic_bp=(patient.diastolic_bp or 0)
                    + max(systolic_offset // 2, 0),
                    change_reason=reasons[index],
                    recorded_by=ADMIN_EMAIL,
                    recorded_at=now - timedelta(days=days_ago),
                )
            )


def seed_connections(db) -> None:
    now = utc_now()
    rows = [
        ("aisha", "maya", "accepted", 112),
        ("daniel", "maya", "accepted", 74),
        ("daniel", "liam", "accepted", 68),
        ("sofia", "priya", "accepted", 40),
        ("marcus", "james", "accepted", 23),
        ("evelyn", "liam", "accepted", 12),
        ("noah", "maya", "accepted", 5),
        ("aisha", "priya", "pending", 2),
        ("marcus", "maya", "rejected", 17),
    ]
    patient_by_key = {item["key"]: item for item in PATIENTS}
    clinician_by_key = {item["key"]: item for item in CLINICIANS}
    for patient_key, clinician_key, status, days_ago in rows:
        requested_at = now - timedelta(days=days_ago)
        db.add(
            MessageRequest(
                patient_email=patient_by_key[patient_key]["email"],
                clinician_email=clinician_by_key[clinician_key]["email"],
                status=status,
                requested_at=requested_at,
                responded_at=(
                    requested_at + timedelta(hours=6)
                    if status != "pending"
                    else None
                ),
            )
        )


def seed_appointments(db) -> dict[str, Appointment]:
    now = utc_now()
    current_local = local_now()
    live_start = current_local + timedelta(minutes=15)
    patient = {item["key"]: item["email"] for item in PATIENTS}
    clinician = {item["key"]: item["email"] for item in CLINICIANS}
    rows = [
        {
            "key": "video_live",
            "patient": "daniel",
            "clinician": "maya",
            "date": live_start.date().isoformat(),
            "time": live_start.strftime("%H:%M"),
            "reason": "Video follow-up: home blood-pressure review",
            "status": "approved",
            "type": "video_call",
            "notes": "Demo launch window. Review the seven-day home BP log.",
            "created_days_ago": 2,
        },
        {
            "key": "aisha_future",
            "patient": "aisha",
            "clinician": "maya",
            "date": next_weekday(0).isoformat(),
            "time": "09:30",
            "reason": "Annual wellness visit and preventive screening review",
            "status": "approved",
            "type": "in_person",
            "notes": "Patient will bring updated vaccination history.",
            "created_days_ago": 9,
        },
        {
            "key": "daniel_cardiology",
            "patient": "daniel",
            "clinician": "liam",
            "date": next_weekday(1).isoformat(),
            "time": "10:30",
            "reason": "Hypertension medication response",
            "status": "pending",
            "type": "phone_call",
            "notes": "Confirm pharmacy and review dizziness symptoms.",
            "created_days_ago": 1,
        },
        {
            "key": "sofia_future",
            "patient": "sofia",
            "clinician": "priya",
            "date": next_weekday(3).isoformat(),
            "time": "11:30",
            "reason": "Migraine frequency and trigger follow-up",
            "status": "approved",
            "type": "video_call",
            "notes": "Review headache diary before consultation.",
            "created_days_ago": 5,
        },
        {
            "key": "marcus_future",
            "patient": "marcus",
            "clinician": "james",
            "date": next_weekday(2).isoformat(),
            "time": "08:30",
            "reason": "Knee rehabilitation progress check",
            "status": "pending",
            "type": "in_person",
            "notes": "Functional movement assessment requested.",
            "created_days_ago": 2,
        },
        {
            "key": "evelyn_future",
            "patient": "evelyn",
            "clinician": "liam",
            "date": next_weekday(4).isoformat(),
            "time": "09:00",
            "reason": "Cardiology follow-up after medication adjustment",
            "status": "approved",
            "type": "in_person",
            "notes": "High-priority review; caregiver plans to attend.",
            "created_days_ago": 6,
        },
        {
            "key": "noah_future",
            "patient": "noah",
            "clinician": "maya",
            "date": next_weekday(4).isoformat(),
            "time": "14:00",
            "reason": "Pediatric follow-up after febrile illness",
            "status": "pending",
            "type": "phone_call",
            "notes": "Parent will join the call.",
            "created_days_ago": 1,
        },
    ]
    past_rows = [
        ("aisha", "maya", -87, "10:00", "Preventive care intake", "completed", "in_person"),
        ("aisha", "maya", -31, "09:30", "Nutrition and sleep follow-up", "completed", "phone_call"),
        ("daniel", "liam", -91, "11:00", "Initial cardiology consultation", "completed", "in_person"),
        ("daniel", "maya", -44, "14:00", "Diabetes care-plan review", "completed", "video_call"),
        ("daniel", "liam", -14, "10:30", "Blood-pressure check", "completed", "in_person"),
        ("sofia", "priya", -62, "13:00", "Migraine assessment", "completed", "in_person"),
        ("sofia", "priya", -20, "15:15", "Medication tolerance review", "completed", "video_call"),
        ("marcus", "james", -39, "08:30", "Acute knee pain assessment", "completed", "in_person"),
        ("marcus", "james", -11, "09:30", "Physical therapy progress", "completed", "in_person"),
        ("evelyn", "liam", -33, "09:00", "Exertional shortness of breath", "completed", "in_person"),
        ("evelyn", "liam", -8, "10:00", "Home vitals review", "completed", "phone_call"),
        ("noah", "maya", -18, "14:30", "Fever and sore throat", "completed", "in_person"),
        ("noah", "maya", -12, "14:00", "Lab result discussion", "completed", "phone_call"),
        ("aisha", "maya", -5, "10:30", "Rescheduled preventive visit", "cancelled", "in_person"),
        ("sofia", "priya", -4, "11:00", "Scheduling conflict", "cancelled", "phone_call"),
        ("marcus", "james", -26, "12:30", "Imaging review request", "rejected", "video_call"),
    ]
    for index, (
        patient_key,
        clinician_key,
        days,
        appt_time,
        reason,
        status,
        appointment_type,
    ) in enumerate(past_rows):
        rows.append(
            {
                "key": f"past_{index}",
                "patient": patient_key,
                "clinician": clinician_key,
                "date": iso_date(days),
                "time": appt_time,
                "reason": reason,
                "status": status,
                "type": appointment_type,
                "notes": (
                    "Visit completed; summary and follow-up plan documented."
                    if status == "completed"
                    else "Demo scheduling outcome retained for status filtering."
                ),
                "created_days_ago": abs(days) + 4,
            }
        )

    appointments: dict[str, Appointment] = {}
    for row in rows:
        appointment = Appointment(
            patient_email=patient[row["patient"]],
            clinician_email=clinician[row["clinician"]],
            appointment_date=row["date"],
            appointment_time=row["time"],
            reason=row["reason"],
            status=row["status"],
            appointment_type=row["type"],
            notes=row["notes"],
            created_at=now - timedelta(days=row["created_days_ago"]),
            updated_at=now - timedelta(
                days=max(row["created_days_ago"] - 1, 0)
            ),
        )
        db.add(appointment)
        appointments[row["key"]] = appointment
    db.flush()
    return appointments


def seed_appointment_reminders(
    db,
    appointments: dict[str, Appointment],
) -> None:
    now = utc_now()
    current_local = local_now()
    offsets = {
        "24_hour": timedelta(hours=24),
        "1_hour": timedelta(hours=1),
    }
    for appointment in appointments.values():
        if appointment.status != "approved":
            continue
        starts_at = datetime.strptime(
            f"{appointment.appointment_date} {appointment.appointment_time[:5]}",
            "%Y-%m-%d %H:%M",
        ).replace(tzinfo=appointment_timezone())
        if starts_at <= current_local:
            continue
        starts_at_utc = starts_at.astimezone(timezone.utc).replace(tzinfo=None)
        for reminder_type, offset in offsets.items():
            scheduled_for = starts_at_utc - offset
            already_due = scheduled_for <= now
            skip_stale_day_notice = (
                reminder_type == "24_hour"
                and starts_at_utc - now <= timedelta(hours=1)
            )
            db.add(
                AppointmentReminder(
                    appointment_id=appointment.id,
                    patient_email=appointment.patient_email,
                    reminder_type=reminder_type,
                    scheduled_for=scheduled_for,
                    status=(
                        "skipped"
                        if skip_stale_day_notice
                        else "sent"
                        if already_due
                        else "scheduled"
                    ),
                    sent_at=(
                        now - timedelta(minutes=1)
                        if already_due and not skip_stale_day_notice
                        else None
                    ),
                    created_at=appointment.created_at,
                    updated_at=now,
                )
            )


def record_specs() -> list[dict[str, Any]]:
    return [
        {
            "patient": "aisha",
            "clinician": "maya",
            "days": 94,
            "name": "Preventive Wellness Laboratory - Baseline",
            "type": "Lab Results",
            "category": "Laboratory",
            "code": "laboratory",
            "tags": ["preventive", "lipids", "wellness"],
            "summary": "Baseline wellness panel is reassuring with mildly low vitamin D.",
            "metrics": {"Total cholesterol": "192 mg/dL", "LDL": "112 mg/dL", "HDL": "58 mg/dL", "Vitamin D": "24 ng/mL", "Glucose": "93 mg/dL"},
            "findings": ["Vitamin D below the preferred range", "Glucose within expected range"],
        },
        {
            "patient": "aisha",
            "clinician": "maya",
            "days": 12,
            "name": "Preventive Wellness Laboratory - Follow-up",
            "type": "Lab Results",
            "category": "Laboratory",
            "code": "laboratory",
            "tags": ["preventive", "lipids", "follow-up"],
            "summary": "Follow-up panel shows improved LDL and vitamin D levels.",
            "metrics": {"Total cholesterol": "178 mg/dL", "LDL": "98 mg/dL", "HDL": "61 mg/dL", "Vitamin D": "34 ng/mL", "Glucose": "91 mg/dL"},
            "findings": ["Vitamin D returned to the expected range", "Improved lipid profile"],
        },
        {
            "patient": "aisha",
            "clinician": "maya",
            "days": 30,
            "name": "Annual Wellness Visit Note",
            "type": "Clinical Notes",
            "category": "Visit Note",
            "code": "visit_note",
            "tags": ["annual exam", "prevention"],
            "summary": "Preventive visit focused on sleep, activity, and age-appropriate screening.",
            "metrics": {"Blood pressure systolic": "118 mmHg", "Blood pressure diastolic": "76 mmHg", "BMI": "23.8"},
            "findings": ["No acute concerns", "Continue regular physical activity"],
        },
        {
            "patient": "daniel",
            "clinician": "liam",
            "days": 92,
            "name": "Cardiometabolic Panel - Baseline",
            "type": "Lab Results",
            "category": "Laboratory",
            "code": "laboratory",
            "tags": ["diabetes", "hypertension", "baseline"],
            "summary": "Baseline panel shows elevated A1c, LDL, and blood pressure.",
            "metrics": {"HbA1c": "8.1 %", "LDL": "148 mg/dL", "Triglycerides": "214 mg/dL", "Systolic BP": "154 mmHg", "Weight": "94.3 kg"},
            "findings": ["HbA1c above individualized goal", "LDL above expected range", "Blood pressure requires follow-up"],
        },
        {
            "patient": "daniel",
            "clinician": "liam",
            "days": 15,
            "name": "Cardiometabolic Panel - Treatment Follow-up",
            "type": "Lab Results",
            "category": "Laboratory",
            "code": "laboratory",
            "tags": ["diabetes", "hypertension", "follow-up"],
            "summary": "Follow-up shows improvement in glycemic and lipid markers; blood pressure remains above goal.",
            "metrics": {"HbA1c": "7.3 %", "LDL": "112 mg/dL", "Triglycerides": "168 mg/dL", "Systolic BP": "142 mmHg", "Weight": "91.2 kg"},
            "findings": ["HbA1c improved but remains above goal", "LDL improved", "Blood pressure remains elevated"],
        },
        {
            "patient": "daniel",
            "clinician": "maya",
            "days": 7,
            "name": "Seven-Day Home Vitals Log",
            "type": "Vital Signs",
            "category": "Vital Signs",
            "code": "vital_signs",
            "tags": ["home monitoring", "blood pressure"],
            "summary": "Average home blood pressure is elevated with no severe-range readings.",
            "metrics": {"Average systolic": "142 mmHg", "Average diastolic": "88 mmHg", "Average heart rate": "76 bpm"},
            "findings": ["Average blood pressure above goal", "No severe-range reading recorded"],
        },
        {
            "patient": "sofia",
            "clinician": "priya",
            "days": 63,
            "name": "Migraine Neurology Assessment",
            "type": "Clinical Notes",
            "category": "Visit Note",
            "code": "visit_note",
            "tags": ["migraine", "neurology", "baseline"],
            "summary": "Pattern is consistent with episodic migraine without new neurologic deficit.",
            "metrics": {"Headache days per month": "9 days", "Average pain score": "7 /10", "Sleep": "6 hours"},
            "findings": ["Episodic migraine pattern", "Sleep is a likely trigger", "Neurologic examination documented as nonfocal"],
        },
        {
            "patient": "sofia",
            "clinician": "priya",
            "days": 19,
            "name": "Migraine Diary Follow-up",
            "type": "Clinical Notes",
            "category": "Visit Note",
            "code": "visit_note",
            "tags": ["migraine", "headache diary", "follow-up"],
            "summary": "Headache frequency and average severity improved after trigger management.",
            "metrics": {"Headache days per month": "5 days", "Average pain score": "5 /10", "Sleep": "7 hours"},
            "findings": ["Headache frequency improved", "Hydration and regular sleep were helpful"],
        },
        {
            "patient": "sofia",
            "clinician": "priya",
            "days": 61,
            "name": "Brain MRI Report",
            "type": "Imaging",
            "category": "Imaging",
            "code": "imaging",
            "tags": ["MRI", "neurology"],
            "summary": "No acute intracranial abnormality is described in the fictional demo report.",
            "metrics": {},
            "findings": ["No acute intracranial abnormality", "No mass effect"],
        },
        {
            "patient": "marcus",
            "clinician": "james",
            "days": 40,
            "name": "Right Knee MRI",
            "type": "Imaging",
            "category": "Imaging",
            "code": "imaging",
            "tags": ["knee", "sports injury", "MRI"],
            "summary": "MRI describes a low-grade medial collateral ligament sprain and small effusion.",
            "metrics": {"Joint effusion": "small", "MCL sprain grade": "1"},
            "findings": ["Low-grade MCL sprain", "Small joint effusion", "No displaced meniscal tear"],
        },
        {
            "patient": "marcus",
            "clinician": "james",
            "days": 10,
            "name": "Orthopedic Rehabilitation Follow-up",
            "type": "Clinical Notes",
            "category": "Visit Note",
            "code": "visit_note",
            "tags": ["knee", "rehabilitation", "return to sport"],
            "summary": "Pain and function improved with progressive strengthening.",
            "metrics": {"Pain score": "2 /10", "Knee flexion": "132 degrees", "Single-leg squat": "8 repetitions"},
            "findings": ["Improved range of motion", "Mild residual weakness", "Continue graded return to running"],
        },
        {
            "patient": "marcus",
            "clinician": "james",
            "days": 37,
            "name": "Physical Therapy Referral",
            "type": "Referral",
            "category": "Other",
            "code": "other",
            "tags": ["physical therapy", "referral"],
            "summary": "Referral for supervised rehabilitation and home exercise education.",
            "metrics": {"Visits authorized": "8 visits"},
            "findings": ["Strength and proprioception program requested"],
        },
        {
            "patient": "evelyn",
            "clinician": "liam",
            "days": 34,
            "name": "Echocardiogram Report",
            "type": "Imaging",
            "category": "Imaging",
            "code": "imaging",
            "tags": ["cardiology", "echocardiogram"],
            "summary": "Fictional echocardiogram shows preserved systolic function with mild diastolic dysfunction.",
            "metrics": {"Ejection fraction": "60 %", "Left atrial volume index": "36 mL/m2", "RVSP": "31 mmHg"},
            "findings": ["Preserved left ventricular systolic function", "Mild diastolic dysfunction"],
        },
        {
            "patient": "evelyn",
            "clinician": "liam",
            "days": 8,
            "name": "Cardiology Vitals and Symptom Review",
            "type": "Vital Signs",
            "category": "Vital Signs",
            "code": "vital_signs",
            "tags": ["cardiology", "hypertension", "high priority"],
            "summary": "Blood pressure remains significantly elevated with intermittent exertional symptoms.",
            "metrics": {"Systolic BP": "166 mmHg", "Diastolic BP": "94 mmHg", "Heart rate": "84 bpm", "Oxygen saturation": "95 %"},
            "findings": ["Blood pressure above goal", "Intermittent exertional shortness of breath", "Prompt clinical follow-up advised"],
        },
        {
            "patient": "evelyn",
            "clinician": "liam",
            "days": 6,
            "name": "Medication Adjustment Visit Note",
            "type": "Clinical Notes",
            "category": "Visit Note",
            "code": "visit_note",
            "tags": ["cardiology", "medication review"],
            "summary": "Medication reconciliation completed and monitoring plan documented.",
            "metrics": {"Home BP readings supplied": "12 readings"},
            "findings": ["Medication adherence reviewed", "Caregiver included in monitoring plan"],
        },
        {
            "patient": "noah",
            "clinician": "maya",
            "days": 18,
            "name": "Pediatric Acute Visit Note",
            "type": "Clinical Notes",
            "category": "Visit Note",
            "code": "visit_note",
            "tags": ["pediatrics", "fever", "sore throat"],
            "summary": "Acute febrile illness assessed with guardian present.",
            "metrics": {"Temperature": "38.4 C", "Heart rate": "104 bpm", "Oxygen saturation": "98 %"},
            "findings": ["Fever", "Sore throat", "Hydration adequate"],
        },
        {
            "patient": "noah",
            "clinician": "maya",
            "days": 17,
            "name": "Rapid Strep Test",
            "type": "Lab Results",
            "category": "Laboratory",
            "code": "laboratory",
            "tags": ["pediatrics", "microbiology"],
            "summary": "Rapid antigen test is negative in this fictional demo result.",
            "metrics": {"Rapid strep": "negative"},
            "findings": ["Rapid strep test negative"],
        },
        {
            "patient": "noah",
            "clinician": "maya",
            "days": 11,
            "name": "Pediatric Recovery Follow-up",
            "type": "Clinical Notes",
            "category": "Visit Note",
            "code": "visit_note",
            "tags": ["pediatrics", "follow-up"],
            "summary": "Symptoms resolved and normal activity resumed.",
            "metrics": {"Temperature": "36.8 C", "Pain score": "0 /10"},
            "findings": ["Fever resolved", "Normal oral intake", "Return precautions reviewed"],
        },
    ]


def seed_records(db) -> dict[str, list[MedicalRecord]]:
    now = utc_now()
    patient_by_key = {item["key"]: item for item in PATIENTS}
    clinician_by_key = {item["key"]: item for item in CLINICIANS}
    records: dict[str, list[MedicalRecord]] = {item["key"]: [] for item in PATIENTS}
    for index, spec in enumerate(record_specs(), start=1):
        patient = patient_by_key[spec["patient"]]
        clinician = clinician_by_key[spec["clinician"]]
        slug = re.sub(r"[^a-z0-9]+", "-", spec["name"].lower()).strip("-")
        path = UPLOAD_DIR / patient["key"] / f"{index:02d}-{slug}.pdf"
        source_date = (local_now().date() - timedelta(days=spec["days"])).isoformat()
        text_lines = [
            "DEMO DATA - NOT A REAL PATIENT RECORD",
            f"Patient: {patient['name']} (fictional)",
            f"Document date: {source_date}",
            f"Category: {spec['category']}",
            "",
            f"Summary: {spec['summary']}",
            "",
            "Structured metrics:",
        ]
        text_lines.extend(
            f"- {key}: {value}" for key, value in spec["metrics"].items()
        )
        text_lines.extend(["", "Key findings:"])
        text_lines.extend(f"- {value}" for value in spec["findings"])
        text_lines.extend(
            [
                "",
                "This document is fictional and intended only for CareConnect testing.",
            ]
        )
        write_simple_pdf(path, spec["name"], text_lines)
        extracted = "\n".join(text_lines)
        record = MedicalRecord(
            patient_email=patient["email"],
            type=spec["type"],
            name=spec["name"],
            category=spec["category"],
            category_code=spec["code"],
            tags=json_text(spec["tags"]),
            source_date=source_date,
            file_path=str(path.resolve()),
            uploaded_at=now - timedelta(days=spec["days"]),
            uploaded_by=clinician["email"],
            analysis_summary=spec["summary"],
            extracted_text=extracted,
            metrics_data=json_text(spec["metrics"]),
            key_findings=json_text(spec["findings"]),
        )
        db.add(record)
        db.flush()
        db.add(
            MedicalRecordVersion(
                record_id=record.id,
                patient_email=patient["email"],
                uploaded_by=clinician["email"],
                version_number=1,
                file_name=path.name,
                file_path=str(path.resolve()),
                file_type="application/pdf",
                file_size=path.stat().st_size,
                change_notes="Initial demo document upload",
                analysis_summary=spec["summary"],
                extracted_text=extracted,
                metrics_data=json_text(spec["metrics"]),
                key_findings=json_text(spec["findings"]),
                is_latest=True,
                uploaded_at=now - timedelta(days=spec["days"]),
            )
        )
        records[spec["patient"]].append(record)
    return records


def prescription_specs() -> list[dict[str, Any]]:
    return [
        {
            "key": "aisha_vitamin_d",
            "patient": "aisha",
            "clinician": "maya",
            "days": 90,
            "diagnosis": "Vitamin D insufficiency",
            "status": "completed",
            "instructions": "Take with a meal. Repeat vitamin D level with routine follow-up.",
            "medicines": [{"medicine_name": "Cholecalciferol", "dosage": "1,000 IU", "frequency": "Once daily", "duration": "12 weeks"}],
        },
        {
            "key": "daniel_metabolic",
            "patient": "daniel",
            "clinician": "maya",
            "days": 43,
            "diagnosis": "Type 2 diabetes and hypertension",
            "status": "active",
            "instructions": "Continue home glucose and blood-pressure logs. Do not change doses without clinical review.",
            "medicines": [
                {"medicine_name": "Metformin ER", "dosage": "1,000 mg", "frequency": "With evening meal", "duration": "90 days"},
                {"medicine_name": "Lisinopril", "dosage": "20 mg", "frequency": "Once daily", "duration": "90 days"},
            ],
        },
        {
            "key": "daniel_lipid",
            "patient": "daniel",
            "clinician": "liam",
            "days": 14,
            "diagnosis": "Hyperlipidemia",
            "status": "active",
            "instructions": "Report unexplained muscle pain and complete follow-up laboratory testing.",
            "medicines": [{"medicine_name": "Atorvastatin", "dosage": "20 mg", "frequency": "Nightly", "duration": "90 days"}],
        },
        {
            "key": "sofia_migraine",
            "patient": "sofia",
            "clinician": "priya",
            "days": 58,
            "diagnosis": "Episodic migraine",
            "status": "active",
            "instructions": "Use at migraine onset as directed; follow the documented maximum daily dose.",
            "medicines": [{"medicine_name": "Sumatriptan", "dosage": "50 mg", "frequency": "At migraine onset as needed", "duration": "30 days"}],
        },
        {
            "key": "marcus_knee",
            "patient": "marcus",
            "clinician": "james",
            "days": 38,
            "diagnosis": "Low-grade MCL sprain",
            "status": "completed",
            "instructions": "Take with food only as directed. Stop and seek review for gastrointestinal symptoms.",
            "medicines": [{"medicine_name": "Naproxen", "dosage": "250 mg", "frequency": "Twice daily as needed", "duration": "7 days"}],
        },
        {
            "key": "evelyn_cardiac",
            "patient": "evelyn",
            "clinician": "liam",
            "days": 6,
            "diagnosis": "Hypertension requiring close follow-up",
            "status": "active",
            "instructions": "Record morning and evening blood pressure. Contact the care team for worsening symptoms.",
            "medicines": [
                {"medicine_name": "Amlodipine", "dosage": "5 mg", "frequency": "Once daily", "duration": "30 days"},
                {"medicine_name": "Metoprolol succinate", "dosage": "25 mg", "frequency": "Once daily", "duration": "30 days"},
            ],
        },
        {
            "key": "noah_supportive",
            "patient": "noah",
            "clinician": "maya",
            "days": 17,
            "diagnosis": "Acute febrile illness",
            "status": "completed",
            "instructions": "Guardian to administer only according to weight-based instructions and return precautions.",
            "medicines": [{"medicine_name": "Acetaminophen", "dosage": "Weight-based dose", "frequency": "Every 6 hours as needed", "duration": "3 days"}],
        },
    ]


def seed_prescriptions(db) -> dict[str, Prescription]:
    now = utc_now()
    patients = {item["key"]: item["email"] for item in PATIENTS}
    clinicians = {item["key"]: item["email"] for item in CLINICIANS}
    prescriptions: dict[str, Prescription] = {}
    for spec in prescription_specs():
        first = spec["medicines"][0]
        prescription = Prescription(
            patient_email=patients[spec["patient"]],
            clinician_email=clinicians[spec["clinician"]],
            medicine_name=first["medicine_name"],
            dosage=first["dosage"],
            frequency=first["frequency"],
            duration=first["duration"],
            instructions=spec["instructions"],
            diagnosis=spec["diagnosis"],
            status=spec["status"],
            created_at=now - timedelta(days=spec["days"]),
            updated_at=now - timedelta(days=max(spec["days"] - 1, 0)),
        )
        db.add(prescription)
        db.flush()
        db.execute(
            text(
                "UPDATE prescriptions SET medicines_json=:medicines "
                "WHERE id=:prescription_id"
            ),
            {
                "medicines": json_text(spec["medicines"]),
                "prescription_id": prescription.id,
            },
        )
        prescriptions[spec["key"]] = prescription
    return prescriptions


def seed_messages(
    db,
    prescriptions: dict[str, Prescription],
) -> dict[str, Message]:
    now = utc_now()
    patient = {item["key"]: item for item in PATIENTS}
    clinician = {item["key"]: item for item in CLINICIANS}
    conversations = [
        (
            "aisha",
            "maya",
            [
                (20, "patient", "Hello Dr. Chen, I uploaded my recent wellness results.", True),
                (19, "clinician", "Thank you, Aisha. I reviewed them; the vitamin D level has improved.", True),
                (18, "patient", "Great. Should I continue the same nutrition plan?", True),
                (17, "clinician", "Yes, continue it until our wellness visit. I added a note to your care plan.", False),
            ],
        ),
        (
            "daniel",
            "maya",
            [
                (7, "patient", "I have added a week of home blood-pressure readings.", True),
                (6, "clinician", "I can see them. The average is still above goal, but there are no severe-range readings.", True),
                (2, "patient", "I occasionally feel lightheaded when standing quickly.", False),
                (1, "clinician", "Please rise slowly, stay hydrated, and discuss this during our video follow-up. Seek urgent care for severe symptoms.", False),
            ],
        ),
        (
            "daniel",
            "liam",
            [
                (15, "clinician", "Your lipid values have improved. I am sending the updated medication plan here.", True),
                (14, "patient", "Received. I will complete the follow-up laboratory work.", True),
            ],
        ),
        (
            "sofia",
            "priya",
            [
                (16, "patient", "My headache diary shows fewer migraine days this month.", True),
                (15, "clinician", "That is encouraging. Please keep tracking sleep and hydration as well.", True),
                (3, "patient", "I uploaded the latest diary before our video visit.", False),
            ],
        ),
        (
            "marcus",
            "james",
            [
                (10, "clinician", "Your rehabilitation note shows good progress.", True),
                (9, "patient", "Can I begin short running intervals?", True),
                (8, "clinician", "Start with the graded plan in your attachment and stop if swelling returns.", False),
            ],
        ),
        (
            "evelyn",
            "liam",
            [
                (6, "clinician", "I have sent the revised medication plan. Please continue twice-daily BP readings.", True),
                (5, "patient", "My daughter will help record them.", True),
                (0, "patient", "This morning's reading was 166/94 and I felt short of breath walking upstairs.", False),
                (0, "clinician", "The care team is reviewing this now. Follow your urgent-care instructions if symptoms are current or worsening.", False),
            ],
        ),
        (
            "noah",
            "maya",
            [
                (12, "clinician", "The rapid test was negative. Continue the supportive-care plan and return precautions.", True),
                (11, "patient", "Noah is fever-free and eating normally again. Thank you.", True),
            ],
        ),
    ]
    created: dict[str, Message] = {}
    for patient_key, clinician_key, rows in conversations:
        patient_item = patient[patient_key]
        clinician_item = clinician[clinician_key]
        for index, (days, sender, body, is_read) in enumerate(rows):
            sender_is_patient = sender == "patient"
            message = Message(
                sender_email=(
                    patient_item["email"]
                    if sender_is_patient
                    else clinician_item["email"]
                ),
                sender_role="patient" if sender_is_patient else "clinician",
                recipient_email=(
                    clinician_item["email"]
                    if sender_is_patient
                    else patient_item["email"]
                ),
                recipient_role="clinician" if sender_is_patient else "patient",
                message=body,
                sent_at=now
                - timedelta(
                    days=days,
                    hours=max(len(rows) - index - 1, 0),
                ),
                read=is_read,
                is_edited=(patient_key == "daniel" and index == 1),
            )
            db.add(message)
            created[f"{patient_key}_{clinician_key}_{index}"] = message

    prescription_links = [
        ("daniel_metabolic", "daniel", "maya", 42),
        ("daniel_lipid", "daniel", "liam", 14),
        ("sofia_migraine", "sofia", "priya", 57),
        ("evelyn_cardiac", "evelyn", "liam", 6),
        ("noah_supportive", "noah", "maya", 17),
    ]
    for key, patient_key, clinician_key, days in prescription_links:
        prescription = prescriptions[key]
        message = Message(
            sender_email=clinician[clinician_key]["email"],
            sender_role="clinician",
            recipient_email=patient[patient_key]["email"],
            recipient_role="patient",
            message=f"Prescription shared: {prescription.diagnosis}",
            sent_at=now - timedelta(days=days),
            read=days > 7,
            prescription_id=prescription.id,
        )
        db.add(message)
        created[f"rx_{key}"] = message
    db.flush()

    plan_path = UPLOAD_DIR / "shared" / "marcus-graded-return-to-running.pdf"
    write_simple_pdf(
        plan_path,
        "Graded Return-to-Running Plan",
        [
            "DEMO DATA - NOT A REAL CARE PLAN",
            "Patient: Marcus Lee (fictional)",
            "Week 1: Walk 4 minutes, jog 1 minute, repeat four times.",
            "Week 2: Walk 3 minutes, jog 2 minutes, repeat four times.",
            "Stop and contact the care team if pain or swelling increases.",
        ],
    )
    attachment_message = created["marcus_james_2"]
    db.add(
        ChatAttachment(
            message_id=attachment_message.id,
            sender_email=clinician["james"]["email"],
            recipient_email=patient["marcus"]["email"],
            file_name=plan_path.name,
            file_path=str(plan_path.resolve()),
            file_type="application/pdf",
            file_size=plan_path.stat().st_size,
            uploaded_at=attachment_message.sent_at,
        )
    )
    return created


def seed_notifications(db) -> None:
    now = utc_now()
    rows = [
        ("aisha", "Upcoming wellness visit", "Your annual wellness visit with Dr. Maya Chen is approved.", "appointment", False, 1),
        ("aisha", "New care message", "Dr. Maya Chen replied to your wellness question.", "message", False, 0),
        ("daniel", "Appointment reminder — 1 hour", "Your approved video follow-up with Dr. Maya Chen is coming up soon.", "appointment_reminder", False, 0),
        ("daniel", "Prescription shared", "An updated cardiometabolic prescription is available in Messages.", "prescription", True, 14),
        ("daniel", "Lab comparison available", "Your baseline and follow-up cardiometabolic reports can now be compared.", "info", False, 1),
        ("sofia", "Video appointment approved", "Your migraine follow-up with Dr. Priya Nair was approved.", "appointment", False, 2),
        ("sofia", "New message", "Your clinician responded about your headache diary.", "message", False, 0),
        ("marcus", "Rehabilitation plan attached", "Dr. James Wilson shared a graded return-to-running plan.", "message", False, 7),
        ("marcus", "Appointment request received", "Your knee rehabilitation follow-up is awaiting review.", "appointment", True, 2),
        ("evelyn", "SOS response acknowledged", "Clinical operations acknowledged your SOS alert and assigned an owner.", "alert", False, 0),
        ("evelyn", "Prescription shared", "Your cardiology medication plan is available in Messages.", "prescription", False, 5),
        ("evelyn", "Upcoming cardiology visit", "Your high-priority cardiology follow-up is approved.", "appointment", False, 1),
        ("noah", "Follow-up requested", "A pediatric recovery follow-up is awaiting clinician review.", "appointment", False, 1),
        ("noah", "Record available", "The recovery follow-up note was added to the patient record.", "info", True, 10),
        ("maya", "New appointment request", "Daniel Brooks requested a hypertension follow-up.", "appointment", False, 1),
        ("maya", "Unread patient message", "Daniel Brooks reported occasional lightheadedness.", "message", False, 0),
        ("liam", "High-priority patient update", "Evelyn Carter submitted a new symptom message.", "alert", False, 0),
        ("james", "Appointment request", "Marcus Lee requested a rehabilitation progress check.", "appointment", False, 2),
        ("priya", "New headache diary", "Sofia Ramirez uploaded an updated headache diary.", "message", False, 1),
    ]
    users = {
        **{item["key"]: item["email"] for item in PATIENTS},
        **{item["key"]: item["email"] for item in CLINICIANS},
    }
    for key, title, message, kind, is_read, days in rows:
        db.add(
            Notification(
                user_email=users[key],
                title=title,
                message=message,
                type=kind,
                is_read=is_read,
                created_at=now - timedelta(days=days),
            )
        )


def seed_consents_and_video_events(
    db,
    appointments: dict[str, Appointment],
) -> None:
    now = utc_now()
    patient = {item["key"]: item["email"] for item in PATIENTS}
    clinician = {item["key"]: item["email"] for item in CLINICIANS}
    consents = [
        (patient["daniel"], "patient", "video_consultation", "accepted", 30, None),
        (clinician["maya"], "clinician", "video_consultation", "accepted", 120, None),
        (patient["sofia"], "patient", "video_consultation", "accepted", 34, None),
        (clinician["priya"], "clinician", "video_consultation", "accepted", 38, None),
        (patient["evelyn"], "patient", "emergency_alert", "accepted", 4, None),
        (patient["aisha"], "patient", "emergency_alert", "accepted", 70, None),
        (patient["marcus"], "patient", "video_consultation", "revoked", 35, 12),
    ]
    for email, role, consent_type, status, accepted_days, revoked_days in consents:
        db.add(
            UserConsent(
                user_email=email,
                user_role=role,
                consent_type=consent_type,
                consent_version=CONSENT_VERSION,
                status=status,
                accepted_at=now - timedelta(days=accepted_days),
                revoked_at=(
                    now - timedelta(days=revoked_days)
                    if revoked_days is not None
                    else None
                ),
                updated_at=(
                    now - timedelta(days=revoked_days)
                    if revoked_days is not None
                    else now - timedelta(days=accepted_days)
                ),
            )
        )

    past_video = appointments["past_3"]
    db.add_all(
        [
            VideoConsultationEvent(
                appointment_id=past_video.id,
                actor_email=patient["daniel"],
                actor_role="patient",
                event_type="launch_authorized",
                provider="comm360",
                created_at=now - timedelta(days=44, minutes=7),
            ),
            VideoConsultationEvent(
                appointment_id=past_video.id,
                actor_email=clinician["maya"],
                actor_role="clinician",
                event_type="launch_authorized",
                provider="comm360",
                created_at=now - timedelta(days=44, minutes=5),
            ),
        ]
    )


def seed_emergency_workflows(db) -> None:
    now = utc_now()
    patient = {item["key"]: item for item in PATIENTS}
    resolved = EmergencyAlert(
        patient_email=patient["aisha"]["email"],
        patient_name=patient["aisha"]["name"],
        alert_type="medical_emergency",
        severity="high",
        message="Patient activated the one-tap SOS button.",
        status="resolved",
        acknowledged_by=ADMIN_EMAIL,
        acknowledged_at=now - timedelta(days=69) + timedelta(minutes=4),
        resolved_by=patient["aisha"]["email"],
        resolved_at=now - timedelta(days=69) + timedelta(minutes=22),
        escalation_level=1,
        owner_email=ADMIN_EMAIL,
        owner_role="admin",
        ownership_assigned_at=now - timedelta(days=69) + timedelta(minutes=3),
        operational_state="false_alarm",
        last_monitored_at=now - timedelta(days=69) + timedelta(minutes=22),
        next_review_at=None,
        escalation_deadline=now - timedelta(days=69) + timedelta(minutes=15),
        consent_version=CONSENT_VERSION,
        consent_acknowledged=True,
        created_at=now - timedelta(days=69),
        updated_at=now - timedelta(days=69) + timedelta(minutes=22),
    )
    active = EmergencyAlert(
        patient_email=patient["evelyn"]["email"],
        patient_name=patient["evelyn"]["name"],
        alert_type="medical_emergency",
        severity="critical",
        message="Patient activated the one-tap SOS button.",
        status="acknowledged",
        acknowledged_by=ADMIN_EMAIL,
        acknowledged_at=now - timedelta(minutes=8),
        escalation_level=2,
        owner_email=ADMIN_EMAIL,
        owner_role="admin",
        ownership_assigned_at=now - timedelta(minutes=9),
        operational_state="owned",
        last_monitored_at=now - timedelta(minutes=2),
        next_review_at=now + timedelta(hours=4),
        escalation_deadline=now + timedelta(hours=8),
        consent_version=CONSENT_VERSION,
        consent_acknowledged=True,
        created_at=now - timedelta(minutes=12),
        updated_at=now - timedelta(minutes=2),
    )
    db.add_all([resolved, active])
    db.flush()
    db.add_all(
        [
            EmergencyAlertEvent(
                alert_id=resolved.id,
                event_type="created",
                actor_email=patient["aisha"]["email"],
                actor_role="patient",
                escalation_level=1,
                notes="SOS created after disclosure acknowledgement.",
                created_at=now - timedelta(days=69),
            ),
            EmergencyAlertEvent(
                alert_id=resolved.id,
                event_type="claimed",
                actor_email=ADMIN_EMAIL,
                actor_role="admin",
                escalation_level=1,
                notes="Clinical operations accepted ownership.",
                created_at=now - timedelta(days=69) + timedelta(minutes=3),
            ),
            EmergencyAlertEvent(
                alert_id=resolved.id,
                event_type="false_alarm",
                actor_email=patient["aisha"]["email"],
                actor_role="patient",
                escalation_level=1,
                notes="Patient confirmed the SOS was activated accidentally.",
                created_at=now - timedelta(days=69) + timedelta(minutes=22),
            ),
            EmergencyAlertEvent(
                alert_id=active.id,
                event_type="created",
                actor_email=patient["evelyn"]["email"],
                actor_role="patient",
                escalation_level=1,
                notes="SOS created after disclosure acknowledgement.",
                created_at=now - timedelta(minutes=12),
            ),
            EmergencyAlertEvent(
                alert_id=active.id,
                event_type="claimed",
                actor_email=ADMIN_EMAIL,
                actor_role="admin",
                escalation_level=1,
                notes="Clinical operations accepted ownership.",
                created_at=now - timedelta(minutes=9),
            ),
            EmergencyAlertEvent(
                alert_id=active.id,
                event_type="acknowledged",
                actor_email=ADMIN_EMAIL,
                actor_role="admin",
                escalation_level=1,
                notes="Patient contact workflow started.",
                created_at=now - timedelta(minutes=8),
            ),
            EmergencyAlertEvent(
                alert_id=active.id,
                event_type="escalated",
                actor_email=ADMIN_EMAIL,
                actor_role="admin",
                escalation_level=2,
                notes="Escalated to the clinical operations lead for symptom review.",
                created_at=now - timedelta(minutes=4),
            ),
            EmergencyAlertEvent(
                alert_id=active.id,
                event_type="check_in",
                actor_email=ADMIN_EMAIL,
                actor_role="admin",
                escalation_level=2,
                notes="Caregiver contact confirmed; awaiting clinician disposition.",
                created_at=now - timedelta(minutes=2),
            ),
        ]
    )


def seed_join_requests_and_audits(db) -> None:
    now = utc_now()
    db.add_all(
        [
            ClinicianJoinRequest(
                name="Dr. Omar Haddad",
                email=f"demo.omar.haddad{DEMO_DOMAIN}",
                phone="(555) 010-2201",
                specialization="Pulmonology",
                license_number="DEMO-CA-PU-6104",
                department="Respiratory Medicine",
                years_of_experience=11,
                message="Interested in supporting CareConnect virtual respiratory follow-ups.",
                status="pending",
                requested_at=now - timedelta(days=2),
            ),
            ClinicianJoinRequest(
                name="Dr. Nina Park",
                email=f"demo.nina.park{DEMO_DOMAIN}",
                phone="(555) 010-2202",
                specialization="Internal Medicine",
                license_number="DEMO-CA-IM-7008",
                department="Primary Care",
                years_of_experience=6,
                message="Fictional declined request for workflow testing.",
                status="rejected",
                requested_at=now - timedelta(days=16),
                reviewed_by=ADMIN_EMAIL,
                reviewed_at=now - timedelta(days=14),
                rejection_reason="Demo application requires additional credential documentation.",
            ),
        ]
    )
    db.add_all(
        [
            AdminAuditLog(
                admin_email=ADMIN_EMAIL,
                action="approved_clinician",
                target_email=f"demo.james.wilson{DEMO_DOMAIN}",
                details=json_text({"department": "Musculoskeletal Care", "source": "demo_seed"}),
                timestamp=now - timedelta(days=19),
            ),
            AdminAuditLog(
                admin_email=ADMIN_EMAIL,
                action="updated_patient_profile",
                target_email=f"demo.daniel{DEMO_DOMAIN}",
                details=json_text({"fields": ["weight_kg", "systolic_bp", "diastolic_bp"], "reason": "Latest admin-verified measurement"}),
                timestamp=now - timedelta(days=3),
            ),
            AdminAuditLog(
                admin_email=ADMIN_EMAIL,
                action="rejected_join_request",
                target_email=f"demo.nina.park{DEMO_DOMAIN}",
                details=json_text({"reason": "Additional credential documentation required"}),
                timestamp=now - timedelta(days=14),
            ),
        ]
    )
    security_rows = [
        ("login", "session", None, None, "success", 0),
        ("view_patient_profile", "patient", "daniel", "daniel", "success", 1),
        ("download_medical_record", "medical_record", "daniel", "daniel", "success", 2),
        ("compare_medical_reports", "medical_record", "daniel", "daniel", "success", 3),
        ("update_patient_profile", "patient", "daniel", "daniel", "success", 4),
        ("download_medical_record", "medical_record", "sofia", "sofia", "denied", 5),
    ]
    patients = {item["key"]: item["email"] for item in PATIENTS}
    for index, (action, resource_type, resource_key, patient_key, outcome, days) in enumerate(security_rows):
        actor = ADMIN_EMAIL if action == "update_patient_profile" else f"demo.maya.chen{DEMO_DOMAIN}"
        db.add(
            SecurityAuditEvent(
                request_id=f"demo-seed-{index + 1:03d}",
                actor_email=actor,
                actor_role="admin" if actor == ADMIN_EMAIL else "clinician",
                action=action,
                resource_type=resource_type,
                resource_id=patients.get(resource_key, "demo-session"),
                patient_email=patients.get(patient_key),
                outcome=outcome,
                ip_address="127.0.0.1",
                details=json_text({"source": "demo_seed", "fictional": True}),
                created_at=now - timedelta(days=days, hours=index),
            )
        )


def seed_meal_planner(db, patients: dict[str, Patient]) -> None:
    now = utc_now()
    profile_rows = [
        ("aisha", 64.8, "Maintain energy and heart health", True, 28, 18),
        ("daniel", 91.2, "Improve cardiometabolic health", False, 28, None),
        ("sofia", 68.5, "Support migraine-friendly routines", True, 30, 11),
        ("marcus", 79.6, "Fuel rehabilitation and strength", False, 28, None),
        ("evelyn", 72.3, "Heart-conscious balanced meals", False, 28, None),
        ("noah", 44.1, "Family-friendly balanced nutrition", False, 28, None),
    ]
    for key, weight, purpose, tracks_cycle, cycle_length, last_period_days in profile_rows:
        patient = patients[key]
        db.execute(
            text(
                "INSERT INTO meal_planner_profiles "
                "(patient_id,username,weight,weight_unit,purpose,profile_completed,"
                "track_menstrual_cycle,last_period_date,cycle_length,menstrual_preferences) "
                "VALUES (:patient_id,:username,:weight,'kg',:purpose,TRUE,:track_cycle,"
                ":last_period,:cycle_length,:preferences)"
            ),
            {
                "patient_id": patient.id,
                "username": f"demo_{key}",
                "weight": weight,
                "purpose": purpose,
                "track_cycle": tracks_cycle,
                "last_period": (
                    (local_now().date() - timedelta(days=last_period_days))
                    if last_period_days is not None
                    else None
                ),
                "cycle_length": cycle_length,
                "preferences": json_text(
                    {
                        "privacy": "private",
                        "nutrition_focus": "general wellness",
                    }
                )
                if tracks_cycle
                else None,
            },
        )

    plans = [
        ("aisha", "Mediterranean Workday", "focused", "Greek yogurt, berries & walnuts", 360, "Lentil quinoa bowl", 520, "Herb salmon with vegetables", 610, "Apple with almond butter", 190, 1680, 3),
        ("aisha", "Easy Weekend Balance", "relaxed", "Vegetable omelet & toast", 410, "Tomato chickpea soup", 470, "Chicken and roasted vegetables", 620, "Citrus fruit cup", 140, 1640, 12),
        ("daniel", "High-Fiber Heart Plan", "healthy", "Steel-cut oats with berries", 390, "Bean and vegetable grain bowl", 540, "Baked cod with barley", 610, "Pear and pumpkin seeds", 180, 1720, 2),
        ("daniel", "Low-Sodium Prep Day", "focused", "Egg and spinach wrap", 380, "No-salt turkey avocado salad", 500, "Lentil vegetable stew", 590, "Plain yogurt with cinnamon", 150, 1620, 10),
        ("sofia", "Hydration-Friendly Day", "calm", "Overnight oats with pear", 370, "Cucumber quinoa tabbouleh", 490, "Ginger tofu rice bowl", 590, "Melon and yogurt", 160, 1610, 4),
        ("sofia", "Regular Meal Rhythm", "focused", "Avocado egg toast", 420, "Chicken soba salad", 520, "Baked sweet potato and beans", 560, "Banana and tahini", 180, 1680, 15),
        ("marcus", "Recovery Protein Plan", "energetic", "Egg, oat and berry bowl", 510, "Chicken quinoa power bowl", 680, "Salmon, potato and greens", 720, "Yogurt and banana smoothie", 290, 2200, 1),
        ("marcus", "Training Day Fuel", "motivated", "Peanut butter banana oats", 560, "Turkey hummus grain wrap", 650, "Beef and vegetable rice bowl", 760, "Cottage cheese and fruit", 240, 2210, 8),
        ("evelyn", "Heart-Conscious Comfort", "calm", "Cinnamon oatmeal with fruit", 340, "White bean vegetable soup", 460, "Lemon chicken with farro", 570, "Unsalted walnuts and pear", 170, 1540, 3),
        ("noah", "Family School-Day Plan", "happy", "Whole-grain waffles and berries", 430, "Turkey avocado sandwich", 560, "Chicken taco bowl", 640, "Yogurt fruit parfait", 220, 1850, 2),
    ]
    for (
        key,
        name,
        mood,
        breakfast,
        breakfast_calories,
        lunch,
        lunch_calories,
        dinner,
        dinner_calories,
        snack,
        snack_calories,
        total,
        days_ago,
    ) in plans:
        db.execute(
            text(
                "INSERT INTO saved_meal_plans "
                "(patient_id,meal_plan_name,mood_context,breakfast_name,"
                "breakfast_calories,lunch_name,lunch_calories,dinner_name,"
                "dinner_calories,snack_name,snack_calories,total_calories,date_created) "
                "VALUES (:patient_id,:name,:mood,:breakfast,:breakfast_calories,"
                ":lunch,:lunch_calories,:dinner,:dinner_calories,:snack,"
                ":snack_calories,:total,:created)"
            ),
            {
                "patient_id": patients[key].id,
                "name": name,
                "mood": mood,
                "breakfast": breakfast,
                "breakfast_calories": breakfast_calories,
                "lunch": lunch,
                "lunch_calories": lunch_calories,
                "dinner": dinner,
                "dinner_calories": dinner_calories,
                "snack": snack,
                "snack_calories": snack_calories,
                "total": total,
                "created": now - timedelta(days=days_ago),
            },
        )

    reviews = [
        ("aisha", "The saved plan view is clear and the Mediterranean options feel practical.", 5, 8),
        ("daniel", "The low-sodium plan gave me useful portions for weekday meal prep.", 5, 5),
        ("sofia", "I liked being able to connect meal timing with my symptom journal.", 4, 3),
        ("marcus", "The recovery plan made protein and calorie targets easy to understand.", 5, 2),
        ("evelyn", "Simple choices and readable meal names made planning less stressful.", 4, 1),
    ]
    patient_lookup = {item["key"]: item for item in PATIENTS}
    for key, content, rating, days_ago in reviews:
        db.execute(
            text(
                "INSERT INTO meal_planner_reviews "
                "(patient_id,name,content,rating,created_at) "
                "VALUES (:patient_id,:name,:content,:rating,:created_at)"
            ),
            {
                "patient_id": patients[key].id,
                "name": patient_lookup[key]["name"],
                "content": content,
                "rating": rating,
                "created_at": now - timedelta(days=days_ago),
            },
        )

    cycle_logs = [
        ("aisha", 17, ["dark chocolate"], ["mild cramps"], "calm", "medium", "Gentle walk and regular meals helped."),
        ("aisha", 18, ["salty snacks"], ["bloating"], "reflective", "medium", "Focused on hydration and lower-sodium foods."),
        ("aisha", 19, ["fruit"], [], "positive", "high", "Symptoms improved."),
        ("sofia", 10, ["carbohydrates"], ["headache", "fatigue"], "low", "low", "Headache improved after rest and a regular meal."),
        ("sofia", 11, ["fruit"], ["light sensitivity"], "calm", "medium", "Tracked hydration and sleep."),
        ("sofia", 12, [], [], "positive", "high", "No migraine symptoms today."),
    ]
    for key, days_ago, cravings, symptoms, mood, energy, notes in cycle_logs:
        db.execute(
            text(
                "INSERT INTO menstrual_cycle_logs "
                "(patient_id,log_date,cravings,symptoms,mood,energy_level,notes,"
                "created_at,updated_at) VALUES "
                "(:patient_id,:log_date,:cravings,:symptoms,:mood,:energy,:notes,"
                ":created_at,:updated_at)"
            ),
            {
                "patient_id": patients[key].id,
                "log_date": local_now().date() - timedelta(days=days_ago),
                "cravings": json_text(cravings),
                "symptoms": json_text(symptoms),
                "mood": mood,
                "energy": energy,
                "notes": notes,
                "created_at": now - timedelta(days=days_ago),
                "updated_at": now - timedelta(days=days_ago),
            },
        )


def counts(db) -> dict[str, int]:
    patient_emails = [item["email"] for item in PATIENTS]
    clinician_emails = [item["email"] for item in CLINICIANS]
    patient_ids = [
        item.id
        for item in db.query(Patient)
        .filter(Patient.email.in_(patient_emails))
        .all()
    ]
    result = {
        "patients": db.query(Patient).filter(Patient.email.in_(patient_emails)).count(),
        "clinicians": db.query(Clinician).filter(Clinician.email.in_(clinician_emails)).count(),
        "admins": db.query(Admin).filter(Admin.email == ADMIN_EMAIL).count(),
        "appointments": db.query(Appointment).filter(Appointment.patient_email.in_(patient_emails)).count(),
        "appointment_reminders": db.query(AppointmentReminder).filter(AppointmentReminder.patient_email.in_(patient_emails)).count(),
        "medical_records": db.query(MedicalRecord).filter(MedicalRecord.patient_email.in_(patient_emails)).count(),
        "record_versions": db.query(MedicalRecordVersion).filter(MedicalRecordVersion.patient_email.in_(patient_emails)).count(),
        "prescriptions": db.query(Prescription).filter(Prescription.patient_email.in_(patient_emails)).count(),
        "messages": db.query(Message).filter(or_(Message.sender_email.in_(DEMO_EMAILS), Message.recipient_email.in_(DEMO_EMAILS))).count(),
        "profile_history": db.query(PatientProfileHistory).filter(PatientProfileHistory.patient_id.in_(patient_ids)).count() if patient_ids else 0,
        "notifications": db.query(Notification).filter(Notification.user_email.in_(DEMO_EMAILS)).count(),
        "emergency_alerts": db.query(EmergencyAlert).filter(EmergencyAlert.patient_email.in_(patient_emails)).count(),
    }
    if patient_ids:
        result["saved_meal_plans"] = db.execute(
            text(
                "SELECT COUNT(*) FROM saved_meal_plans WHERE patient_id IN "
                f"({','.join(str(value) for value in patient_ids)})"
            )
        ).scalar_one()
        result["meal_reviews"] = db.execute(
            text(
                "SELECT COUNT(*) FROM meal_planner_reviews WHERE patient_id IN "
                f"({','.join(str(value) for value in patient_ids)})"
            )
        ).scalar_one()
    else:
        result["saved_meal_plans"] = 0
        result["meal_reviews"] = 0
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed fictional CareConnect test data."
    )
    parser.add_argument(
        "--clear-only",
        action="store_true",
        help="Remove the demo namespace without recreating it.",
    )
    parser.add_argument(
        "--allow-production",
        action="store_true",
        help="Explicitly allow execution when ENVIRONMENT=production.",
    )
    args = parser.parse_args()

    if is_production() and not args.allow_production:
        parser.error(
            "Refusing to seed ENVIRONMENT=production. "
            "Use a development database or pass --allow-production explicitly."
        )
    if not DEMO_PASSWORD or len(DEMO_PASSWORD) < 12:
        parser.error(
            "CARECONNECT_DEMO_PASSWORD must contain at least 12 characters."
        )

    ensure_application_schema()
    db = SessionLocal()
    try:
        delete_demo_rows(db)
        db.commit()
        if args.clear_only:
            if UPLOAD_DIR.exists():
                shutil.rmtree(UPLOAD_DIR)
            print("Removed the CareConnect demo namespace.")
            return 0

        shared_password_hash = password_hash(db)
        patients, clinicians, _admin = seed_accounts(db, shared_password_hash)
        seed_profile_history(db, patients)
        seed_connections(db)
        appointments = seed_appointments(db)
        seed_appointment_reminders(db, appointments)
        seed_records(db)
        prescriptions = seed_prescriptions(db)
        seed_messages(db, prescriptions)
        seed_notifications(db)
        seed_consents_and_video_events(db, appointments)
        seed_emergency_workflows(db)
        seed_join_requests_and_audits(db)
        seed_meal_planner(db, patients)
        db.commit()

        summary = counts(db)
        print("\nCareConnect demo data is ready.")
        print(json.dumps(summary, indent=2))
        print("\nLogin accounts (all use the same password):")
        print(f"  Admin:     {ADMIN_EMAIL}")
        print(f"  Patient:   {PATIENTS[1]['email']} (rich chronic-care scenario)")
        print(f"  Patient:   {PATIENTS[4]['email']} (SOS/high-priority scenario)")
        print(f"  Clinician: {CLINICIANS[0]['email']} (primary-care workflow)")
        print(f"  Clinician: {CLINICIANS[1]['email']} (cardiology workflow)")
        print(f"  Password:  {DEMO_PASSWORD}")
        print(
            "\nAll demo PDFs are fictional and stored under "
            f"{UPLOAD_DIR.resolve()}."
        )
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
