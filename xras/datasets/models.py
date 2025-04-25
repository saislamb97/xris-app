from django.db import models
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
import os

class XmprData(models.Model):
    time = models.DateTimeField()
    csv = models.FileField(upload_to='xmpr/csv/', blank=True, null=True)
    png = models.ImageField(upload_to='xmpr/png/', blank=True, null=True)
    tiff = models.ImageField(upload_to='xmpr/tiff/', blank=True, null=True)

    csv_size = models.BigIntegerField(default=0)   # in bytes
    png_size = models.BigIntegerField(default=0)
    tiff_size = models.BigIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-time']

    def __str__(self):
        return f"XmprData {self.time:%Y-%m-%d %H:%M:%S}"

    # --- Safe URL helpers ---
    def _get_clean_url(self, file_field):
        if file_field and hasattr(file_field, 'url'):
            return file_field.url.replace('/media/media/', '/media/')
        return ''

    @property
    def csv_url(self):
        return self._get_clean_url(self.csv)

    @property
    def png_url(self):
        return self._get_clean_url(self.png)

    @property
    def tiff_url(self):
        return self._get_clean_url(self.tiff)

    # --- File size helpers ---
    @property
    def total_file_size(self):
        return sum(filter(None, [self.csv_size, self.png_size, self.tiff_size]))

    @property
    def total_file_size_display(self):
        size = self.total_file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} TB"

    def update_file_sizes(self):
        """Update file sizes from filesystem."""
        for field_name in ['csv', 'png', 'tiff']:
            field = getattr(self, field_name)
            size = os.path.getsize(field.path) if field and hasattr(field, 'path') and os.path.exists(field.path) else 0
            setattr(self, f"{field_name}_size", size)


@receiver(post_save, sender=XmprData)
def update_xmpr_file_sizes(sender, instance, **kwargs):
    """Post-save hook to update file sizes without infinite recursion."""
    updated_fields = {}
    for field_name in ['csv', 'png', 'tiff']:
        field = getattr(instance, field_name)
        if field and hasattr(field, 'path') and os.path.exists(field.path):
            updated_fields[f"{field_name}_size"] = os.path.getsize(field.path)
        else:
            updated_fields[f"{field_name}_size"] = 0

    if updated_fields:
        XmprData.objects.filter(pk=instance.pk).update(**updated_fields)


class XmprDownloadLog(models.Model):
    xmpr_data = models.ForeignKey(XmprData, on_delete=models.CASCADE, related_name='download_logs')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    downloaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-downloaded_at']

    def __str__(self):
        return f"{self.user or 'Anonymous'} downloaded at {self.downloaded_at:%Y-%m-%d %H:%M:%S}"
