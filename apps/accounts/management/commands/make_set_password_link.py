"""Issue a new set-password link for a user who lost theirs (audit M2)."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.accounts.models import User
from apps.accounts.services import reissue_set_password_token, set_password_path


class Command(BaseCommand):
    help = "Print a new one-time set-password link. Older unused links stop working."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("email", help="Email of the user.")
        parser.add_argument(
            "--base-url",
            default="",
            help="Site address to put in front of the link, e.g. https://lms.example",
        )

    def handle(self, *args, **options) -> None:
        user = User.objects.filter(email__iexact=options["email"].strip()).first()
        if user is None:
            raise CommandError("No user has this email.")
        if not user.is_active:
            raise CommandError("This user is inactive. Activate them first.")
        path = set_password_path(reissue_set_password_token(user).key)
        # The link goes to stdout only, for the operator to send; never logged.
        self.stdout.write(options["base_url"].rstrip("/") + path)
