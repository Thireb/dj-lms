"""Meeting providers (ARCHITECTURE section 7). Only the manual link for now."""

from __future__ import annotations

from apps.lectures.models import DeliveryMode
from apps.lectures.providers.base import MeetingProvider
from apps.lectures.providers.manual import ManualLinkProvider, NoMeetingProvider

_PROVIDERS: dict[str, MeetingProvider] = {
    DeliveryMode.MANUAL_LINK: ManualLinkProvider(),
    DeliveryMode.IN_PERSON: NoMeetingProvider(),
}


def provider_for(delivery_mode: str) -> MeetingProvider:
    return _PROVIDERS[delivery_mode]
