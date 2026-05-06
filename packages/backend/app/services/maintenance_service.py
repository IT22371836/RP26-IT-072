from datetime import datetime

from app.repositories.maintenance_repository import MaintenanceRepository
from app.core.database import get_database
from app.schemas.maintenance import (
    CustomerDashboard,
    ProviderDashboard,
    MaintenanceRequestOut,
    DashboardStats,
)


class MaintenanceService:
    @staticmethod
    async def get_customer_dashboard(customer_id: str, limit: int = 20) -> CustomerDashboard:
        db = get_database()
        repo = MaintenanceRepository(db)
        requests = await repo.find_by_customer(customer_id, limit=limit)
        stats_raw = await repo.count_by_status("customer_id", customer_id)

        stats = DashboardStats(
            open=stats_raw.get("open", 0),
            assigned=stats_raw.get("assigned", 0),
            in_progress=stats_raw.get("in_progress", 0),
            completed=stats_raw.get("completed", 0),
            cancelled=stats_raw.get("cancelled", 0),
        )

        recent = [
            MaintenanceRequestOut(
                id=str(r.get("_id")),
                customer_id=r.get("customer_id"),
                provider_id=r.get("provider_id"),
                asset_type=r.get("asset_type"),
                description=r.get("description"),
                status=r.get("status", "open"),
                priority=r.get("priority", "normal"),
                eta=r.get("eta"),
                created_at=r.get("created_at", datetime.utcnow()),
                updated_at=r.get("updated_at"),
            )
            for r in requests
        ]

        return CustomerDashboard(stats=stats, recent_requests=recent)

    @staticmethod
    async def get_provider_dashboard(provider_id: str, limit: int = 20) -> ProviderDashboard:
        db = get_database()
        repo = MaintenanceRepository(db)
        jobs = await repo.find_by_provider(provider_id, limit=limit)
        stats_raw = await repo.count_by_status("provider_id", provider_id)

        stats = DashboardStats(
            open=stats_raw.get("open", 0),
            assigned=stats_raw.get("assigned", 0),
            in_progress=stats_raw.get("in_progress", 0),
            completed=stats_raw.get("completed", 0),
            cancelled=stats_raw.get("cancelled", 0),
        )

        recent = [
            MaintenanceRequestOut(
                id=str(r.get("_id")),
                customer_id=r.get("customer_id"),
                provider_id=r.get("provider_id"),
                asset_type=r.get("asset_type"),
                description=r.get("description"),
                status=r.get("status", "open"),
                priority=r.get("priority", "normal"),
                eta=r.get("eta"),
                created_at=r.get("created_at", datetime.utcnow()),
                updated_at=r.get("updated_at"),
            )
            for r in jobs
        ]

        return ProviderDashboard(stats=stats, recent_jobs=recent)
