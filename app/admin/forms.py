from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, SelectField, BooleanField, SubmitField, TextAreaField
)
from wtforms.validators import DataRequired, Email, Length, Optional, EqualTo


class UserForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=150)])
    username = StringField("Username", validators=[DataRequired(), Length(max=80)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=150)])
    phone = StringField("Phone", validators=[Optional(), Length(max=30)])
    position = StringField("Position", validators=[Optional(), Length(max=120)])
    department_id = SelectField("Department", coerce=int, validators=[Optional()])
    role_id = SelectField("Role", coerce=int, validators=[DataRequired()])
    status = SelectField(
        "Status", choices=[("Active", "Active"), ("Inactive", "Inactive"), ("Suspended", "Suspended")]
    )
    password = PasswordField(
        "Password",
        validators=[Optional(), Length(min=8, message="Password must be at least 8 characters.")],
    )
    submit = SubmitField("Save User")


class RoleForm(FlaskForm):
    name = StringField("Role Name", validators=[DataRequired(), Length(max=80)])
    description = StringField("Description", validators=[Optional(), Length(max=255)])
    is_super_admin = BooleanField("Full access (bypasses all permission checks)")
    submit = SubmitField("Save Role")


class DepartmentForm(FlaskForm):
    name = StringField("Department Name", validators=[DataRequired(), Length(max=120)])
    description = TextAreaField("Description", validators=[Optional()])
    is_active = BooleanField("Active", default=True)
    submit = SubmitField("Save Department")
