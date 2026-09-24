from datetime import date, datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.extensions import db
from app.models.procurement import (
    Supplier, ProcurementRequest, ProcurementItem, Material,
    PROCUREMENT_STATUSES, SUPPLIER_STATUSES, MATERIAL_STATUSES,
)
from app.models.event import CooperativeDay
from app.models.department import Department
from app.models.team import Team
from app.models.user import User
from app.procurement.forms import ProcurementRequestForm, ProcurementItemForm, SupplierForm, MaterialForm
from app.utils.decorators import permission_required
from app.utils.audit import log_action
from app.utils.notifications import notify, notify_users_with_permission

procurement_bp = Blueprint("procurement", __name__)


# ---------------------------------------------------------------------------
# Purchase requests
# ---------------------------------------------------------------------------

@procurement_bp.route("/")
@login_required
@permission_required("view_procurement")
def requests_list():
    event_id = request.args.get("event_id", type=int)
    department_id = request.args.get("department_id", type=int)
    status = request.args.get("status", "")
    keyword = request.args.get("q", "").strip()

    query = ProcurementRequest.query
    if event_id:
        query = query.filter_by(cooperative_day_id=event_id)
    if department_id:
        query = query.filter_by(department_id=department_id)
    if status:
        query = query.filter_by(status=status)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            db.or_(ProcurementRequest.request_number.ilike(like), ProcurementRequest.item_service.ilike(like))
        )

    requests_ = query.order_by(ProcurementRequest.created_at.desc()).all()
    events = CooperativeDay.query.order_by(CooperativeDay.year.desc()).all()
    departments = Department.query.filter_by(is_active=True).order_by(Department.name).all()

    return render_template(
        "procurement/requests_list.html", requests=requests_, events=events, departments=departments,
        statuses=PROCUREMENT_STATUSES, selected_event_id=event_id, selected_department_id=department_id,
        selected_status=status, keyword=keyword, today=date.today(),
    )


@procurement_bp.route("/requests/new", methods=["GET", "POST"])
@login_required
@permission_required("create_purchase_request")
def request_new():
    form = ProcurementRequestForm()
    _populate_request_choices(form)
    if form.validate_on_submit():
        if ProcurementRequest.query.filter_by(request_number=form.request_number.data).first():
            flash("That request number is already in use.", "danger")
            return render_template("procurement/request_form.html", form=form, is_new=True)

        pr = ProcurementRequest(
            request_number=form.request_number.data,
            cooperative_day_id=form.cooperative_day_id.data,
            department_id=form.department_id.data or None,
            team_id=form.team_id.data or None,
            requested_by_id=form.requested_by_id.data or current_user.id,
            item_service=form.item_service.data,
            description=form.description.data,
            quantity=form.quantity.data or 1,
            unit=form.unit.data,
            estimated_cost=form.estimated_cost.data,
            required_date=form.required_date.data,
            justification=form.justification.data,
            priority=form.priority.data,
            status=form.status.data,
            supplier_id=form.supplier_id.data or None,
            po_number=form.po_number.data,
            order_date=form.order_date.data,
            expected_delivery_date=form.expected_delivery_date.data,
            actual_delivery_date=form.actual_delivery_date.data,
            inspected_by_id=form.inspected_by_id.data or None,
            inspection_notes=form.inspection_notes.data,
            payment_status=form.payment_status.data,
            paid_amount=form.paid_amount.data,
            payment_date=form.payment_date.data,
            created_by_id=current_user.id,
        )
        db.session.add(pr)
        db.session.flush()
        log_action("create", "ProcurementRequest", pr.id, f"Created purchase request {pr.request_number}")
        if pr.status in ("Submitted", "Under Review"):
            notify_users_with_permission(
                "approve_purchase", f"Purchase request needs approval: {pr.request_number}",
                f"'{pr.item_service}' ({pr.quantity or 1} {pr.unit or ''}) submitted by "
                f"{pr.requested_by.full_name if pr.requested_by else 'a staff member'}.",
                category="Procurement", link=f"/procurement/requests/{pr.id}",
                entity_type="ProcurementRequest", entity_id=pr.id, exclude_user_id=current_user.id,
            )
        db.session.commit()
        flash(f"Purchase request '{pr.request_number}' created.", "success")
        return redirect(url_for("procurement.request_detail", request_id=pr.id))
    return render_template("procurement/request_form.html", form=form, is_new=True)


