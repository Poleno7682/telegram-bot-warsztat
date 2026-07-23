"""Regression tests for format_booking_status (docs/REFACTORING_PLAN_2026-07.md,
item 1.3): before this, booking.py rendered status via a local emoji-only
dict that didn't even cover BookingStatus.NEGOTIATING, while calendar.py
rendered plain i18n text with no emoji - two independent mappings of the
same enum that could silently disagree.
"""

import pytest

from app.core.i18n import get_text
from app.models.booking import BookingStatus
from app.utils.booking_utils import format_booking_status, get_booking_status_emoji


def translate(key: str, **kwargs) -> str:
    return get_text(key, "ru", **kwargs)


class TestFormatBookingStatus:
    @pytest.mark.parametrize("status", list(BookingStatus))
    def test_every_status_has_a_non_placeholder_emoji(self, status):
        """Every enum member - including NEGOTIATING, missing from the old
        ad-hoc dict - must resolve to a real emoji, not the "unknown" one."""
        assert get_booking_status_emoji(status) != "❓"

    def test_with_emoji_combines_emoji_and_label(self):
        result = format_booking_status(BookingStatus.ACCEPTED, translate)
        assert result == "✅ Подтверждена"

    def test_without_emoji_returns_bare_label(self):
        result = format_booking_status(BookingStatus.ACCEPTED, translate, with_emoji=False)
        assert result == "Подтверждена"

    def test_unknown_status_falls_back_to_placeholder_emoji(self):
        assert get_booking_status_emoji("not-a-real-status") == "❓"
