from pydantic import BaseModel, Field
from typing import List, Dict, Any

class CriteriaScale(BaseModel):
    Score_0: str = Field(description="Description for getting a score of 0 for this criteria")
    Score_1: str = Field(description="Description for getting a score of 1 for this criteria")
    Score_2: str = Field(description="Description for getting a score of 2 for this criteria")
    Score_3: str = Field(description="Description for getting a score of 3 for this criteria")
    Score_4: str = Field(description="Description for getting a score of 4 for this criteria")
    Score_5: str = Field(description="Description for getting a score of 5 for this criteria")

class CriterionWithScale(BaseModel):
    name: str = Field(description="The name of the criterion")
    scale: CriteriaScale = Field(description="The scoring scale for this criterion")

# Legacy Scale class for backward compatibility
class Scale(BaseModel):
    Score_0: str = Field(description="The criteria for getting a score of 0")
    Score_1: str = Field(description="The criteria for getting a score of 1")
    Score_2: str = Field(description="The criteria for getting a score of 2")
    Score_3: str = Field(description="The criteria for getting a score of 3")
    Score_4: str = Field(description="The criteria for getting a score of 4")
    Score_5: str = Field(description="The criteria for getting a score of 5")

class Rubric(BaseModel):
    criteria_list: List[CriterionWithScale] = Field(description="List of criteria with their scoring scales")
    
    def to_dict_format(self) -> Dict[str, Any]:
        """Convert to the expected dictionary format for compatibility"""
        return {
            "Criteria": {
                criterion.name: {
                    "Score_0": criterion.scale.Score_0,
                    "Score_1": criterion.scale.Score_1,
                    "Score_2": criterion.scale.Score_2,
                    "Score_3": criterion.scale.Score_3,
                    "Score_4": criterion.scale.Score_4,
                    "Score_5": criterion.scale.Score_5
                }
                for criterion in self.criteria_list
            }
        }