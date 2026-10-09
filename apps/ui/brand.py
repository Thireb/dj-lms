"""Product brand shown in shells and public pages (Lexicon, roadmap Phase R).

The "LEX" mark stands in until Lexicon's logo arrives as SVG (R2 decision);
swap it here only.
"""

from __future__ import annotations

from typing import Any

from apps.core.roles import Role

BRAND_MARK = "LEX"
BRAND_NAME = "LEXICON"
BRAND_LONG_NAME = "Lexicon Education, Training & Consultancy"

ROLE_LABELS = {
    Role.SUPER_ADMIN: "Super admin",
    Role.INSTITUTE_ADMIN: "Institute admin",
    Role.SUB_ADMIN: "Sub admin",
    Role.TEACHER: "Teacher",
    Role.STUDENT: "Student",
    Role.GUARDIAN: "Guardian",
}

AVATAR_TONES = ("royal", "indigo", "teal", "clay")


def initials(name: str) -> str:
    """ "Hiba Rauf" -> "HR"; "kinza.malik@example.com" -> "KM"; "sam@x.pk" -> "SA"."""
    local = name.split("@", 1)[0]
    words = local.replace(".", " ").replace("_", " ").replace("-", " ").split()
    if len(words) >= 2:
        return (words[0][0] + words[1][0]).upper()
    return (words[0][:2] if words else "?").upper()


def avatar_tone(name: str) -> str:
    """A stable soft tint per person, so the same person keeps one colour."""
    return AVATAR_TONES[sum(map(ord, name)) % len(AVATAR_TONES)]


def user_badge(user: Any) -> dict[str, str]:
    full_name = ""
    if hasattr(user, "get_full_name"):
        full_name = user.get_full_name()
    name = full_name or getattr(user, "email", "") or "Account"
    return {
        "name": name,
        "initials": initials(name),
        "tone": avatar_tone(name),
        "role": ROLE_LABELS.get(getattr(user, "role", ""), ""),
    }
