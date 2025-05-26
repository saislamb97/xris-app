import uuid
from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.core.cache import cache
from django.core.exceptions import ValidationError


def create_unique_username(email):
    base_username = email.split('@')[0]
    suffix = uuid.uuid4().hex[:4]  # 4 hex chars is typically enough to avoid collisions
    candidate = f"{base_username}_{suffix}"
    return candidate

def avatar_upload_path(instance, filename):
    # Uses user's primary key to create a path like: xris/avatars/42/avatar.jpg
    return f'xris/avatars/{instance.pk}/{filename}'

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
    avatar = models.ImageField(upload_to=avatar_upload_path, blank=True, null=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        indexes = [models.Index(fields=['email'])]

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = create_unique_username(self.email)

        super().save(*args, **kwargs)

class ProjectConfig(models.Model):
    site_name = models.CharField(max_length=100, default="XRIS")
    short_description = models.CharField(max_length=255, default="X-Band Radar Information System")
    logo = models.ImageField(upload_to='xris/project/logo/', help_text="Logo image")
    favicon = models.ImageField(upload_to='xris/project/favicon/', help_text="Favicon image")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.site_name

    def clean(self):
        if not self.pk and ProjectConfig.objects.exists():
            raise ValidationError("Only one ProjectConfig instance is allowed.")

    def save(self, *args, **kwargs):
        self.full_clean()
        result = super().save(*args, **kwargs)
        cache.set('project_config', self)  # update cache after save
        return result

    @classmethod
    def get_cached(cls):
        config = cache.get('project_config')
        if not config:
            config = cls.objects.first()
            if config:
                cache.set('project_config', config)
        return config

class HeroSection(models.Model):
    title = models.CharField(max_length=200, default="Empowering Rainfall Intelligence")
    subtitle = models.TextField(default="XRIS is a web-based platform to access, analyze, and visualize data...")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title

class AboutXMPR(models.Model):
    heading = models.CharField(max_length=200, default="What is X-Band Multiparameter Radar?")
    paragraph_1 = models.TextField()
    paragraph_2 = models.TextField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.heading

def gallery_image_path(instance, filename):
    return f'xris/gallery/{filename}'

class GalleryImage(models.Model):
    image = models.ImageField(upload_to=gallery_image_path)
    caption = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.caption or f"Image {self.pk}"
