from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import db
from app.models.user import User
from app.auth.forms import LoginForm, ChangePasswordForm
from app.utils.audit import log_action

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        identifier = form.username.data.strip()
        user = User.query.filter(
            (User.username == identifier) | (User.email == identifier)
        ).first()

        if user is None or not user.check_password(form.password.data):
            flash("Invalid username/email or password.", "danger")
            return render_template("auth/login.html", form=form)

        if user.status != "Active":
            flash("This account is not active. Contact an administrator.", "danger")
            return render_template("auth/login.html", form=form)

        login_user(user, remember=form.remember_me.data)
        user.last_login = datetime.utcnow()
        log_action("login", "User", user.id, f"{user.username} logged in")
        db.session.commit()

        next_page = request.args.get("next")
        return redirect(next_page or url_for("main.dashboard"))

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    log_action("logout", "User", current_user.id, f"{current_user.username} logged out")
    db.session.commit()
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/profile")
@login_required
def profile():
    return render_template("auth/profile.html")


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("Current password is incorrect.", "danger")
        elif form.new_password.data != form.confirm_password.data:
            flash("New password and confirmation do not match.", "danger")
        else:
            current_user.set_password(form.new_password.data)
            log_action("update", "User", current_user.id, "Password changed")
            db.session.commit()
            flash("Password updated successfully.", "success")
            return redirect(url_for("auth.profile"))
    return render_template("auth/change_password.html", form=form)
