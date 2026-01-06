import uuid
from app.core.database import SessionLocal, Base, engine
from app.models.tenant import Tenant, PlanTier
from app.models.project import Project
from app.models.scan import ScanJob, ScanLevel, ScanStatus
from app.models.finding import Finding, Severity
from app.services.pdf_reports import _compute_findings_metrics


def test_report_totals_match_findings():
    # fresh db
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        tenant = Tenant(id=str(uuid.uuid4()), name="tenant", plan=PlanTier.PRO)
        owner_id = str(uuid.uuid4())
        from app.models.user import User
        user = User(
            id=owner_id,
            email="owner@example.com",
            username="owner",
            hashed_password="",
            tenant_id=tenant.id,
        )
        project = Project(
            id=str(uuid.uuid4()),
            name="proj",
            target_url="http://example.com",
            root_domain="example.com",
            owner_id=owner_id,
            tenant_id=tenant.id,
        )
        scan = ScanJob(
            id=str(uuid.uuid4()),
            project_id=project.id,
            scan_level=ScanLevel.PRO,
            status=ScanStatus.COMPLETED,
        )
        db.add_all([tenant, user, project, scan])
        db.commit()

        findings = [
            Finding(
                id=str(uuid.uuid4()),
                scan_job_id=scan.id,
                project_id=project.id,
                title="crit",
                severity=Severity.CRITICAL,
                description="",
            ),
            Finding(
                id=str(uuid.uuid4()),
                scan_job_id=scan.id,
                project_id=project.id,
                title="high",
                severity=Severity.HIGH,
                description="",
            ),
            Finding(
                id=str(uuid.uuid4()),
                scan_job_id=scan.id,
                project_id=project.id,
                title="low",
                severity=Severity.LOW,
                description="",
            ),
        ]
        db.add_all(findings)
        db.commit()

        count, breakdown = _compute_findings_metrics(findings)
        assert count == 3
        assert breakdown == {"critical": 1, "high": 1, "medium": 0, "low": 1, "info": 0}
    finally:
        db.close()

