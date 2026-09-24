from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db


# Many-to-many: which permissions a role grants.
role_permissions = db.Table(
    "role_permissions",
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id"), primary_key=True),
    db.Column("permission_id", db.Integer, db.ForeignKey("permissions.id"), primary_key=True),
)


class Permission(db.Model):
    """A single grantable capability, e.g. 'manage_users', 'approve_purchase'.

    Permissions are seeded (see seed.py) but administrators can create more
    later from the Admin Control Center — nothing is hard-coded into logic
    other than the string code itself.
    """

    __tablename__ = "permissions"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), unique=True, nullable=False, index=True)
    description = db.Column(db.String(255))
    module = db.Column(db.String(80))  # groups permissions in the admin UI

    def __repr__(self):
        return f"<Permission {self.code}>"


class Role(db.Model):
    """A named role (SUPER ADMIN, ADMIN, TEAM LEADER, ...).

    Administrators can create additional roles at runtime; behaviour is
    driven by the permissions attached to a role, not by the role name
    itself (except for the built-in 'is_super_admin' bypass).
    """

    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(255))
    is_super_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_system = db.Column(db.Boolean, default=False, nullable=False)  # built-in roles, not deletable
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    permissions = db.relationship(
        "Permission", secondary=role_permissions, backref="roles", lazy="joined"
    )
    users = db.relationship("User", backref="role", lazy="dynamic")

    def has_permission(self, code):
        if self.is_super_admin:
            return True
        return any(p.code == code for p in self.permissions)

    def __repr__(self):
        return f"<Role {self.name}>"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(30))
    position = db.Column(db.String(120))

    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)

    password_hash = db.Column(db.String(255), nullable=False)

    status = db.Column(db.String(20), default="Active", nullable=False)  # Active / Inactive / Suspended

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    # relationships
    led_teams = db.relationship("Team", backref="leader", foreign_keys="Team.leader_id")
    coordinated_events = db.relationship(
        "CooperativeDay", backref="coordinator", foreign_keys="CooperativeDay.coordinator_id"
    )
    team_memberships = db.relationship(
        "TeamMember", backref="user", lazy="dynamic", foreign_keys="TeamMember.user_id"
    )

    # ---- password helpers ----
    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    # ---- permission helpers ----
    def has_permission(self, code):
        if not self.role:
            return False
        return self.role.has_permission(code)

    def has_role(self, *role_names):
        return self.role is not None and self.role.name in role_names

    @property
    def is_super_admin(self):
        return self.role is not None and self.role.is_super_admin

    @property
    def is_active_user(self):
        return self.status == "Active"

    # Flask-Login uses is_active to block login of disabled accounts
    @property
    def is_active(self):
        return self.status == "Active"

    def __repr__(self):
        return f"<User {self.username}>"