@procurement_bp.route("/requests/<int:request_id>")
@login_required
@permission_required("view_procurement")
def request_detail(request_id):
    pr = ProcurementRequest.query.get_or_404(request_id)
    item_form = ProcurementItemForm()
    _populate_item_choices(item_form)
    suppliers = Supplier.query.filter_by(status="Active").order_by(Supplier.name).all()
    return render_template(
        "procurement/request_detail.html", pr=pr, item_form=item_form, suppliers=suppliers, today=date.today(),
    )


@procurement_bp.route("/requests/<int:request_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("create_purchase_request")
def request_edit(request_id):
    pr = ProcurementRequest.query.get_or_404(request_id)
    form = ProcurementRequestForm(obj=pr)
    _populate_request_choices(form)
    if request.method == "GET":
        form.department_id.data = pr.department_id or 0
        form.team_id.data = pr.team_id or 0
        form.requested_by_id.data = pr.requested_by_id or 0
        form.supplier_id.data = pr.supplier_id or 0
        form.inspected_by_id.data = pr.inspected_by_id or 0

    if form.validate_on_submit():
        existing = ProcurementRequest.query.filter(
            ProcurementRequest.request_number == form.request_number.data, ProcurementRequest.id != pr.id
        ).first()
        if existing:
            flash("That request number is already in use.", "danger")
            return render_template("procurement/request_form.html", form=form, is_new=False, pr=pr)

        pr.request_number = form.request_number.data
        pr.cooperative_day_id = form.cooperative_day_id.data
        pr.department_id = form.department_id.data or None
        pr.team_id = form.team_id.data or None
        pr.requested_by_id = form.requested_by_id.data or None
        pr.item_service = form.item_service.data
        pr.description = form.description.data
        pr.quantity = form.quantity.data or 1
        pr.unit = form.unit.data
        pr.estimated_cost = form.estimated_cost.data
        pr.required_date = form.required_date.data
        pr.justification = form.justification.data
        pr.priority = form.priority.data
        pr.status = form.status.data
        pr.supplier_id = form.supplier_id.data or None
        pr.po_number = form.po_number.data
        pr.order_date = form.order_date.data
        pr.expected_delivery_date = form.expected_delivery_date.data
        pr.actual_delivery_date = form.actual_delivery_date.data
        pr.inspected_by_id = form.inspected_by_id.data or None
        pr.inspection_notes = form.inspection_notes.data
        pr.payment_status = form.payment_status.data
        pr.paid_amount = form.paid_amount.data
        pr.payment_date = form.payment_date.data
        log_action("update", "ProcurementRequest", pr.id, f"Updated purchase request {pr.request_number}")
        db.session.commit()
        flash("Purchase request updated.", "success")
        return redirect(url_for("procurement.request_detail", request_id=pr.id))
    return render_template("procurement/request_form.html", form=form, is_new=False, pr=pr)


@procurement_bp.route("/requests/<int:request_id>/status/<string:new_status>", methods=["POST"])
@login_required
@permission_required("approve_purchase")
def request_status(request_id, new_status):
    pr = ProcurementRequest.query.get_or_404(request_id)
    if new_status not in PROCUREMENT_STATUSES:
        flash("Invalid status.", "danger")
        return redirect(url_for("procurement.request_detail", request_id=pr.id))

    pr.status = new_status
    # Light bookkeeping so the workflow's key milestones stay honest even
    # when a status is set directly (rather than only through the edit form).
    if new_status == "Ordered" and not pr.order_date:
        pr.order_date = date.today()
    if new_status == "Delivered" and not pr.actual_delivery_date:
        pr.actual_delivery_date = date.today()
    if new_status == "Delivered" and not pr.inspected_by_id:
        pr.inspected_by_id = current_user.id
        pr.inspected_at = datetime.utcnow()
    if new_status == "Completed" and pr.payment_status == "Not Paid" and pr.paid_amount:
        pr.payment_status = "Paid"
        pr.payment_date = pr.payment_date or date.today()

    log_action("update", "ProcurementRequest", pr.id, f"Status changed to {new_status}")

    if new_status in ("Submitted", "Under Review"):
        notify_users_with_permission(
            "approve_purchase", f"Purchase request needs approval: {pr.request_number}",
            f"'{pr.item_service}' is now '{new_status}' and awaiting action.",
            category="Procurement", link=f"/procurement/requests/{pr.id}",
            entity_type="ProcurementRequest", entity_id=pr.id, exclude_user_id=current_user.id,
        )
    elif new_status in ("Approved", "Rejected") and pr.requested_by_id:
        notify(
            pr.requested_by_id, f"Purchase request {new_status.lower()}: {pr.request_number}",
            f"'{pr.item_service}' was {new_status.lower()}.",
            category="Procurement", link=f"/procurement/requests/{pr.id}",
            entity_type="ProcurementRequest", entity_id=pr.id,
        )

    db.session.commit()
    flash(f"Purchase request status set to {new_status}.", "success")
    return redirect(url_for("procurement.request_detail", request_id=pr.id))


# ---------------------------------------------------------------------------
# Line items
# ---------------------------------------------------------------------------

@procurement_bp.route("/requests/<int:request_id>/items/new", methods=["POST"])
@login_required
@permission_required("create_purchase_request")
def item_new(request_id):
    pr = ProcurementRequest.query.get_or_404(request_id)
    form = ProcurementItemForm()
    _populate_item_choices(form)
    if form.validate_on_submit():
        item = ProcurementItem(
            procurement_request_id=pr.id,
            item_name=form.item_name.data,
            quantity=form.quantity.data or 1,
            unit=form.unit.data,
            unit_cost=form.unit_cost.data,
            status=form.status.data,
            responsible_user_id=form.responsible_user_id.data or None,
            notes=form.notes.data,
        )
        db.session.add(item)
        log_action("create", "ProcurementItem", pr.id, f"Added item '{item.item_name}' to {pr.request_number}")
        db.session.commit()
        flash(f"Item '{item.item_name}' added.", "success")
    else:
        flash("Could not add item — check the fields and try again.", "danger")
    return redirect(url_for("procurement.request_detail", request_id=pr.id))


@procurement_bp.route("/items/<int:item_id>/status/<string:new_status>", methods=["POST"])
@login_required
@permission_required("create_purchase_request")
def item_status(item_id, new_status):
    item = ProcurementItem.query.get_or_404(item_id)
    from app.models.procurement import PROCUREMENT_ITEM_STATUSES
    if new_status not in PROCUREMENT_ITEM_STATUSES:
        flash("Invalid status.", "danger")
        return redirect(url_for("procurement.request_detail", request_id=item.procurement_request_id))
    item.status = new_status
    log_action("update", "ProcurementItem", item.id, f"Item status changed to {new_status}")
    db.session.commit()
    flash("Item status updated.", "success")
    return redirect(url_for("procurement.request_detail", request_id=item.procurement_request_id))


@procurement_bp.route("/items/<int:item_id>/delete", methods=["POST"])
@login_required
@permission_required("create_purchase_request")
def item_delete(item_id):
    item = ProcurementItem.query.get_or_404(item_id)
    request_id = item.procurement_request_id
    item_name = item.item_name
    db.session.delete(item)
    log_action("delete", "ProcurementItem", request_id, f"Removed item '{item_name}'")
    db.session.commit()
    flash(f"Item '{item_name}' removed.", "success")
    return redirect(url_for("procurement.request_detail", request_id=request_id))


# ---------------------------------------------------------------------------
# Suppliers
# ---------------------------------------------------------------------------

@procurement_bp.route("/suppliers")
@login_required
@permission_required("view_procurement")
def suppliers_list():
    keyword = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    query = Supplier.query
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            db.or_(Supplier.name.ilike(like), Supplier.service_category.ilike(like))
        )
    if status:
        query = query.filter_by(status=status)
    suppliers = query.order_by(Supplier.name).all()
    return render_template(
        "procurement/suppliers_list.html", suppliers=suppliers, statuses=SUPPLIER_STATUSES,
        keyword=keyword, selected_status=status,
    )


