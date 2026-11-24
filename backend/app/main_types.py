from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


class QuestionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    role: str = Field(default="Software Engineer", min_length=2, max_length=100)
    topic: str = Field(default="Data Structures", min_length=2, max_length=100)
    difficulty: Literal["Beginner", "Intermediate", "Advanced"] = "Beginner"


class QuestionResponse(BaseModel):
    question: str
    model: str
