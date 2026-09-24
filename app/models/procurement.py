from datetime import datetime, date
from app.extensions import db

# Full lifecycle per spec:
# Request -> Approval -> Supplier quotation -> Evaluation -> Purchase order
# -> Delivery -> Inspection -> Payment -> Completion
PROCUREMENT_STATUSES = [
    "Draft", "Submitted", "Under Review", "Approved", "Rejected",
    "Procurement", "Ordered", "Delivered", "Completed", "Cancelled",
]

PROCUREMENT_PRIORITIES = ["Low", "Medium", "High", "Critical"]

PAYMENT_STATUSES = ["Not Paid", "Partially Paid", "Paid"]

# Individual line-item statuses (e.g. "Event banners — Qty 20 — Ordered")
PROCUREMENT_ITEM_STATUSES = ["Requested", "Ordered", "Delivered", "Completed", "Cancelled"]

SUPPLIER_STATUSES = ["Active", "Inactive"]

MATERIAL_STATUSES = ["Needed", "Requested", "Purchased", "Available", "Deployed", "Returned"]


class Supplier(db.Model):
    """A vendor/supplier that can be linked to procurement requests."""

    __tablename__ = "suppliers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    contact_person = db.Column(db.String(120))
    phone = db.Column(db.String(30))
    email = db.Column(db.String(150))
    address = db.Column(db.String(255))
    service_category = db.Column(db.String(120))  # e.g. Printing, Catering, Media, Furniture
    registration_info = db.Column(db.String(255))  # TIN / trade license / registration number
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default="Active", nullable=False, index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    requests = db.relationship("ProcurementRequest", backref="supplier", lazy="dynamic")

    def __repr__(self):
        return f"<Supplier {self.name}>"


class ProcurementRequest(db.Model):
    """A purchase request, tracked end-to-end from request through payment."""

    __tablename__ = "procurement_requests"

    id = db.Column(db.Integer, primary_key=True)
    request_number = db.Column(db.String(60), unique=True, nullable=False, index=True)

    cooperative_day_id = db.Column(db.Integer, db.ForeignKey("cooperative_days.id"), nullable=False, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"))
    requested_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    item_service = db.Column(db.String(200), nullable=False)  # what's being requested, in short
    description = db.Column(db.Text)
    quantity = db.Column(db.Integer, default=1)
    unit = db.Column(db.String(30))
    estimated_cost = db.Column(db.Float)
    required_date = db.Column(db.Date)
    justification = db.Column(db.Text)

    priority = db.Column(db.String(20), default="Medium", nullable=False)
    status = db.Column(db.String(20), default="Draft", nullable=False, index=True)

    # Supplier selection / purchase order
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"))
    po_number = db.Column(db.String(60))
    order_date = db.Column(db.Date)

    # Delivery & inspection
    expected_delivery_date = db.Column(db.Date)
    actual_delivery_date = db.Column(db.Date)
    inspected_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    inspected_at = db.Column(db.DateTime)
    inspection_notes = db.Column(db.Text)

    # Payment / completion
    payment_status = db.Column(db.String(20), default="Not Paid", nullable=False)
    paid_amount = db.Column(db.Float)
    payment_date = db.Column(db.Date)

    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    cooperative_day = db.relationship("CooperativeDay", backref=db.backref("procurement_requests", lazy="dynamic"))
    department = db.relationship("Department")
    team = db.relationship("Team")
    requested_by = db.relationship("User", foreign_keys=[requested_by_id])
    inspected_by = db.relationship("User", foreign_keys=[inspected_by_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])

    items = db.relationship(
        "ProcurementItem", backref="request", lazy="dynamic", cascade="all, delete-orphan"
    )

    @property
    def is_overdue(self):
        return bool(
            self.required_date and self.required_date < date.today()
            and self.status not in ("Completed", "Cancelled", "Delivered")
        )

    @property
    def items_total_cost(self):
        total = 0.0
        for item in self.items:
            if item.unit_cost and item.quantity:
                total += item.unit_cost * item.quantity
        return total

    def __repr__(self):
        return f"<ProcurementRequest {self.request_number}>"


class ProcurementItem(db.Model):
    """One line item within a purchase request, e.g. 'Event banners x20'."""

    __tablename__ = "procurement_items"

    id = db.Column(db.Integer, primary_key=True)
    procurement_request_id = db.Column(db.Integer, db.ForeignKey("procurement_requests.id"), nullable=False)

    item_name = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    unit = db.Column(db.String(30))
    unit_cost = db.Column(db.Float)
    status = db.Column(db.String(20), default="Requested", nullable=False)
    responsible_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    notes = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    responsible_user = db.relationship("User")

    @property
    def line_total(self):
        if self.unit_cost and self.quantity:
            return self.unit_cost * self.quantity
        return 0.0

    def __repr__(self):
        return f"<ProcurementItem {self.item_name}>"


class Material(db.Model):
    """Event material / asset tracking (chairs, tents, banners, sound
    systems...) — required vs. available vs. purchased quantities, per
    Cooperative Day year. Distinct from ProcurementItem: a Material row can
    exist before any purchase request does (planning stage), and can be
    fulfilled from stock rather than a purchase."""

    __tablename__ = "materials"

    id = db.Column(db.Integer, primary_key=True)
    cooperative_day_id = db.Column(db.Integer, db.ForeignKey("cooperative_days.id"), nullable=False, index=True)

    item_name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100))  # e.g. Furniture, Signage, AV Equipment, Print Materials

    quantity_required = db.Column(db.Integer, default=0, nullable=False)
    quantity_available = db.Column(db.Integer, default=0, nullable=False)
    quantity_purchased = db.Column(db.Integer, default=0, nullable=False)

    responsible_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    location = db.Column(db.String(150))
    status = db.Column(db.String(20), default="Needed", nullable=False, index=True)
    notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    cooperative_day = db.relationship("CooperativeDay", backref=db.backref("materials", lazy="dynamic"))
    responsible_user = db.relationship("User")

    @property
    def shortfall(self):
        have = (self.quantity_available or 0) + (self.quantity_purchased or 0)
        return max((self.quantity_required or 0) - have, 0)

    def __repr__(self):
        return f"<Material {self.item_name}>"
