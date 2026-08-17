"""
Bootstrap seed script — run this ONCE after setting up the database, before
using the API. It creates:
    1. A superuser account (bypasses all permission checks)
    2. The default set of roles and permissions
    3. Assigns the "admin" role (with all permissions) to the superuser

This script talks to the database DIRECTLY (not through the API), so it
never hits RequirePermission checks — this is exactly how tools like
Django's `createsuperuser` or Laravel's database seeders solve the same
"need a permission to create the first permission" bootstrap problem.

Usage:
    python -m src.scripts.seed_admin
"""
from datetime import date

from src.core.database import SessionLocal
from src.core.security import get_password_hash
from src.models.IAM import Permission, Role, User
from src.models.profile import UserContact, UserProfile

# --- Configuration: edit these before running in a real environment ---
SUPERUSER_EMAIL = "superadmin@hms.com"
SUPERUSER_PASSWORD = "SuperAdmin123!"

DEFAULT_PERMISSIONS = [
    ("Manage Users", "iam:manage_users"),
    ("View Users", "iam:view_users"),
    ("Manage Roles", "iam:manage_roles"),
    ("Manage Permissions", "iam:manage_permissions"),
    ("View Audit Logs", "iam:view_audit_logs"),
]


def seed() -> None:
    db = SessionLocal()
    try:
        # --- 1. Superuser account (skip if it already exists) ---
        existing = db.query(User).filter(User.email == SUPERUSER_EMAIL).first()
        if existing:
            print(f"Superuser '{SUPERUSER_EMAIL}' already exists — skipping user creation.")
            superuser = existing
        else:
            superuser = User(
                email=SUPERUSER_EMAIL,
                hashed_password=get_password_hash(SUPERUSER_PASSWORD),
                is_active=True,
                is_superuser=True,
            )
            db.add(superuser)
            db.flush()  # get superuser.id without committing yet

            # Minimal identity/contact so the superuser is a "complete" user too
            db.add(UserProfile(
                user_id=superuser.id, first_name="Super", last_name="Admin",
                gender="other", dob=date(1990, 1, 1),
            ))
            db.add(UserContact(user_id=superuser.id, primary_phone="0000000000"))
            print(f"Created superuser: {SUPERUSER_EMAIL} / {SUPERUSER_PASSWORD}")

        # --- 2. Default permissions (skip ones that already exist) ---
        created_permissions = []
        for name, code in DEFAULT_PERMISSIONS:
            perm = db.query(Permission).filter(Permission.code == code).first()
            if perm is None:
                perm = Permission(name=name, code=code)
                db.add(perm)
                db.flush()
                print(f"Created permission: {code}")
            created_permissions.append(perm)

        # --- 3. Default "admin" role with all permissions attached ---
        admin_role = db.query(Role).filter(Role.name == "admin").first()
        if admin_role is None:
            admin_role = Role(name="admin", description="Full system access")
            db.add(admin_role)
            db.flush()
            print("Created role: admin")

        for perm in created_permissions:
            if perm not in admin_role.permissions:
                admin_role.permissions.append(perm)

        # --- 4. Also assign the admin role to the superuser (belt-and-suspenders) ---
        if admin_role not in superuser.roles:
            superuser.roles.append(admin_role)

        db.commit()
        print("\nSeeding complete.")
        print(f"Login with: {SUPERUSER_EMAIL} / {SUPERUSER_PASSWORD}")
        print("This account can now create further roles/permissions/users through the API.")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
