from pydantic import BaseModel


class ConceptSkill(BaseModel):
    period_id: str
    concept_name: str
    skill_name: str

    def to_item(self):
        return self.model_dump()
