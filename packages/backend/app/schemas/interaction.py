from datetime import datetime

from pydantic import BaseModel, Field


class InteractionDatasetRecord(BaseModel):
    """Exact contract of the Component 1 interaction research dataset."""

    interaction_id: str
    user_id: str
    provider_id: str
    category: str
    interaction_type: str
    rating: int = Field(ge=1, le=5)
    booking_status: str
    timestamp: datetime
