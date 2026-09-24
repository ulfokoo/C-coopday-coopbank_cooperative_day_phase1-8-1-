from flask_wtf import FlaskForm
from wtforms import (
    StringField, TextAreaField, SelectField, IntegerField, FloatField, DateField, SubmitField,
)
from wtforms.validators import DataRequired, Optional, Length, NumberRange

from app.models.procurement import (
    PROCUREMENT_PRIORITIES, PROCUREMENT_STATUSES, PROCUREMENT_ITEM_STATUSES,
    PAYMENT_STATUSES, SUPPLIER_STATUSES, MATERIAL_STATUSES,
)


class ProcurementRequestForm(FlaskForm):
    request_number = StringField("Request Number", validators=[DataRequired(), Length(max=60)])
    cooperative_day_id = SelectField("Cooperative Day", coerce=int, validators=[DataRequired()])
    department_id = SelectField("Department", coerce=int, validators=[Optional()])
    team_id = SelectField("Team", coerce=int, validators=[Optional()])
    requested_by_id = SelectField("Requested By", coerce=int, validators=[Optional()])

    item_service = StringField("Item / Service", validators=[DataRequired(), Length(max=200)])
    description = TextAreaField("Description", validators=[Optional()])
    quantity = IntegerField("Quantity", validators=[Optional(), NumberRange(min=1)], default=1)
    unit = StringField("Unit", validators=[Optional(), Length(max=30)])
    estimated_cost = FloatField("Estimated Cost", validators=[Optional(), NumberRange(min=0)])
    required_date = DateField("Required Date", validators=[Optional()])
    justification = TextAreaField("Justification", validators=[Optional()])

    priority = SelectField("Priority", choices=[(p, p) for p in PROCUREMENT_PRIORITIES])
    status = SelectField("Status", choices=[(s, s) for s in PROCUREMENT_STATUSES])

    supplier_id = SelectField("Supplier", coerce=int, validators=[Optional()])
    po_number = StringField("PO Number", validators=[Optional(), Length(max=60)])
    order_date = DateField("Order Date", validators=[Optional()])

    expected_delivery_date = DateField("Expected Delivery Date", validators=[Optional()])
    actual_delivery_date = DateField("Actual Delivery Date", validators=[Optional()])
    inspected_by_id = SelectField("Inspected By", coerce=int, validators=[Optional()])
    inspection_notes = TextAreaField("Inspection Notes", validators=[Optional()])

    payment_status = SelectField("Payment Status", choices=[(p, p) for p in PAYMENT_STATUSES])
    paid_amount = FloatField("Paid Amount", validators=[Optional(), NumberRange(min=0)])
    payment_date = DateField("Payment Date", validators=[Optional()])

    submit = SubmitField("Save Purchase Request")


class ProcurementItemForm(FlaskForm):
    item_name = StringField("Item Name", validators=[DataRequired(), Length(max=200)])
    quantity = IntegerField("Quantity", validators=[DataRequired(), NumberRange(min=1)], default=1)
    unit = StringField("Unit", validators=[Optional(), Length(max=30)])
    unit_cost = FloatField("Unit Cost", validators=[Optional(), NumberRange(min=0)])
    status = SelectField("Status", choices=[(s, s) for s in PROCUREMENT_ITEM_STATUSES])
    responsible_user_id = SelectField("Responsible", coerce=int, validators=[Optional()])
    notes = StringField("Notes", validators=[Optional(), Length(max=255)])
    submit = SubmitField("Add Item")


class SupplierForm(FlaskForm):
    name = StringField("Supplier Name", validators=[DataRequired(), Length(max=150)])
    contact_person = StringField("Contact Person", validators=[Optional(), Length(max=120)])
    phone = StringField("Phone", validators=[Optional(), Length(max=30)])
    email = StringField("Email", validators=[Optional(), Length(max=150)])
    address = StringField("Address", validators=[Optional(), Length(max=255)])
    service_category = StringField("Service Category", validators=[Optional(), Length(max=120)])
    registration_info = StringField("Registration Info", validators=[Optional(), Length(max=255)])
    notes = TextAreaField("Notes", validators=[Optional()])
    status = SelectField("Status", choices=[(s, s) for s in SUPPLIER_STATUSES])
    submit = SubmitField("Save Supplier")


class MaterialForm(FlaskForm):
    cooperative_day_id = SelectField("Cooperative Day", coerce=int, validators=[DataRequired()])
    item_name = StringField("Item Name", validators=[DataRequired(), Length(max=200)])
    category = StringField("Category", validators=[Optional(), Length(max=100)])
    quantity_required = IntegerField("Quantity Required", validators=[Optional(), NumberRange(min=0)], default=0)
    quantity_available = IntegerField("Quantity Available", validators=[Optional(), NumberRange(min=0)], default=0)
    quantity_purchased = IntegerField("Quantity Purchased", validators=[Optional(), NumberRange(min=0)], default=0)
    responsible_user_id = SelectField("Responsible", coerce=int, validators=[Optional()])
    location = StringField("Location", validators=[Optional(), Length(max=150)])
    status = SelectField("Status", choices=[(s, s) for s in MATERIAL_STATUSES])
    notes = TextAreaField("Notes", validators=[Optional()])
    submit = SubmitField("Save Material")
