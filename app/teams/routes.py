import re
from io import BytesIO

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, send_file
from flask_login import login_required, current_user

from app.extensions import db
from app.models.team import Team, TeamMember, WINDOW_SECTIONS
from app.models.document import Document
from app.models.event import CooperativeDay
from app.models.user import User
from app.teams.forms import TeamForm, TeamMemberForm, WindowForm, ActionForm, DistrictForm
from app.utils.decorators import permission_required
from app.utils.audit import log_action

teams_bp = Blueprint("teams", __name__)


def _uses_windows(team):
    """Only the Invitation / Registration / Per-diem team uses window leaders + staff."""
    return "invitation" in (team.name or "").lower()


def _section_query(team, section):
    """Top-level leaders of one section. Older leaders with no section count as the first one."""
    query = team.members.filter_by(parent_id=None)
    if section == WINDOW_SECTIONS[0]:
        return query.filter(db.or_(TeamMember.section == section, TeamMember.section.is_(None)))
    return query.filter(TeamMember.section == section)


def _window_sort_key(member):
    """Sort by the number in the window label (Window 2 before Window 10).
    Members with no window go last."""
    match = re.search(r"\d+", member.window_label or "")
    number = int(match.group()) if match else 10**9
    return (number, (member.window_label or "").lower(), member.id)


def _back(team_id, section=None):
    return redirect(url_for("teams.team_detail", team_id=team_id, section=section))


def _export_context(team):
    """Resolve (use_windows, section, members) for the export routes,
    mirroring the logic in team_detail()."""
    use_windows = _uses_windows(team)
    section = None
    if use_windows:
        section = request.args.get("section")
        if section not in WINDOW_SECTIONS:
            section = WINDOW_SECTIONS[0]
        members = _section_query(team, section).order_by(TeamMember.id).all()
        members.sort(key=_window_sort_key)
    else:
        members = team.members.filter_by(parent_id=None).order_by(TeamMember.id).all()
    return use_windows, section, members


def _safe_filename(*parts):
    name = "_".join(p for p in parts if p)
    name = re.sub(r"[^A-Za-z0-9_\-]+", "_", name).strip("_")
    return name or "export"


def _is_team_manager(team):
    """Admin (manage_teams permission) OR the leader of this very team."""
    return current_user.has_permission("manage_teams") or team.leader_id == current_user.id


def _is_team_viewer(team):
    """Managers plus ordinary members of the team can open it."""
    if _is_team_manager(team):
        return True
    return TeamMember.query.filter_by(team_id=team.id, user_id=current_user.id).first() is not None


@teams_bp.route("/")
@login_required
def teams_list():
    event_id = request.args.get("event_id", type=int)
    query = Team.query
    # Admins see every team; everyone else sees only teams they lead or belong to.
    if not current_user.has_permission("manage_teams"):
        member_team_ids = db.session.query(TeamMember.team_id).filter_by(user_id=current_user.id)
        query = query.filter(
            db.or_(Team.leader_id == current_user.id, Team.id.in_(member_team_ids))
        )
    if event_id:
        query = query.filter_by(cooperative_day_id=event_id)
    teams = query.order_by(Team.cooperative_day_id.desc(), Team.name).all()
    events = CooperativeDay.query.order_by(CooperativeDay.year.desc()).all()
    return render_template("teams/list.html", teams=teams, events=events, selected_event_id=event_id)


@teams_bp.route("/new", methods=["GET", "POST"])
@login_required
@permission_required("manage_teams")
def team_new():
    form = TeamForm()
    _populate_choices(form)
    if form.validate_on_submit():
        team = Team(
            name=form.name.data,
            description=form.description.data,
            cooperative_day_id=form.cooperative_day_id.data,
            leader_id=form.leader_id.data or None,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            status=form.status.data,
        )
        db.session.add(team)
        db.session.flush()
        log_action("create", "Team", team.id, f"Created team {team.name}")
        db.session.commit()
        flash(f"Team '{team.name}' created.", "success")
        return redirect(url_for("teams.team_detail", team_id=team.id))
    return render_template("teams/form.html", form=form, is_new=True)


