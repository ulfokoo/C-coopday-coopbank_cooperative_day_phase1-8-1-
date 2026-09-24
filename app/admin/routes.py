from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models.user import User, Role, Permission
from app.models.department import Department
from app.models.audit import AuditLog
from app.admin.forms import UserForm, RoleForm, DepartmentForm
from app.utils.decorators import permission_required
from app.utils.audit import log_action

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/")
@login_required
@permission_required("manage_users")
def index():
    return render_template("admin/index.html")


# --------------------------------------------------------------- AUDIT LOG ----
@admin_bp.route("/audit-log")
@login_required
@permission_required("manage_users")
def audit_log():
    page = request.args.get("page", 1, type=int)
    action = request.args.get("action", "", type=str)
    entity_type = request.args.get("entity_type", "", type=str)
    user_id = request.args.get("user_id", type=int)

    query = AuditLog.query
    if action:
        query = query.filter_by(action=action)
    if entity_type:
        query = query.filter_by(entity_type=entity_type)
    if user_id:
        query = query.filter_by(user_id=user_id)

    pagination = query.order_by(AuditLog.created_at.desc()).paginate(page=page, per_page=30, error_out=False)

    actions = [a[0] for a in db.session.query(AuditLog.action).distinct().order_by(AuditLog.action).all()]
    entity_types = [
        e[0] for e in db.session.query(AuditLog.entity_type).distinct().order_by(AuditLog.entity_type).all()
    ]
    users = User.query.order_by(User.full_name).all()

    return render_template(
        "admin/audit_log.html", pagination=pagination, actions=actions, entity_types=entity_types, users=users,
        selected_action=action, selected_entity_type=entity_type, selected_user_id=user_id,
    )


# ---------------------------------------------------------------- USERS ----
@admin_bp.route("/users")
@login_required
@permission_required("manage_users")
def users_list():
    page = request.args.get("page", 1, type=int)
    q = request.args.get("q", "", type=str).strip()
    query = User.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            (User.full_name.ilike(like)) | (User.username.ilike(like)) | (User.email.ilike(like))
        )
    pagination = query.order_by(User.full_name).paginate(page=page, per_page=20, error_out=False)
    return render_template("admin/users_list.html", pagination=pagination, q=q)


