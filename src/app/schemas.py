from pydantic import BaseModel
from typing import List, Optional

class ScoreRequest(BaseModel):
    text: str

class ScoreResponse(BaseModel):
    label: str
    prob: float

class ReportResponse(BaseModel):
    html: str
