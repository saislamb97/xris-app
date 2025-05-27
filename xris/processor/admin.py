from django.contrib import admin
from django.utils.html import format_html
from .models import XmprData


@admin.register(XmprData)
class XmprDataAdmin(admin.ModelAdmin):
    list_display = (
        'time', 'created_at', 'updated_at',
        'download_csv', 'download_tiff', 'preview_png'
    )
    list_filter = ('time', 'created_at', 'updated_at')
    search_fields = ('time', 'csv')
    ordering = ('-time',)
    readonly_fields = (
        'created_at', 'updated_at',
        'download_csv', 'download_tiff', 'preview_png'
    )

    def download_csv(self, obj):
        if obj.csv:
            return format_html(
                '<a href="{}" download title="Download CSV file">'
                '<span style="background-color:#2563EB;color:white;padding:2px 8px;border-radius:4px;">CSV</span></a>',
                obj.csv.url
            )
        return format_html('<span style="color:gray;">No CSV</span>')
    download_csv.short_description = "CSV"

    def download_tiff(self, obj):
        if obj.geotiff:
            return format_html(
                '<a href="{}" download title="Download TIFF file">'
                '<span style="background-color:#F59E0B;color:white;padding:2px 8px;border-radius:4px;">TIFF</span></a>',
                obj.geotiff.url
            )
        return format_html('<span style="color:gray;">No TIFF</span>')
    download_tiff.short_description = "TIFF"

    def preview_png(self, obj):
        if obj.image:
            return format_html(
                '<a href="{}" target="_blank" title="Preview PNG">'
                '<img src="{}" width="60" style="border-radius:4px; box-shadow:0 2px 4px rgba(0,0,0,0.1); margin:2px;">'
                '</a>',
                obj.image.url,
                obj.image.url
            )
        return format_html('<span style="color:gray;">No Image</span>')
    preview_png.short_description = "PNG Preview"