@admin_bp.route("/users/new", methods=["GET", "POST"])
@login_required
@permission_required("manage_users")
def user_new():
    form = UserForm()
    _populate_user_choices(form)
    if form.validate_on_submit():
        if not form.password.data:
            flash("Password is required for a new user.", "danger")
            return render_template("admin/user_form.html", form=form, is_new=True)
        if User.query.filter_by(username=form.username.data).first():
            flash("That username is already taken.", "danger")
            return render_template("admin/user_form.html", form=form, is_new=True)
        if User.query.filter_by(email=form.email.data).first():
            flash("That email is already registered.", "danger")
            return render_template("admin/user_form.html", form=form, is_new=True)

        user = User(
            full_name=form.full_name.data,
            username=form.username.data,
            email=form.email.data,
            phone=form.phone.data,
            position=form.position.data,
            department_id=form.department_id.data or None,
            role_id=form.role_id.data,
            status=form.status.data,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()
        log_action("create", "User", user.id, f"Created user {user.username}")
        db.session.commit()
        flash(f"User '{user.full_name}' created.", "success")
        return redirect(url_for("admin.users_list"))
    return render_template("admin/user_form.html", form=form, is_new=True)


@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("manage_users")
def user_edit(user_id):
    user = User.query.get_or_404(user_id)
    form = UserForm(obj=user)
    _populate_user_choices(form)
    if request.method == "GET":
        form.department_id.data = user.department_id or 0

    if form.validate_on_submit():
        existing = User.query.filter(User.username == form.username.data, User.id != user.id).first()
        if existing:
            flash("That username is already taken.", "danger")
            return render_template("admin/user_form.html", form=form, is_new=False, user=user)

        user.full_name = form.full_name.data
        user.username = form.username.data
        user.email = form.email.data
        user.phone = form.phone.data
        user.position = form.position.data
        user.department_id = form.department_id.data or None
        user.role_id = form.role_id.data
        user.status = form.status.data
        if form.password.data:
            user.set_password(form.password.data)

        log_action("update", "User", user.id, f"Updated user {user.username}")
        db.session.commit()
        flash(f"User '{user.full_name}' updated.", "success")
        return redirect(url_for("admin.users_list"))
    return render_template("admin/user_form.html", form=form, is_new=False, user=user)


@admin_bp.route("/users/<int:user_id>/toggle-status", methods=["POST"])
@login_required
@permission_required("manage_users")
def user_toggle_status(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("You cannot deactivate your own account.", "warning")
        return redirect(url_for("admin.users_list"))
    user.status = "Inactive" if user.status == "Active" else "Active"
    log_action("update", "User", user.id, f"Status changed to {user.status}")
    db.session.commit()
    flash(f"User '{user.full_name}' is now {user.status}.", "info")
    return redirect(url_for("admin.users_list"))


def _populate_user_choices(form):
    form.department_id.choices = [(0, "— None —")] + [
        (d.id, d.name) for d in Department.query.filter_by(is_active=True).order_by(Department.name)
    ]
    form.role_id.choices = [(r.id, r.name) for r in Role.query.order_by(Role.name)]


# ---------------------------------------------------------------- ROLES ----
@admin_bp.route("/roles")
@login_required
@permission_required("manage_users")
def roles_list():
    roles = Role.query.order_by(Role.name).all()
    return render_template("admin/roles_list.html", roles=roles)


@admin_bp.route("/roles/new", methods=["GET", "POST"])
@login_required
@permission_required("manage_users")
def role_new():
    form = RoleForm()
    all_permissions = Permission.query.order_by(Permission.module, Permission.code).all()
    if form.validate_on_submit():
        role = Role(
            name=form.name.data,
            description=form.description.data,
            is_super_admin=form.is_super_admin.data,
        )
        selected_ids = request.form.getlist("permission_ids")
        role.permissions = Permission.query.filter(Permission.id.in_(selected_ids)).all()
        db.session.add(role)
        db.session.flush()
        log_action("create", "Role", role.id, f"Created role {role.name}")
        db.session.commit()
        flash(f"Role '{role.name}' created.", "success")
        return redirect(url_for("admin.roles_list"))
    return render_template(
        "admin/role_form.html", form=form, all_permissions=all_permissions, role=None, is_new=True
    )


@admin_bp.route("/roles/<int:role_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("manage_users")
def role_edit(role_id):
    role = Role.query.get_or_404(role_id)
    form = RoleForm(obj=role)
    all_permissions = Permission.query.order_by(Permission.module, Permission.code).all()
    if form.validate_on_submit():
        if role.is_system and role.name != form.name.data:
            flash("Built-in role names cannot be changed.", "warning")
            return redirect(url_for("admin.roles_list"))
        role.name = form.name.data
        role.description = form.description.data
        role.is_super_admin = form.is_super_admin.data
        selected_ids = request.form.getlist("permission_ids")
        role.permissions = Permission.query.filter(Permission.id.in_(selected_ids)).all()
        log_action("update", "Role", role.id, f"Updated role {role.name}")
        db.session.commit()
        flash(f"Role '{role.name}' updated.", "success")
        return redirect(url_for("admin.roles_list"))
    return render_template(
        "admin/role_form.html", form=form, all_permissions=all_permissions, role=role, is_new=False
    )


@admin_bp.route("/roles/<int:role_id>/delete", methods=["POST"])
@login_required
@permission_required("manage_users")
def role_delete(role_id):
    role = Role.query.get_or_404(role_id)
    if role.is_system:
        flash("Built-in roles cannot be deleted.", "warning")
    elif role.users.count() > 0:
        flash("Cannot delete a role that is still assigned to users.", "warning")
    else:
        log_action("delete", "Role", role.id, f"Deleted role {role.name}")
        db.session.delete(role)
        db.session.commit()
        flash("Role deleted.", "info")
    return redirect(url_for("admin.roles_list"))


# ----------------------------------------------------------- DEPARTMENTS ----
@admin_bp.route("/departments")
@login_required
@permission_required("manage_users")
def departments_list():
    departments = Department.query.order_by(Department.name).all()
    return render_template("admin/departments_list.html", departments=departments)


@admin_bp.route("/departments/new", methods=["GET", "POST"])
@login_required
@permission_required("manage_users")
def department_new():
    form = DepartmentForm()
    if form.validate_on_submit():
        if Department.query.filter_by(name=form.name.data).first():
            flash("A department with that name already exists.", "danger")
            return render_template("admin/department_form.html", form=form, is_new=True)
        dept = Department(name=form.name.data, description=form.description.data, is_active=form.is_active.data)
        db.session.add(dept)
        db.session.flush()
        log_action("create", "Department", dept.id, f"Created department {dept.name}")
        db.session.commit()
        flash(f"Department '{dept.name}' created.", "success")
        return redirect(url_for("admin.departments_list"))
    return render_template("admin/department_form.html", form=form, is_new=True)


@admin_bp.route("/departments/<int:dept_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("manage_users")
def department_edit(dept_id):
    dept = Department.query.get_or_404(dept_id)
    form = DepartmentForm(obj=dept)
    if form.validate_on_submit():
        dept.name = form.name.data
        dept.description = form.description.data
        dept.is_active = form.is_active.data
        log_action("update", "Department", dept.id, f"Updated department {dept.name}")
        db.session.commit()
        flash(f"Department '{dept.name}' updated.", "success")
        return redirect(url_for("admin.departments_list"))
    return render_template("admin/department_form.html", form=form, is_new=False, dept=dept)
