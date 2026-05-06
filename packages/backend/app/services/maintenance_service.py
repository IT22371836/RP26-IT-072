from app.repositories.maintenance_repository import MaintenanceRepository


class MaintenanceService:
    def __init__(self, repository: MaintenanceRepository):
        self.repository = repository

    async def get_summary(self) -> dict[str, int]:
        total = await self.repository.count()
        return {"total": total}