@teams_bp.route("/<int:team_id>")
@login_required
def team_detail(team_id):
    team = Team.query.get_or_404(team_id)
    if not _is_team_viewer(team):
        abort(403)
    member_form = TeamMemberForm()
    documents = Document.query.filter_by(team_id=team.id).order_by(Document.created_at.desc()).all()

    use_windows = _uses_windows(team)
    current_section = None
    if use_windows:
        current_section = request.args.get("section")
        if current_section not in WINDOW_SECTIONS:
            current_section = WINDOW_SECTIONS[0]
        members = _section_query(team, current_section).order_by(TeamMember.id).all()
        members.sort(key=_window_sort_key)
    else:
        members = team.members.filter_by(parent_id=None).order_by(TeamMember.id).all()

    extra_field_names = []
    if use_windows:
        names = set()
        for m in members:
            names.update((m.extra_fields or {}).keys())
        extra_field_names = sorted(names)

    return render_template(
        "teams/detail.html",
        team=team,
        members=members,
        use_windows=use_windows,
        sections=WINDOW_SECTIONS,
        current_section=current_section,
        extra_field_names=extra_field_names,
        documents=documents,
        member_form=member_form,
        can_manage_members=_is_team_manager(team),
        can_edit_team=current_user.has_permission("manage_teams"),
    )


