from django.db import models
from django.conf import settings
from django.template.defaultfilters import filesizeformat

class XmprData(models.Model):
    time = models.DateTimeField()

    # Store relative paths to files (e.g., csv/2024/12/22/file.csv)
    csv = models.CharField(max_length=512, blank=True, null=True)
    png = models.CharField(max_length=512, blank=True, null=True)
    tiff = models.CharField(max_length=512, blank=True, null=True)

    csv_size = models.BigIntegerField(default=0)   # in bytes
    png_size = models.BigIntegerField(default=0)
    tiff_size = models.BigIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-time']

    def __str__(self):
        return f"XmprData {self.time:%Y-%m-%d %H:%M:%S}"

    # --- URL Resolvers ---
    def _get_served_url(self, path):
        return f"{settings.MEDIA_URL}{path}" if path else ''

    @property
    def csv_url(self):
        return self._get_served_url(self.csv)

    @property
    def png_url(self):
        return self._get_served_url(self.png)

    @property
    def tiff_url(self):
        return self._get_served_url(self.tiff)

    # --- File size utilities ---
    @property
    def total_file_size(self):
        return sum(filter(None, [self.csv_size, self.png_size, self.tiff_size]))

    @property
    def total_file_size_display(self):
        return filesizeformat(self.total_file_size)


class XmprDownloadLog(models.Model):
    xmpr_data = models.ForeignKey(XmprData, on_delete=models.CASCADE, related_name='download_logs')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    downloaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-downloaded_at']

    def __str__(self):
        return f"{self.user or 'Anonymous'} downloaded at {self.downloaded_at:%Y-%m-%d %H:%M:%S}"
