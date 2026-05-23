import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float, Index
from sqlalchemy.orm import relationship

from app.core.database import Base


def _utcnow():
    """Return timezone-aware UTC datetime (avoids deprecated datetime.utcnow)."""
    return datetime.datetime.now(datetime.timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    git_url = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    scans = relationship("Scan", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name={self.name!r})>"


class Scan(Base):
    __tablename__ = "scans"

    id = Column(String, primary_key=True, index=True)  # UUID string
    project_id = Column(Integer, ForeignKey("projects.id"), index=True)
    status = Column(String, default="pending")  # pending, running, completed, failed
    target_type = Column(String)  # code, website, api, cloud
    target_value = Column(String)  # git url, local file path, api url
    
    # Progress telemetry
    progress = Column(Integer, default=0)
    current_phase = Column(String, default="idle")
    
    # Overall scoring computed by ML Agent
    risk_score = Column(Float, default=0.0)
    critical_count = Column(Integer, default=0)
    high_count = Column(Integer, default=0)
    medium_count = Column(Integer, default=0)
    low_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=_utcnow)
    completed_at = Column(DateTime, nullable=True)

    project = relationship("Project", back_populates="scans")
    findings = relationship("Finding", back_populates="scan", cascade="all, delete-orphan")
    activities = relationship("AgentActivity", back_populates="scan", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_scans_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Scan(id={self.id!r}, status={self.status!r}, risk_score={self.risk_score})>"


class Finding(Base):
    __tablename__ = "findings"

    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(String, ForeignKey("scans.id"), index=True)
    
    title = Column(String, index=True)
    description = Column(Text)
    severity = Column(String)  # Critical, High, Medium, Low
    file_path = Column(String, nullable=True)
    line_number = Column(Integer, nullable=True)
    code_snippet = Column(Text, nullable=True)
    
    # Security categorization
    cwe = Column(String, nullable=True)
    cve = Column(String, nullable=True)
    mitre_attack = Column(String, nullable=True)
    owasp_category = Column(String, nullable=True)
    confidence = Column(String, nullable=True)

    # Dependency advisory metadata when the finding comes from a manifest scan.
    package = Column(String, nullable=True)
    current_version = Column(String, nullable=True)
    fixed_version = Column(String, nullable=True)
    
    # Remediation
    remediation_explanation = Column(Text, nullable=True)
    remediation_code = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=_utcnow)

    scan = relationship("Scan", back_populates="findings")

    __table_args__ = (
        Index("ix_findings_severity", "severity"),
    )

    def __repr__(self) -> str:
        return f"<Finding(id={self.id}, title={self.title!r}, severity={self.severity!r})>"


class AgentActivity(Base):
    __tablename__ = "agent_activities"

    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(String, ForeignKey("scans.id"), index=True)
    
    agent_name = Column(String)  # Orchestrator, CodeAnalyzer, SecurityReviewer, ThreatIntel, MLAgent, ReportAgent
    message = Column(Text)
    type = Column(String, default="info")  # info, warning, success, error
    timestamp = Column(DateTime, default=_utcnow)

    scan = relationship("Scan", back_populates="activities")

    def __repr__(self) -> str:
        return f"<AgentActivity(id={self.id}, agent={self.agent_name!r}, type={self.type!r})>"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String)
    user = Column(String, default="admin")
    details = Column(Text)
    timestamp = Column(DateTime, default=_utcnow)

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action={self.action!r})>"
