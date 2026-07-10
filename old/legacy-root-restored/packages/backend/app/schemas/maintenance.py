from pydantic import BaseModel


class MaintenanceSummary(BaseModel):
    total: int
