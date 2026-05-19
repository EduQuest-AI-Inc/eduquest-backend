"""
Meta-test: assert that response model field types match the domain model types.

When a field exists in both a domain model (models/) and a response model (responses/),
the Python type must be compatible — mismatches cause FastAPI ResponseValidationError
(500) at runtime. This test catches them in CI without requiring hardcoded fixtures.

Maintenance: adding a new str field requires no changes here. Only new int/bool/list
fields in domain models need a corresponding entry in CHECKED_FIELDS below.
"""
import types
from typing import Union, get_args, get_origin

import pytest

from models.student import Student
from responses.enrollment import StudentProfileResponse
from responses.user import UserProfileResponse


def _inner_types(annotation) -> set:
    """Return the non-None types inside Optional/Union, or the type itself."""
    origin = get_origin(annotation)
    if origin is Union or origin is types.UnionType:
        return {arg for arg in get_args(annotation) if arg is not type(None)}
    return {annotation}


def _assert_compatible(domain_cls, response_cls, field: str) -> None:
    domain_ann = domain_cls.model_fields[field].annotation
    resp_ann = response_cls.model_fields[field].annotation
    domain_types = _inner_types(domain_ann)
    resp_types = _inner_types(resp_ann)
    assert domain_types == resp_types, (
        f"{response_cls.__name__}.{field}: "
        f"response declares {resp_types} but {domain_cls.__name__} has {domain_types}"
    )


# Fields shared between Student domain model and response models that have
# non-trivial types (int, bool, list). str fields are omitted — they can't
# silently mismatch in a way that causes a 500.
STUDENT_TYPED_FIELDS = ["grade", "strength", "weakness", "interest", "learning_style"]


class TestUserProfileResponseMatchesStudentModel:
    @pytest.mark.parametrize("field", STUDENT_TYPED_FIELDS)
    def test_field_type(self, field: str) -> None:
        if field not in UserProfileResponse.model_fields:
            pytest.skip(f"{field} not declared in UserProfileResponse")
        _assert_compatible(Student, UserProfileResponse, field)


class TestStudentProfileResponseMatchesStudentModel:
    @pytest.mark.parametrize("field", ["strength", "weakness", "interest", "learning_style"])
    def test_field_type(self, field: str) -> None:
        _assert_compatible(Student, StudentProfileResponse, field)