@teams_bp.route("/<int:team_id>/export.xlsx")
@login_required
def team_export_excel(team_id):
    team = Team.query.get_or_404(team_id)
    if not _is_team_viewer(team):
        abort(403)
    use_windows, section, members = _export_context(team)

    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = (section or "Members")[:31]

    header_fill = PatternFill("solid", fgColor="1F4E3D")
    header_font = Font(bold=True, color="FFFFFF")
    title_font = Font(bold=True, size=14)
    thin = Side(style="thin", color="B7B7B7")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left = Alignment(horizontal="left", vertical="center", wrap_text=True)

    extra_field_names = []
    if use_windows:
        names = set()
        for m in members:
            names.update((m.extra_fields or {}).keys())
        extra_field_names = sorted(names)

    title_text = f"{section} Team" if section else team.name
    base_cols = 6  # S/no, Leader, Window, District, Staff, Action
    n_cols = (base_cols + len(extra_field_names)) if use_windows else 3
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=n_cols)
    ws.cell(row=1, column=1, value=title_text).font = title_font
    ws.cell(row=1, column=1).alignment = center

    if use_windows:
        headers = ["S/no", "Leader", "Window", "District", "Staff", "Action"] + extra_field_names
    else:
        headers = ["#", "Name", "Added"]
    for col, h in enumerate(headers, start=1):
        c = ws.cell(row=3, column=col, value=h)
        c.font = header_font
        c.fill = header_fill
        c.border = border
        c.alignment = center

    row_ptr = 4
    if use_windows:
        staff_col = 5
        total_cols = base_cols + len(extra_field_names)
        merge_cols = [c for c in range(1, total_cols + 1) if c != staff_col]

        for idx, m in enumerate(members, start=1):
            staff = sorted(m.staff, key=lambda s: s.id)
            staff_names = [s.display_name for s in staff] or ["No staff yet"]
            span = len(staff_names)
            start_row, end_row = row_ptr, row_ptr + span - 1

            ws.cell(row=start_row, column=1, value=idx)
            ws.cell(row=start_row, column=2, value=m.display_name)
            ws.cell(row=start_row, column=3, value=m.window_label or "")
            ws.cell(row=start_row, column=4, value=m.district or "")
            ws.cell(row=start_row, column=6, value=m.action_note or "")
            for i, fname in enumerate(extra_field_names):
                ws.cell(row=start_row, column=7 + i, value=(m.extra_fields or {}).get(fname, ""))
            for i, name in enumerate(staff_names):
                ws.cell(row=row_ptr + i, column=staff_col, value=name)

            if span > 1:
                for col in merge_cols:
                    ws.merge_cells(start_row=start_row, end_row=end_row, start_column=col, end_column=col)

            for r in range(start_row, end_row + 1):
                for col in range(1, total_cols + 1):
                    cell = ws.cell(row=r, column=col)
                    cell.border = border
                    cell.alignment = left if col == staff_col else center
            row_ptr = end_row + 1

        widths = [6, 22, 14, 16, 26, 30] + [18] * len(extra_field_names)
    else:
        for idx, m in enumerate(members, start=1):
            ws.cell(row=row_ptr, column=1, value=idx)
            ws.cell(row=row_ptr, column=2, value=m.display_name)
            ws.cell(row=row_ptr, column=3, value=m.joined_at.strftime("%Y-%m-%d") if m.joined_at else "")
            for col in range(1, 4):
                cell = ws.cell(row=row_ptr, column=col)
                cell.border = border
                cell.alignment = center
            row_ptr += 1
        widths = [6, 30, 16]

    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = _safe_filename(team.name, section) + ".xlsx"
    return send_file(
        buf,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

@teams_bp.route("/<int:team_id>/import.xlsx", methods=["POST"])
@login_required
def team_import_excel(team_id):
    team = Team.query.get_or_404(team_id)
    if not _is_team_manager(team):
        abort(403)

    use_windows = _uses_windows(team)
    if not use_windows:
        abort(404)

    section = request.form.get("section") or request.args.get("section")
    if section not in WINDOW_SECTIONS:
        section = WINDOW_SECTIONS[0]

    file = request.files.get("excel_file")
    if not file or not file.filename:
        flash("Choose an Excel file to upload.", "danger")
        return _back(team.id, section)
    if not file.filename.lower().endswith(".xlsx"):
        flash("Please upload a .xlsx file.", "danger")
        return _back(team.id, section)

    from openpyxl import load_workbook
    try:
        wb = load_workbook(file, data_only=True)
        ws = wb.active
    except Exception:
        flash("Could not read that file. Make sure it's a valid .xlsx export.", "danger")
        return _back(team.id, section)

    # Map each column to a known field, or treat it as a new custom field.
    col_map = {}
    header_row = next(ws.iter_rows(min_row=3, max_row=3), [])
    for cell in header_row:
        text = str(cell.value).strip() if cell.value not in (None, "") else ""
        if not text:
            continue
        key = text.lower()
        if key in ("s/no", "#", "no"):
            col_map[cell.column] = "sno"
        elif key == "leader":
            col_map[cell.column] = "leader"
        elif key == "window":
            col_map[cell.column] = "window"
        elif key == "district":
            col_map[cell.column] = "district"
        elif key == "staff":
            col_map[cell.column] = "staff"
        elif key == "action":
            col_map[cell.column] = "action"
        else:
            col_map[cell.column] = ("extra", text)

    groups = []
    current = None
    for row in ws.iter_rows(min_row=4):
        row_leader = row_window = row_district = row_action = row_staff = None
        row_extra = {}
        for cell in row:
            kind = col_map.get(cell.column)
            if not kind:
                continue
            val = cell.value
            val = str(val).strip() if val not in (None, "") else ""
            if kind == "leader":
                row_leader = val
            elif kind == "window":
                row_window = val
            elif kind == "district":
                row_district = val
            elif kind == "staff":
                row_staff = val
            elif kind == "action":
                row_action = val
            elif isinstance(kind, tuple) and kind[0] == "extra":
                row_extra[kind[1]] = val

        if row_leader:
            current = {
                "leader": row_leader,
                "window": row_window or "",
                "district": row_district or "",
                "action": row_action or "",
                "extra": {k: v for k, v in row_extra.items() if v},
                "staff": [],
            }
            groups.append(current)

        if current is None:
            continue

        for k, v in row_extra.items():
            if v:
                current["extra"][k] = v

        if row_staff and row_staff.lower() != "no staff yet":
            current["staff"].append(row_staff)

    if not groups:
        flash("No rows found in that file.", "warning")
        return _back(team.id, section)

    existing = _section_query(team, section).all()
    for m in existing:
        db.session.delete(m)
    db.session.flush()

    for g in groups:
        leader = TeamMember(
            team_id=team.id,
            member_name=g["leader"].rstrip(","),
            window_label=g["window"] or None,
            district=g["district"] or None,
            action_note=g["action"] or None,
            section=section,
            extra_fields=g["extra"] or None,
        )
        db.session.add(leader)
        db.session.flush()
        for name in g["staff"]:
            db.session.add(TeamMember(team_id=team.id, member_name=name, parent_id=leader.id))

    log_action("update", "Team", team.id, f"Imported {section} roster from Excel ({len(groups)} leaders)")
    db.session.commit()
    flash(f"Imported {len(groups)} leader(s) into {section}.", "success")
    return _back(team.id, section)


@teams_bp.route("/<int:team_id>/export.pdf")
@login_required
def team_export_pdf(team_id):
    team = Team.query.get_or_404(team_id)
    if not _is_team_viewer(team):
        abort(403)
    use_windows, section, members = _export_context(team)

    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

    styles = getSampleStyleSheet()
    cell_style = styles["BodyText"]
    cell_style.fontSize = 9
    cell_style.leading = 11

    extra_field_names = []
    if use_windows:
        names = set()
        for m in members:
            names.update((m.extra_fields or {}).keys())
        extra_field_names = sorted(names)

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.2 * cm, bottomMargin=1.2 * cm,
    )
    title_text = f"{section} Team" if section else team.name
    story = [Paragraph(f"<b>{title_text}</b>", styles["Title"]), Spacer(1, 10)]

    spans = []
    if use_windows:
        data = [["#", "Leader", "Window", "District", "Staff", "Action"] + extra_field_names]
        row_ptr = 1
        for idx, m in enumerate(members, start=1):
            staff = sorted(m.staff, key=lambda s: s.id)
            staff_names = [s.display_name for s in staff] or ["No staff yet"]
            span = len(staff_names)
            start_row, end_row = row_ptr, row_ptr + span - 1
            for i, name in enumerate(staff_names):
                row = [
                    str(idx) if i == 0 else "",
                    Paragraph(m.display_name, cell_style) if i == 0 else "",
                    (m.window_label or "") if i == 0 else "",
                    (m.district or "") if i == 0 else "",
                    Paragraph(name, cell_style),
                    Paragraph(m.action_note or "", cell_style) if i == 0 else "",
                ]
                for fname in extra_field_names:
                    row.append(Paragraph((m.extra_fields or {}).get(fname, ""), cell_style) if i == 0 else "")
                data.append(row)
            if span > 1:
                for col in [0, 1, 2, 3, 5] + list(range(6, 6 + len(extra_field_names))):
                    spans.append(("SPAN", (col, start_row), (col, end_row)))
            row_ptr = end_row + 1
        col_widths = [1.3 * cm, 3.5 * cm, 2.3 * cm, 2.3 * cm, 5 * cm, 6 * cm] + [3.5 * cm] * len(extra_field_names)
    else:
        data = [["#", "Name", "Added"]]
        for idx, m in enumerate(members, start=1):
            data.append([str(idx), Paragraph(m.display_name, cell_style),
                         m.joined_at.strftime("%Y-%m-%d") if m.joined_at else ""])
        col_widths = [1.5 * cm, 10 * cm, 4 * cm]

    if len(data) == 1:
        data.append(["No records." if use_windows else "No members."] + [""] * (len(data[0]) - 1))

    table = Table(data, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E3D")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B7B7B7")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
    ] + spans
    table.setStyle(TableStyle(style_cmds))
    story.append(table)
    doc.build(story)
    buf.seek(0)
    filename = _safe_filename(team.name, section) + ".pdf"
    return send_file(buf, as_attachment=True, download_name=filename, mimetype="application/pdf")


