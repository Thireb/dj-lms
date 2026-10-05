from dataclasses import dataclass


@dataclass(frozen=True)
class MenuItem:
    label: str
    url_name: str
    icon: str
    menu_key: str | None = None
    feature: str | None = None
