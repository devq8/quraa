from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    """Custom manager for User with email as the main identifier."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address.")
        email = self.normalize_email(email)
        # Use email as username if username not provided
        if not extra_fields.get("username"):
            extra_fields["username"] = email
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("user_type", User.UserType.ADMIN)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Custom user model with distinct types:
    - Admin: Full authorities (superadmin).
    - Staff: Higher authorities, configurable via Django admin groups.
    - Reciter: Limited authorities.
    """

    class UserType(models.TextChoices):
        ADMIN = "admin", _("Admin")
        STAFF = "staff", _("Staff")
        RECITER = "reciter", _("Reciter")

    email = models.EmailField(_("email address"), unique=True)
    user_type = models.CharField(
        max_length=20,
        choices=UserType.choices,
        default=UserType.RECITER,
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        # Keep is_staff and is_superuser in sync with user_type
        if self.user_type == self.UserType.ADMIN:
            self.is_staff = True
            self.is_superuser = True
        elif self.user_type == self.UserType.STAFF:
            self.is_staff = True
            self.is_superuser = False
        else:  # RECITER
            self.is_staff = False
            self.is_superuser = False
        super().save(*args, **kwargs)

    # Convenience checks (Django already provides is_staff and is_superuser)
    @property
    def is_admin_user(self):
        """True if user has full admin (superuser) authorities."""
        return self.is_superuser

    @property
    def is_staff_user(self):
        """True if user is staff (higher authorities, group-based)."""
        return self.is_staff and not self.is_superuser

    @property
    def is_reciter(self):
        """True if user is a reciter with limited authorities."""
        return self.user_type == self.UserType.RECITER
