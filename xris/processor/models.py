from django.db import models
from django.conf import settings
import os

def upload_to_csv(instance, filename):
    return f"converted/{instance.time:%Y/%m/%d}/{filename}"

def upload_to_png(instance, filename):
    return f"images/png/{instance.time:%Y/%m/%d}/{filename}"

def upload_to_tiff(instance, filename):
    return f"images/tif/{instance.time:%Y/%m/%d}/{filename}"

class XmprData(models.Model):
    time = models.DateTimeField()
    csv = models.FileField(upload_to=upload_to_csv)
    image = models.FileField(upload_to=upload_to_png)
    geotiff = models.FileField(upload_to=upload_to_tiff)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"XmprData - {self.time.strftime('%Y-%m-%d %H:%M:%S')}"


def upload_to_jpeg(instance, filename):
    return f"rainmaps/{instance.time:%Y/%m/%d}/{filename}"

class RainMapImage(models.Model):
    time = models.DateTimeField()
    image = models.ImageField(upload_to=upload_to_jpeg)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"RainMap - {self.time.strftime('%Y-%m-%d %H:%M:%S')}"

    @property
    def file_size_bytes(self):
        if self.image and os.path.isfile(self.image.path):
            return os.path.getsize(self.image.path)
        return 0

    @property
    def file_size_display(self):
        size = self.file_size_bytes
        if size == 0:
            return "0 B"
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} TB"


class RainMapDownloadLog(models.Model):
    rainmap = models.ForeignKey(RainMapImage, on_delete=models.CASCADE, related_name='download_logs')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    downloaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-downloaded_at']

    def __str__(self):
        return f"{self.user or 'Anonymous'} downloaded rainmap at {self.downloaded_at:%Y-%m-%d %H:%M:%S}"