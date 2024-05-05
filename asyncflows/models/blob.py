from typing import Optional

from pydantic import BaseModel


BlobId = str


class Blob(BaseModel):
    id: BlobId
    file_extension: Optional[str] = None
    # ttl: timedelta
    # created_at: datetime
