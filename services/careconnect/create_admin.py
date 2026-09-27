from database import SessionLocal
from models import Admin as AdminModel
import bcrypt


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


db = SessionLocal()

admin_email = "admin@careconnect.com"
admin_password = "Admin@123"

existing = db.query(AdminModel).filter(AdminModel.email == admin_email).first()

if existing:
    existing.name = "CareConnect Admin"
    existing.hashed_password = get_password_hash(admin_password)
    existing.role = "admin"
    existing.is_active = True
    existing.email_verified = True
    existing.access_level = "super_admin"
    existing.department = "Administration"
    print("Existing admin updated")
else:
    admin = AdminModel(
        name="CareConnect Admin",
        email=admin_email,
        hashed_password=get_password_hash(admin_password),
        role="admin",
        is_active=True,
        email_verified=True,
        access_level="super_admin",
        department="Administration",
    )
    db.add(admin)
    print("New admin created")

db.commit()
db.close()

print("Admin login created")
print("Email:", admin_email)
print("Password:", admin_password)