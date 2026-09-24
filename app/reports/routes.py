from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file
from flask_login import login_required, current_user

from app.extensions import db
from app.models.event import CooperativeDay
from app.models.report import AnnualReport
from app.models.document import Document
from app.reports.forms import AnnualReportForm
from app.reports.services import build_report_context, build_comparison, COMPARISON_METRICS
from app.reports.exporters import build_pdf, build_excel, build_comparison_excel
from app.utils.decorators import permission_required
from app.utils.audit import log_action

reports_bp = Blueprint("reports", __name__)


def _get_or_create_report(event):
    report = AnnualReport.query.filter_by(cooperative_day_id=event.id).first()
    if not report:
        report = AnnualReport(cooperative_day_id=event.id, status="Draft")
        db.session.add(report)
        db.session.commit()
    return report


@reports_bp.route("/")
@login_required
@permission_required("view_reports")
def reports_list():
    events = CooperativeDay.query.order_by(CooperativeDay.year.desc()).all()
    reports_by_event = {r.cooperative_day_id: r for r in AnnualReport.query.all()}
    return render_template("reports/list.html", events=events, reports_by_event=reports_by_event)


@reports_bp.route("/<int:event_id>")
@login_required
@permission_required("view_reports")
def report_detail(event_id):
    event = CooperativeDay.query.get_or_404(event_id)
    report = _get_or_create_report(event)
    ctx = build_report_context(event)
    photos_docs = Document.query.filter(
        Document.cooperative_day_id == event.id, Document.document_type.in_(["Photo", "Video"])
    ).order_by(Document.created_at.desc()).limit(24).all()
    return render_template("reports/detail.html", ctx=ctx, report=report, photos_docs=photos_docs)


@reports_bp.route("/<int:event_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("generate_reports")
def report_edit(event_id):
    event = CooperativeDay.query.get_or_404(event_id)
    report = _get_or_create_report(event)
    form = AnnualReportForm(obj=report)
    if form.validate_on_submit():
        was_published = report.status == "Published"
        report.executive_summary = form.executive_summary.data
        report.key_achievements = form.key_achievements.data
        report.challenges = form.challenges.data
        report.lessons_learned = form.lessons_learned.data
        report.recommendations = form.recommendations.data
        report.status = form.status.data
        report.prepared_by_id = current_user.id
        if report.status == "Published" and not was_published:
            report.published_at = datetime.utcnow()
        log_action("update", "AnnualReport", report.id, f"Updated Annual Report for {event.name}")
        db.session.commit()
        flash("Annual report saved.", "success")
        return redirect(url_for("reports.report_detail", event_id=event.id))
    return render_template("reports/form.html", form=form, event=event)


@reports_bp.route("/<int:event_id>/pdf")
@login_required
@permission_required("generate_reports")
def report_pdf(event_id):
    event = CooperativeDay.query.get_or_404(event_id)
    report = _get_or_create_report(event)
    ctx = build_report_context(event)
    buf = build_pdf(ctx, report)
    log_action("download", "AnnualReport", report.id, f"Downloaded PDF for {event.name}")
    db.session.commit()
    filename = f"CoopBank_Cooperative_Day_{event.year}_Annual_Report.pdf"
    return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name=filename)


@reports_bp.route("/<int:event_id>/excel")
@login_required
@permission_required("generate_reports")
def report_excel(event_id):
    event = CooperativeDay.query.get_or_404(event_id)
    report = _get_or_create_report(event)
    ctx = build_report_context(event)
    buf = build_excel(ctx, report)
    log_action("download", "AnnualReport", report.id, f"Downloaded Excel export for {event.name}")
    db.session.commit()
    filename = f"CoopBank_Cooperative_Day_{event.year}_Annual_Report.xlsx"
    return send_file(
        buf, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True, download_name=filename,
    )


@reports_bp.route("/compare")
@login_required
@permission_required("view_reports")
def compare():
    all_events = CooperativeDay.query.order_by(CooperativeDay.year.desc()).all()

    years_param = request.args.get("years", "")
    selected_ids = [int(v) for v in years_param.split(",") if v.strip().isdigit()]
    if not selected_ids:
        # default: compare every year on record (up to a sane display limit)
        selected_ids = [e.id for e in sorted(all_events, key=lambda e: e.year)][-6:]

    selected_events = [e for e in all_events if e.id in selected_ids]
    selected_events.sort(key=lambda e: e.year)

    contexts = build_comparison(selected_events) if selected_events else []

    chart_data = {
        "labels": [str(c["event"].year) for c in contexts],
        "series": [
            {"label": label, "data": [c[key] for c in contexts]}
            for key, label in COMPARISON_METRICS
        ],
    }

    return render_template(
        "reports/compare.html", all_events=all_events, selected_ids=selected_ids,
        contexts=contexts, metrics=COMPARISON_METRICS, chart_data=chart_data,
    )


@reports_bp.route("/compare/excel")
@login_required
@permission_required("generate_reports")
def compare_excel():
    years_param = request.args.get("years", "")
    selected_ids = [int(v) for v in years_param.split(",") if v.strip().isdigit()]
    events = CooperativeDay.query.filter(CooperativeDay.id.in_(selected_ids)).order_by(CooperativeDay.year).all()
    if not events:
        flash("Select at least one Cooperative Day year to compare.", "warning")
        return redirect(url_for("reports.compare"))
    contexts = build_comparison(events)
    buf = build_comparison_excel(contexts)
    log_action("download", "AnnualReport", None, "Downloaded year-comparison Excel export")
    db.session.commit()
    years_label = "-".join(str(e.year) for e in events)
    return send_file(
        buf, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True, download_name=f"CoopBank_Cooperative_Day_Comparison_{years_label}.xlsx",
    )
