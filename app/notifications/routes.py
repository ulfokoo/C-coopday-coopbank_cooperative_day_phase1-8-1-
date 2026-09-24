from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, request
from flask_login import login_required, current_user

from app.extensions import db
from app.models.notification import Notification, NOTIFICATION_CATEGORIES

notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.route("/")
@login_required
def notifications_list():
    page = request.args.get("page", 1, type=int)
    only_unread = request.args.get("unread", "") == "1"
    category = request.args.get("category", "")

    query = Notification.query.filter_by(user_id=current_user.id)
    if only_unread:
        query = query.filter_by(is_read=False)
    if category:
        query = query.filter_by(category=category)

    pagination = query.order_by(Notification.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template(
        "notifications/list.html", pagination=pagination, categories=NOTIFICATION_CATEGORIES,
        only_unread=only_unread, selected_category=category,
    )


@notifications_bp.route("/<int:notification_id>/open")
@login_required
def notification_open(notification_id):
    n = Notification.query.filter_by(id=notification_id, user_id=current_user.id).first_or_404()
    if not n.is_read:
        n.is_read = True
        n.read_at = datetime.utcnow()
        db.session.commit()
    return redirect(n.link or url_for("notifications.notifications_list"))


@notifications_bp.route("/<int:notification_id>/mark-read", methods=["POST"])
@login_required
def notification_mark_read(notification_id):
    n = Notification.query.filter_by(id=notification_id, user_id=current_user.id).first_or_404()
    n.is_read = True
    n.read_at = datetime.utcnow()
    db.session.commit()
    return redirect(request.referrer or url_for("notifications.notifications_list"))


@notifications_bp.route("/mark-all-read", methods=["POST"])
@login_required
def notifications_mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update(
        {"is_read": True, "read_at": datetime.utcnow()}
    )
    db.session.commit()
    return redirect(request.referrer or url_for("notifications.notifications_list"))
