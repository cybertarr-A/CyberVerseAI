"""Initial schema — projects, scans, findings, agent_activities, audit_logs

Revision ID: 001
Revises:
Create Date: 2026-05-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("git_url", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_projects_id", "projects", ["id"])
    op.create_index("ix_projects_name", "projects", ["name"], unique=True)

    op.create_table(
        "scans",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("target_type", sa.String(), nullable=True),
        sa.Column("target_value", sa.String(), nullable=True),
        sa.Column("progress", sa.Integer(), nullable=True),
        sa.Column("current_phase", sa.String(), nullable=True),
        sa.Column("risk_score", sa.Float(), nullable=True),
        sa.Column("critical_count", sa.Integer(), nullable=True),
        sa.Column("high_count", sa.Integer(), nullable=True),
        sa.Column("medium_count", sa.Integer(), nullable=True),
        sa.Column("low_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_scans_id", "scans", ["id"])
    op.create_index("ix_scans_project_id", "scans", ["project_id"])
    op.create_index("ix_scans_status", "scans", ["status"])

    op.create_table(
        "findings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scan_id", sa.String(), sa.ForeignKey("scans.id"), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(), nullable=True),
        sa.Column("file_path", sa.String(), nullable=True),
        sa.Column("line_number", sa.Integer(), nullable=True),
        sa.Column("code_snippet", sa.Text(), nullable=True),
        sa.Column("cwe", sa.String(), nullable=True),
        sa.Column("cve", sa.String(), nullable=True),
        sa.Column("mitre_attack", sa.String(), nullable=True),
        sa.Column("owasp_category", sa.String(), nullable=True),
        sa.Column("remediation_explanation", sa.Text(), nullable=True),
        sa.Column("remediation_code", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_findings_id", "findings", ["id"])
    op.create_index("ix_findings_scan_id", "findings", ["scan_id"])
    op.create_index("ix_findings_severity", "findings", ["severity"])
    op.create_index("ix_findings_title", "findings", ["title"])

    op.create_table(
        "agent_activities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scan_id", sa.String(), sa.ForeignKey("scans.id"), nullable=True),
        sa.Column("agent_name", sa.String(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("type", sa.String(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_agent_activities_id", "agent_activities", ["id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("action", sa.String(), nullable=True),
        sa.Column("user", sa.String(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_audit_logs_id", "audit_logs", ["id"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("agent_activities")
    op.drop_table("findings")
    op.drop_table("scans")
    op.drop_table("projects")
