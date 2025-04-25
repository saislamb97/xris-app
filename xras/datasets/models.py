from django.db import models
from django.conf import settings
import os


class XmprData(models.Model):
    time = models.DateTimeField()
    csv = models.FileField(upload_to='xmpr/csv/', blank=True, null=True)
    png = models.ImageField(upload_to='xmpr/png/', blank=True, null=True)
    tiff = models.ImageField(upload_to='xmpr/tiff/', blank=True, null=True)

    size = models.BigIntegerField(default=0)  # Total size in bytes

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-time']

    def __str__(self):
        return f"XmprData {self.time.strftime('%Y-%m-%d %H:%M:%S')}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.update_size()

    def update_size(self):
        total = 0
        for f in [self.csv, self.png, self.tiff]:
            if f and hasattr(f, 'path') and os.path.isfile(f.path):
                total += os.path.getsize(f.path)
        self.size = total
        XmprData.objects.filter(pk=self.pk).update(size=total)  # Avoid recursion

    # ✅ Cleaned URL helpers
    @property
    def csv_url(self):
        return self._clean_url(self.csv)

    @property
    def png_url(self):
        return self._clean_url(self.png)

    @property
    def tiff_url(self):
        return self._clean_url(self.tiff)

    def _clean_url(self, file_field):
        try:
            url = file_field.url
            return url.replace('/media/media/', '/media/')
        except Exception:
            return ''


class XmprDownloadLog(models.Model):
    xmpr_data = models.ForeignKey(XmprData, on_delete=models.CASCADE, related_name='download_logs')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    downloaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-downloaded_at']

    def __str__(self):
        return f"{self.user} downloaded at {self.downloaded_at}"
