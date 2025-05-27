from django.db import models

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
