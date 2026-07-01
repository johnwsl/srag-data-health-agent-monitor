from pydantic import BaseModel, Field


class EtlResponse(BaseModel):
    message: str
    files_merged: list[str] = Field(default_factory=list)
    rows_before_filter: int
    rows_after_filter: int
    rows_saved: int
    table_name: str
    database_path: str
