from pydantic import BaseModel, ConfigDict, Field, StrictInt, computed_field
from typing import Annotated

Score = Annotated[StrictInt, Field(ge=0, le=10)]
Note = Annotated[str, Field(min_length=1, max_length=600)]


class Feedback(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)
    technical_accuracy: Score
    completeness: Score
    clarity: Score
    reasoning: Score
    strengths: list[Note] = Field(max_length=3)
    missing_concepts: list[Note] = Field(max_length=3)
    suggestions: list[Note] = Field(min_length=1, max_length=3)

    @computed_field
    @property
    def score(self) -> float:
        return round((self.technical_accuracy + self.completeness + self.clarity + self.reasoning) / 4, 1)
