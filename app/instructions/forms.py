from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateField, SubmitField
from wtforms.validators import DataRequired, Optional, Length

from app.models.instruction import INSTRUCTION_PRIORITIES, INSTRUCTION_STATUSES, DECISION_STATUSES


class InstructionForm(FlaskForm):
    title = StringField("Instruction Title", validators=[DataRequired(), Length(max=200)])
    description = TextAreaField("Description", validators=[Optional()])
    cooperative_day_id = SelectField("Cooperative Day", coerce=int, validators=[DataRequired()])
    source_person = StringField("Source / Issued By", validators=[Optional(), Length(max=150)])
    instruction_date = DateField("Instruction Date", validators=[Optional()])
    department_id = SelectField("Responsible Department", coerce=int, validators=[Optional()])
    responsible_user_id = SelectField("Responsible Person", coerce=int, validators=[Optional()])
    team_id = SelectField("Related Team", coerce=int, validators=[Optional()])
    task_id = SelectField("Related Task", coerce=int, validators=[Optional()])
    deadline = DateField("Deadline", validators=[Optional()])
    priority = SelectField("Priority", choices=[(p, p) for p in INSTRUCTION_PRIORITIES])
    status = SelectField("Status", choices=[(s, s) for s in INSTRUCTION_STATUSES])
    submit = SubmitField("Save Instruction")


class DecisionForm(FlaskForm):
    title = StringField("Decision", validators=[DataRequired(), Length(max=200)])
    description = TextAreaField("Description", validators=[Optional()])
    decision_date = DateField("Decision Date", validators=[Optional()])
    responsible_user_id = SelectField("Responsible Person", coerce=int, validators=[Optional()])
    related_task_id = SelectField("Related Task", coerce=int, validators=[Optional()])
    status = SelectField("Status", choices=[(s, s) for s in DECISION_STATUSES])
    submit = SubmitField("Save Decision")