@procurement_bp.route("/suppliers/new", methods=["GET", "POST"])
@login_required
@permission_required("manage_suppliers")
def supplier_new():
    form = SupplierForm()
    if form.validate_on_submit():
        supplier = Supplier(
            name=form.name.data, contact_person=form.contact_person.data, phone=form.phone.data,
            email=form.email.data, address=form.address.data, service_category=form.service_category.data,
            registration_info=form.registration_info.data, notes=form.notes.data, status=form.status.data,
        )
        db.session.add(supplier)
        db.session.flush()
        log_action("create", "Supplier", supplier.id, f"Added supplier '{supplier.name}'")
        db.session.commit()
        flash(f"Supplier '{supplier.name}' added.", "success")
        return redirect(url_for("procurement.supplier_detail", supplier_id=supplier.id))
    return render_template("procurement/supplier_form.html", form=form, is_new=True)


@procurement_bp.route("/suppliers/<int:supplier_id>")
@login_required
@permission_required("view_procurement")
def supplier_detail(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    linked_requests = supplier.requests.order_by(ProcurementRequest.created_at.desc()).all()
    return render_template("procurement/supplier_detail.html", supplier=supplier, linked_requests=linked_requests)


@procurement_bp.route("/suppliers/<int:supplier_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("manage_suppliers")
def supplier_edit(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    form = SupplierForm(obj=supplier)
    if form.validate_on_submit():
        supplier.name = form.name.data
        supplier.contact_person = form.contact_person.data
        supplier.phone = form.phone.data
        supplier.email = form.email.data
        supplier.address = form.address.data
        supplier.service_category = form.service_category.data
        supplier.registration_info = form.registration_info.data
        supplier.notes = form.notes.data
        supplier.status = form.status.data
        log_action("update", "Supplier", supplier.id, f"Updated supplier '{supplier.name}'")
        db.session.commit()
        flash("Supplier updated.", "success")
        return redirect(url_for("procurement.supplier_detail", supplier_id=supplier.id))
    return render_template("procurement/supplier_form.html", form=form, is_new=False, supplier=supplier)


# ---------------------------------------------------------------------------
# Materials / assets
# ---------------------------------------------------------------------------

@procurement_bp.route("/materials")
@login_required
@permission_required("view_procurement")
def materials_list():
    event_id = request.args.get("event_id", type=int)
    status = request.args.get("status", "")
    query = Material.query
    if event_id:
        query = query.filter_by(cooperative_day_id=event_id)
    if status:
        query = query.filter_by(status=status)
    materials = query.order_by(Material.item_name).all()
    events = CooperativeDay.query.order_by(CooperativeDay.year.desc()).all()
    return render_template(
        "procurement/materials_list.html", materials=materials, events=events, statuses=MATERIAL_STATUSES,
        selected_event_id=event_id, selected_status=status,
    )


@procurement_bp.route("/materials/new", methods=["GET", "POST"])
@login_required
@permission_required("manage_materials")
def material_new():
    form = MaterialForm()
    _populate_material_choices(form)
    if form.validate_on_submit():
        material = Material(
            cooperative_day_id=form.cooperative_day_id.data, item_name=form.item_name.data,
            category=form.category.data, quantity_required=form.quantity_required.data or 0,
            quantity_available=form.quantity_available.data or 0,
            quantity_purchased=form.quantity_purchased.data or 0,
            responsible_user_id=form.responsible_user_id.data or None,
            location=form.location.data, status=form.status.data, notes=form.notes.data,
        )
        db.session.add(material)
        db.session.flush()
        log_action("create", "Material", material.id, f"Added material '{material.item_name}'")
        db.session.commit()
        flash(f"Material '{material.item_name}' added.", "success")
        return redirect(url_for("procurement.material_detail", material_id=material.id))
    return render_template("procurement/material_form.html", form=form, is_new=True)


@procurement_bp.route("/materials/<int:material_id>")
@login_required
@permission_required("view_procurement")
def material_detail(material_id):
    material = Material.query.get_or_404(material_id)
    return render_template("procurement/material_detail.html", material=material)


@procurement_bp.route("/materials/<int:material_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("manage_materials")
def material_edit(material_id):
    material = Material.query.get_or_404(material_id)
    form = MaterialForm(obj=material)
    _populate_material_choices(form)
    if request.method == "GET":
        form.responsible_user_id.data = material.responsible_user_id or 0
    if form.validate_on_submit():
        material.cooperative_day_id = form.cooperative_day_id.data
        material.item_name = form.item_name.data
        material.category = form.category.data
        material.quantity_required = form.quantity_required.data or 0
        material.quantity_available = form.quantity_available.data or 0
        material.quantity_purchased = form.quantity_purchased.data or 0
        material.responsible_user_id = form.responsible_user_id.data or None
        material.location = form.location.data
        material.status = form.status.data
        material.notes = form.notes.data
        log_action("update", "Material", material.id, f"Updated material '{material.item_name}'")
        db.session.commit()
        flash("Material updated.", "success")
        return redirect(url_for("procurement.material_detail", material_id=material.id))
    return render_template("procurement/material_form.html", form=form, is_new=False, material=material)


@procurement_bp.route("/materials/<int:material_id>/status/<string:new_status>", methods=["POST"])
@login_required
@permission_required("manage_materials")
def material_status(material_id, new_status):
    material = Material.query.get_or_404(material_id)
    if new_status not in MATERIAL_STATUSES:
        flash("Invalid status.", "danger")
        return redirect(url_for("procurement.material_detail", material_id=material.id))
    material.status = new_status
    log_action("update", "Material", material.id, f"Status changed to {new_status}")
    db.session.commit()
    flash(f"Material status set to {new_status}.", "success")
    return redirect(url_for("procurement.material_detail", material_id=material.id))


# ---------------------------------------------------------------------------
# Choice helpers
# ---------------------------------------------------------------------------

def _populate_request_choices(form):
    form.cooperative_day_id.choices = [
        (e.id, e.name) for e in CooperativeDay.query.order_by(CooperativeDay.year.desc())
    ]
    form.department_id.choices = [(0, "— None —")] + [
        (d.id, d.name) for d in Department.query.filter_by(is_active=True).order_by(Department.name)
    ]
    form.team_id.choices = [(0, "— None —")] + [(t.id, t.name) for t in Team.query.order_by(Team.name)]
    active_users = [(u.id, u.full_name) for u in User.query.filter_by(status="Active").order_by(User.full_name)]
    form.requested_by_id.choices = [(0, "— Unassigned —")] + active_users
    form.inspected_by_id.choices = [(0, "— Not Inspected —")] + active_users
    form.supplier_id.choices = [(0, "— None Selected —")] + [
        (s.id, s.name) for s in Supplier.query.filter_by(status="Active").order_by(Supplier.name)
    ]


def _populate_item_choices(form):
    form.responsible_user_id.choices = [(0, "— Unassigned —")] + [
        (u.id, u.full_name) for u in User.query.filter_by(status="Active").order_by(User.full_name)
    ]


def _populate_material_choices(form):
    form.cooperative_day_id.choices = [
        (e.id, e.name) for e in CooperativeDay.query.order_by(CooperativeDay.year.desc())
    ]
    form.responsible_user_id.choices = [(0, "— Unassigned —")] + [
        (u.id, u.full_name) for u in User.query.filter_by(status="Active").order_by(User.full_name)
    ]
