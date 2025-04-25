import uuid
from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db.models import JSONField


def create_unique_username(email):
    base_username = email.split('@')[0]
    suffix = uuid.uuid4().hex[:4]  # 4 hex chars is typically enough to avoid collisions
    candidate = f"{base_username}_{suffix}"
    return candidate

# --------------------------------------------------------------------
# Custom User Manager
# --------------------------------------------------------------------
class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.update({
            "is_staff": True,
            "is_superuser": True
        })
        return self.create_user(email, password, **extra_fields)


# --------------------------------------------------------------------
# User Model
# --------------------------------------------------------------------
class User(AbstractUser):
    email = models.EmailField(unique=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        indexes = [models.Index(fields=['email'])]

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        # Only generate a username if it's not already set
        if not self.username:
            self.username = create_unique_username(self.email)

        super().save(*args, **kwargs)