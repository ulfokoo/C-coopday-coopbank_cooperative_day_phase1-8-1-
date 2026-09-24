"""One-time (and safe-to-rerun) seed script.

Creates:
  - the baseline permission list
  - the baseline roles (SUPER ADMIN, ADMIN, EVENT COORDINATOR, TEAM LEADER,
    TEAM MEMBER, FINANCE, PROCUREMENT, DOCUMENT OFFICER, VIEWER) wired up
    with a sensible starting set of permissions
  - a starter list of departments
  - one SUPER ADMIN user so you can log in and take it from there

Run with:  python seed.py
Safe to re-run: existing rows are left alone / updated, not duplicated.
"""
import os
from app import create_app
from app.extensions import db
from app.models.user import User, Role, Permission
from app.models.department import Department

app = create_app(os.environ.get("FLASK_ENV", "development"))

PERMISSIONS = [
    # (code, module, description)
    ("view_event", "Events", "View Cooperative Day events"),
    ("create_event", "Events", "Create a new Cooperative Day event"),
    ("edit_event", "Events", "Edit Cooperative Day event details"),
    ("delete_event", "Events", "Archive/cancel a Cooperative Day event"),
    ("manage_teams", "Teams", "Create/edit teams and manage team members"),
    ("manage_tasks", "Tasks", "Create/edit/assign tasks and post task comments"),
    ("manage_instructions", "Instructions", "Record/manage instructions and the decision register"),
    ("manage_meetings", "Meetings", "Schedule meetings, record minutes and action points"),
    ("view_documents", "Documents", "View documents and correspondence"),
    ("upload_documents", "Documents", "Upload documents, new versions and log correspondence"),
    ("approve_documents", "Documents", "Approve/reject documents"),
    ("download_documents", "Documents", "Download documents"),
    ("view_procurement", "Procurement", "View procurement requests, suppliers and materials"),
    ("create_purchase_request", "Procurement", "Create/edit purchase requests and line items"),
    ("approve_purchase", "Procurement", "Approve/reject purchase requests and change their workflow status"),
    ("manage_suppliers", "Procurement", "Create/edit supplier records"),
    ("manage_materials", "Procurement", "Create/edit event material & asset tracking records"),
    ("view_finance", "Finance", "View financial/cost information"),
    ("manage_users", "Admin", "Manage users, roles, permissions and departments"),
    ("view_reports", "Reports", "View annual reports and dashboards"),
    ("generate_reports", "Reports", "Generate/export annual reports"),
    ("view_activities", "Activities", "View the Cooperative Day activity/event schedule"),
    ("manage_activities", "Activities", "Create/edit activities and manage activity participants"),
    ("view_communication", "Communication", "View communication/media items"),
    ("manage_communication", "Communication", "Create/edit press releases, posters, social posts and other media items"),
    ("approve_communication", "Communication", "Approve/reject communication/media items before publication"),
]

ROLE_PERMISSIONS = {
    "SUPER ADMIN": "ALL",  # is_super_admin=True bypasses checks entirely
    "ADMIN": [p[0] for p in PERMISSIONS],
    "EVENT COORDINATOR": [
        "view_event", "create_event", "edit_event", "manage_teams", "manage_tasks",
        "manage_instructions", "manage_meetings",
        "view_documents", "upload_documents", "approve_documents", "download_documents",
        "view_procurement", "manage_materials", "view_reports", "generate_reports",
        "view_activities", "manage_activities", "view_communication", "manage_communication", "approve_communication",
    ],
    "TEAM LEADER": [
        "view_event", "manage_tasks", "manage_meetings", "view_documents", "upload_documents",
        "download_documents", "view_procurement", "create_purchase_request", "manage_materials", "view_reports",
        "view_activities", "manage_activities", "view_communication", "manage_communication",
    ],
    "TEAM MEMBER": [
        "view_event", "view_documents", "upload_documents", "download_documents",
        "view_activities", "view_communication",
    ],
    "FINANCE": ["view_event", "view_finance", "view_procurement", "approve_purchase", "view_reports"],
    "PROCUREMENT": [
        "view_event", "view_procurement", "create_purchase_request", "approve_purchase",
        "manage_suppliers", "manage_materials", "view_documents",
    ],
    "DOCUMENT OFFICER": [
        "view_event", "view_documents", "upload_documents", "approve_documents", "download_documents",
        "view_communication",
    ],
    "VIEWER": ["view_event", "view_documents", "view_reports", "view_activities", "view_communication"],
}

DEPARTMENTS = [
    "Agri Business", "Cooperative Business", "Marketing", "Communication", "Procurement",
    "Finance", "HR", "IT", "Legal", "Administration", "Branch Operations", "Partnerships",
    "BDS", "ESG", "Other",
]


def run():
    with app.app_context():
        db.create_all()

        # --- permissions ---
        perm_by_code = {}
        for code, module, desc in PERMISSIONS:
            perm = Permission.query.filter_by(code=code).first()
            if not perm:
                perm = Permission(code=code, module=module, description=desc)
                db.session.add(perm)
            else:
                perm.module, perm.description = module, desc
            perm_by_code[code] = perm
        db.session.flush()

        # --- roles ---
        for role_name, perm_codes in ROLE_PERMISSIONS.items():
            role = Role.query.filter_by(name=role_name).first()
            if not role:
                role = Role(name=role_name, is_system=True)
                db.session.add(role)
            role.is_super_admin = perm_codes == "ALL"
            role.is_system = True
            if perm_codes != "ALL":
                role.permissions = [perm_by_code[c] for c in perm_codes]
            db.session.flush()

        # --- departments ---
        for name in DEPARTMENTS:
            if not Department.query.filter_by(name=name).first():
                db.session.add(Department(name=name))

        db.session.commit()

        # --- super admin user ---
        admin_username = app.config["SEED_ADMIN_USERNAME"]
        if not User.query.filter_by(username=admin_username).first():
            super_role = Role.query.filter_by(name="SUPER ADMIN").first()
            admin = User(
                full_name="System Administrator",
                username=admin_username,
                email=app.config["SEED_ADMIN_EMAIL"],
                role_id=super_role.id,
                status="Active",
            )
            admin.set_password(app.config["SEED_ADMIN_PASSWORD"])
            db.session.add(admin)
            db.session.commit()
            print(f"Created SUPER ADMIN user: {admin_username} / (password from SEED_ADMIN_PASSWORD)")
        else:
            print(f"SUPER ADMIN user '{admin_username}' already exists — skipped.")

        print("Seed complete: permissions, roles, departments ready.")


if __name__ == "__main__":
    run()
