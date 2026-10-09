"""Custom user model: email login, single product role, optional institute."""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from apps.core.roles import Role as RoleConstants


class UserManager(BaseUserManager["User"]):
    use_in_migrations = True

    def _create_user(
        self,
        email: str,
        password: str | None,
        **extra_fields: object,
    ) -> User:
        if not email:
            msg = "Email must be set"
            raise ValueError(msg)
        email = self.normalize_email(email).strip().lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.full_clean()
        user.save(using=self._db)
        return user

    def create_user(
        self,
        email: str,
        password: str | None = None,
        **extra_fields: object,
    ) -> User:
        # A super admin always needs the developer admin (audit L8).
        is_super = extra_fields.get("role") == RoleConstants.SUPER_ADMIN
        extra_fields.setdefault("is_staff", is_super)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def get_by_natural_key(self, username: str) -> User:
        # Sign-in ignores case: Sam@Example.com is sam@example.com (audit H2).
        return self.get(email__iexact=username.strip())

    def create_superuser(
        self,
        email: str,
        password: str | None = None,
        **extra_fields: object,
    ) -> User:
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.SUPER_ADMIN)
        extra_fields.setdefault("institute", None)

        if extra_fields.get("is_staff") is not True:
            msg = "Superuser must have is_staff=True."
            raise ValueError(msg)
        if extra_fields.get("is_superuser") is not True:
            msg = "Superuser must have is_superuser=True."
            raise ValueError(msg)

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """One account, one product role; email is the login identifier."""

    class Role(models.TextChoices):
        SUPER_ADMIN = RoleConstants.SUPER_ADMIN, "Super admin"
        INSTITUTE_ADMIN = RoleConstants.INSTITUTE_ADMIN, "Institute admin"
        SUB_ADMIN = RoleConstants.SUB_ADMIN, "Sub admin"
        TEACHER = RoleConstants.TEACHER, "Teacher"
        STUDENT = RoleConstants.STUDENT, "Student"
        GUARDIAN = RoleConstants.GUARDIAN, "Guardian"

    username = None
    email = models.EmailField("email address", unique=True)
    role = models.CharField(
        max_length=32,
        choices=Role.choices,
        default=Role.STUDENT,
    )
    institute = models.ForeignKey(
        "institutes.Institute",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="users",
    )
    phone = models.CharField(max_length=32, blank=True, default="")
    timezone = models.CharField(max_length=63, blank=True, default="")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    class Meta:
        ordering = ["email"]
        constraints = [
            models.UniqueConstraint(
                Lower("email"), name="accounts_user_email_lower_unique"
            ),
        ]

    def __str__(self) -> str:
        return self.email

    def clean(self) -> None:
        super().clean()
        if self.role == self.Role.SUPER_ADMIN:
            if self.institute_id is not None:
                raise ValidationError(
                    {"institute": "Super admin must not belong to an institute."}
                )
        else:
            if self.is_staff or self.is_superuser:
                raise ValidationError(
                    "Only super admin accounts may use Django admin flags."
                )
            if self.institute_id is None:
                raise ValidationError({"institute": "This role requires an institute."})

    def save(self, *args: object, **kwargs: object) -> None:
        self.email = (self.email or "").strip().lower()
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def is_super_admin(self) -> bool:
        return self.role == self.Role.SUPER_ADMIN

    @property
    def is_institute_admin(self) -> bool:
        return self.role == self.Role.INSTITUTE_ADMIN

    @property
    def is_sub_admin(self) -> bool:
        return self.role == self.Role.SUB_ADMIN

    @property
    def is_teacher(self) -> bool:
        return self.role == self.Role.TEACHER

    @property
    def is_student(self) -> bool:
        return self.role == self.Role.STUDENT

    @property
    def is_guardian(self) -> bool:
        return self.role == self.Role.GUARDIAN


class SetPasswordToken(models.Model):
    """One-time link for first-time password setup (not tenant-scoped)."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="set_password_tokens",
    )
    key = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    @classmethod
    def generate_key(cls) -> str:
        return secrets.token_urlsafe(32)

    @staticmethod
    def hash_key(plaintext_key: str) -> str:
        return hashlib.sha256(plaintext_key.encode("utf-8")).hexdigest()

    @classmethod
    def create_for_user(
        cls, user: User, *, ttl_hours: int = 72
    ) -> tuple[str, SetPasswordToken]:
        plaintext_key = cls.generate_key()
        token = cls.objects.create(
            user=user,
            key=cls.hash_key(plaintext_key),
            expires_at=timezone.now() + timedelta(hours=ttl_hours),
        )
        return plaintext_key, token

    def is_valid(self) -> bool:
        if self.used_at is not None:
            return False
        return timezone.now() <= self.expires_at

    def mark_used(self) -> None:
        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])
