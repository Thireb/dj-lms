"""InstituteSettings defaults and validation."""

from __future__ import annotations

import pytest
from apps.institutes.models import InstituteSettings
from apps.institutes.services import validate_settings_ranges
from django.core.exceptions import ValidationError


@pytest.mark.django_db
def test_settings_created_for_new_institute(institute_a) -> None:
    assert InstituteSettings.unscoped.filter(institute=institute_a).exists()


@pytest.mark.django_db
def test_validate_settings_rejects_invalid_fee_due_day(institute_a) -> None:
    settings = institute_a.settings
    settings.fee_due_day = 29
    with pytest.raises(ValidationError):
        validate_settings_ranges(settings)
