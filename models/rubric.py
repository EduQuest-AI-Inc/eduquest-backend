from pydantic import BaseModel, Field

class Scale(BaseModel):
    Score_0: str = Field(description="The criteria for getting a score of 0")
    Score_1: str = Field(description="The criteria for getting a score of 1")
    Score_2: str = Field(description="The criteria for getting a score of 2")
    Score_3: str = Field(description="The criteria for getting a score of 3")
    Score_4: str = Field(description="The criteria for getting a score of 4")
    Score_5: str = Field(description="The criteria for getting a score of 5")

class Rubric(BaseModel):
    Grade_Scale: Scale = Field(description="The scale for the rubric")
    Criteria: str = Field(description="The criteria for the rubric")