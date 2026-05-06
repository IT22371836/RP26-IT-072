from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

Status = Literal["open", "assigned", "in_progress", "completed", "cancelled"]
Priority = Literal["low", "normal", "high"]


class MaintenanceRequestOut(BaseModel):
    id: str
    customer_id: str
    provider_id: Optional[str]
    asset_type: Optional[str]
    description: Optional[str]
    status: Status
    priority: Priority
    eta: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]


class DashboardStats(BaseModel):
    open: int = 0
    assigned: int = 0
    in_progress: int = 0
    completed: int = 0
    cancelled: int = 0


class CustomerDashboard(BaseModel):
    stats: DashboardStats
    recent_requests: list[MaintenanceRequestOut]


class ProviderDashboard(BaseModel):
    stats: DashboardStats
    recent_jobs: list[MaintenanceRequestOut]
