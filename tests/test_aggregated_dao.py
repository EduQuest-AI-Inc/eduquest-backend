import os
import sys
from typing import List

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data_access.aggregated_dao import AggregatedMetricsDAO
from models.aggregated_metrics import AggregatedMetrics, SkillMetric, WeekMetrics


class FakeTable:
    def __init__(self):
        self.items = {}

    def put_item(self, Item):
        self.items[Item["course-week"]] = dict(Item)

    def get_item(self, Key):
        item = self.items.get(Key["course-week"])
        return {"Item": dict(item)} if item else {}

    def update_item(self, Key, UpdateExpression, ExpressionAttributeNames, ExpressionAttributeValues):
        item = self.items.setdefault(Key["course-week"], {"course-week": Key["course-week"]})
        for placeholder, attr_name in ExpressionAttributeNames.items():
            value_key = placeholder.replace("#", ":")
            if value_key in ExpressionAttributeValues:
                item[attr_name] = ExpressionAttributeValues[value_key]

    def delete_item(self, Key):
        self.items.pop(Key["course-week"], None)


def test_get_aggregated_metrics_by_course_week(monkeypatch):
    fake_table = FakeTable()

    metrics = AggregatedMetrics(
        course_week="pre_calc_1",
        weeks=[
            WeekMetrics(
                skills=[
                    SkillMetric(percentage=80, skill_name="skill1"),
                    SkillMetric(percentage=75, skill_name="skill2"),
                ]
            )
        ],
    )

    fake_table.put_item(Item=metrics.to_dynamo_item())

    monkeypatch.setattr(
        "data_access.aggregated_dao.DynamoDBConfig.get_table",
        lambda self, table_name: fake_table,
    )

    dao = AggregatedMetricsDAO()

    loaded = dao.get_aggregated_metrics_by_course_week("pre_calc_1")
    assert isinstance(loaded, AggregatedMetrics)
    assert loaded.course_week == "pre_calc_1"
    assert len(loaded.weeks) == 1
    assert [s.skill_name for s in loaded.weeks[0].skills] == ["skill1", "skill2"]

    weeks: List[WeekMetrics] = dao.get_skills_by_course_week("pre_calc_1")
    assert len(weeks) == 1
    assert [s.skill_name for s in weeks[0].skills] == ["skill1", "skill2"]

    assert dao.get_aggregated_metrics_by_course_week("missing") is None
    assert dao.get_skills_by_course_week("missing") == []


def test_update_and_delete_aggregated_metrics(monkeypatch):
    fake_table = FakeTable()

    initial_metrics = AggregatedMetrics(
        course_week="pre_calc_1",
        weeks=[
            WeekMetrics(
                skills=[
                    SkillMetric(percentage=80, skill_name="skill1"),
                ]
            )
        ],
    )

    fake_table.put_item(Item=initial_metrics.to_dynamo_item())

    monkeypatch.setattr(
        "data_access.aggregated_dao.DynamoDBConfig.get_table",
        lambda self, table_name: fake_table,
    )

    dao = AggregatedMetricsDAO()

    updated_weeks = [
        WeekMetrics(
            skills=[
                SkillMetric(percentage=90, skill_name="skill1"),
                SkillMetric(percentage=60, skill_name="skill3"),
            ]
        )
    ]

    # Update the stored Weeks attribute using the raw DynamoDB field name.
    dao.update_aggregated_metrics(
        "pre_calc_1",
        {"Weeks": AggregatedMetrics(course_week="pre_calc_1", weeks=updated_weeks).to_dynamo_item()["Weeks"]},
    )

    updated_metrics = dao.get_aggregated_metrics_by_course_week("pre_calc_1")
    assert isinstance(updated_metrics, AggregatedMetrics)
    assert [s.skill_name for s in updated_metrics.weeks[0].skills] == ["skill1", "skill3"]

    # The raw item in the fake table should have a last_updated_at field.
    raw_item = fake_table.get_item({"course-week": "pre_calc_1"})["Item"]
    assert "last_updated_at" in raw_item

    dao.delete_aggregated_metrics("pre_calc_1")
    assert dao.get_aggregated_metrics_by_course_week("pre_calc_1") is None
