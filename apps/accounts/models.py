"""Custom user model: email login, single product role, optional institute."""

from __future__ import annotations

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models

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
        email = self.normalize_email(email)
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
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

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
    timezone = models.CharField(max_length=63, blank=True, default="")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    class Meta:
        ordering = ["email"]

    def __str__(self) -> str:
        return self.email

    def clean(self) -> None:
        super().clean()
        if self.role == self.Role.SUPER_ADMIN:
            if self.institute_id is not None:
                raise ValidationError(
                    {"institute": "Super admin must not belong to an institute."}
                )
        elif self.institute_id is None:
            raise ValidationError({"institute": "This role requires an institute."})

    def save(self, *args: object, **kwargs: object) -> None:
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