@teams_bp.route("/<int:team_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("manage_teams")
def team_edit(team_id):
    team = Team.query.get_or_404(team_id)
    form = TeamForm(obj=team)
    _populate_choices(form)
    if request.method == "GET":
        form.leader_id.data = team.leader_id or 0

    if form.validate_on_submit():
        team.name = form.name.data
        team.description = form.description.data
        team.cooperative_day_id = form.cooperative_day_id.data
        team.leader_id = form.leader_id.data or None
        team.start_date = form.start_date.data
        team.end_date = form.end_date.data
        team.status = form.status.data
        log_action("update", "Team", team.id, f"Updated team {team.name}")
        db.session.commit()
        flash(f"Team '{team.name}' updated.", "success")
        return redirect(url_for("teams.team_detail", team_id=team.id))
    return render_template("teams/form.html", form=form, is_new=False, team=team)


@teams_bp.route("/<int:team_id>/members/add", methods=["POST"])
@login_required
def team_member_add(team_id):
    team = Team.query.get_or_404(team_id)
    if not _is_team_manager(team):
        abort(403)
    use_windows = _uses_windows(team)
    section = request.form.get("section")
    if not use_windows or section not in WINDOW_SECTIONS:
        section = None
    form = TeamMemberForm()
    if form.validate_on_submit():
        pool = _section_query(team, section) if section else team.members
        existing = {(m.member_name or "").strip().lower() for m in pool}
        added = 0
        for line in form.names.data.splitlines():
            name = line.strip()
            if not name or name.lower() in existing:
                continue
            db.session.add(TeamMember(
                team_id=team.id, member_name=name[:150],
                role_in_team="Member", section=section,
            ))
            existing.add(name.lower())
            added += 1
        log_action("create", "TeamMember", team.id, f"Added {added} member(s) to team {team.name}")
        db.session.commit()
        flash(f"{added} member(s) added to the team.", "success")
    else:
        flash("Please write at least one name.", "danger")
    return _back(team.id, section)


@teams_bp.route("/<int:team_id>/members/<int:member_id>/remove", methods=["POST"])
@login_required
def team_member_remove(team_id, member_id):
    team = Team.query.get_or_404(team_id)
    if not _is_team_manager(team):
        abort(403)
    member = TeamMember.query.filter_by(id=member_id, team_id=team_id).first_or_404()
    root = member.leader or member
    section = root.section if _uses_windows(team) else None
    log_action("delete", "TeamMember", member.id, f"Removed member {member.display_name} from team {team_id}")
    db.session.delete(member)
    db.session.commit()
    flash("Member removed from team.", "info")
    return _back(team_id, section)


@teams_bp.route("/<int:team_id>/members/<int:member_id>/window", methods=["POST"])
@login_required
def team_member_window(team_id, member_id):
    team = Team.query.get_or_404(team_id)
    if not _is_team_manager(team):
        abort(403)
    member = TeamMember.query.filter_by(id=member_id, team_id=team_id).first_or_404()
    form = WindowForm()
    if form.validate_on_submit():
        member.window_label = (form.window_label.data or "").strip() or None
        log_action("update", "TeamMember", member.id, f"Set window for {member.display_name}")
        db.session.commit()
        if request.headers.get("X-Requested-With") == "fetch":
            return "", 204
        flash("Window saved.", "success")
    return _back(team_id, member.section)

@teams_bp.route("/<int:team_id>/members/<int:member_id>/field", methods=["POST"])
@login_required
def team_member_field(team_id, member_id):
    team = Team.query.get_or_404(team_id)
    if not _is_team_manager(team):
        abort(403)
    member = TeamMember.query.filter_by(id=member_id, team_id=team_id).first_or_404()
    field_name = (request.form.get("field_name") or "").strip()
    field_value = (request.form.get("field_value") or "").strip()
    if field_name:
        data = dict(member.extra_fields or {})
        if field_value:
            data[field_name] = field_value
        else:
            data.pop(field_name, None)
        member.extra_fields = data
        log_action("update", "TeamMember", member.id, f"Set field '{field_name}' for {member.display_name}")
        db.session.commit()
        flash(f"'{field_name}' saved.", "success")
    return _back(team_id, member.section)


@teams_bp.route("/<int:team_id>/members/<int:member_id>/district", methods=["POST"])
@login_required
def team_member_district(team_id, member_id):
    team = Team.query.get_or_404(team_id)
    if not _is_team_manager(team):
        abort(403)
    member = TeamMember.query.filter_by(id=member_id, team_id=team_id).first_or_404()
    form = DistrictForm()
    if form.validate_on_submit():
        member.district = (form.district.data or "").strip() or None
        log_action("update", "TeamMember", member.id, f"Set district for {member.display_name}")
        db.session.commit()
        if request.headers.get("X-Requested-With") == "fetch":
            return "", 204
        flash("District saved.", "success")
    return _back(team_id, member.section)


@teams_bp.route("/<int:team_id>/members/<int:member_id>/action", methods=["POST"])
@login_required
def team_member_action(team_id, member_id):
    team = Team.query.get_or_404(team_id)
    if not _is_team_manager(team):
        abort(403)
    member = TeamMember.query.filter_by(id=member_id, team_id=team_id).first_or_404()
    form = ActionForm()
    if form.validate_on_submit():
        member.action_note = (form.action_note.data or "").strip() or None
        log_action("update", "TeamMember", member.id, f"Set today's action for {member.display_name}")
        db.session.commit()
        flash("Action saved.", "success")
    return _back(team_id, member.section)


@teams_bp.route("/<int:team_id>/members/<int:member_id>/staff/add", methods=["POST"])
@login_required
def team_staff_add(team_id, member_id):
    team = Team.query.get_or_404(team_id)
    if not _is_team_manager(team):
        abort(403)
    leader = TeamMember.query.filter_by(id=member_id, team_id=team_id, parent_id=None).first_or_404()
    form = TeamMemberForm()
    if form.validate_on_submit():
        existing = {(m.member_name or "").strip().lower() for m in team.members}
        added = 0
        for line in form.names.data.splitlines():
            name = line.strip()
            if not name or name.lower() in existing:
                continue
            db.session.add(TeamMember(
                team_id=team.id, parent_id=leader.id,
                member_name=name[:150], role_in_team="Staff",
            ))
            existing.add(name.lower())
            added += 1
        log_action("create", "TeamMember", leader.id, f"Added {added} staff under {leader.display_name}")
        db.session.commit()
        flash(f"{added} staff added under {leader.display_name}.", "success")
    else:
        flash("Please write at least one name.", "danger")
    return _back(team_id, leader.section)

@teams_bp.route("/<int:team_id>/members/<int:staff_id>/staff/move", methods=["POST"])
@login_required
def team_staff_move(team_id, staff_id):
    """Drag-and-drop: reassign a staff member from one window leader to another."""
    team = Team.query.get_or_404(team_id)
    if not _is_team_manager(team):
        abort(403)
    staff = TeamMember.query.filter_by(id=staff_id, team_id=team_id).first_or_404()
    if staff.parent_id is None:
        return {"ok": False, "error": "Not a staff member."}, 400
    new_leader_id = request.form.get("new_leader_id", type=int)
    new_leader = TeamMember.query.filter_by(id=new_leader_id, team_id=team_id, parent_id=None).first_or_404()
    if new_leader.section != staff.leader.section:
        return {"ok": False, "error": "Leaders are in different sections."}, 400
    old_leader_name = staff.leader.display_name if staff.leader else "?"
    staff.parent_id = new_leader.id
    log_action(
        "update", "TeamMember", staff.id,
        f"Moved staff {staff.display_name} from {old_leader_name} to {new_leader.display_name}",
    )
    db.session.commit()
    return {"ok": True}


def _populate_choices(form):
    form.cooperative_day_id.choices = [
        (e.id, e.name) for e in CooperativeDay.query.order_by(CooperativeDay.year.desc())
    ]
    form.leader_id.choices = [(0, "— None —")] + [
        (u.id, u.full_name) for u in User.query.filter_by(status="Active").order_by(User.full_name)
    ]