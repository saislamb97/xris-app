from django.contrib import admin
from django.utils.html import format_html
from .models import RainMapDownloadLog, RainMapImage, XmprData


@admin.register(XmprData)
class XmprDataAdmin(admin.ModelAdmin):
    list_display = (
        'time', 'created_at', 'updated_at',
        'download_csv', 'download_tiff', 'preview_png'
    )
    list_filter = ('time', 'created_at', 'updated_at')
    search_fields = ('time', 'csv__icontains')
    ordering = ('-time',)
    readonly_fields = (
        'created_at', 'updated_at',
        'download_csv', 'download_tiff', 'preview_png'
    )

    def download_csv(self, obj):
        if obj.csv and hasattr(obj.csv, 'url'):
            return format_html(
                '<a href="{}" target="_blank" download title="Download CSV file">'
                '<span class="inline-block px-3 py-1 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-500 rounded">'
                'Download CSV</span></a>',
                obj.csv.url
            )
        return format_html('<span style="color:gray;">No CSV</span>')
    download_csv.short_description = "CSV"

    def download_tiff(self, obj):
        if obj.geotiff and hasattr(obj.geotiff, 'url'):
            return format_html(
                '<a href="{}" target="_blank" download title="Download TIFF file">'
                '<span class="inline-block px-3 py-1 text-sm font-semibold text-white bg-amber-600 hover:bg-amber-500 rounded">'
                'Download TIFF</span></a>',
                obj.geotiff.url
            )
        return format_html('<span style="color:gray;">No TIFF</span>')
    download_tiff.short_description = "TIFF"

    def preview_png(self, obj):
        if obj.image and hasattr(obj.image, 'url'):
            return format_html(
                '<a href="{}" target="_blank" title="Preview PNG">'
                '<img src="{}" width="60" style="border-radius:4px; box-shadow:0 2px 4px rgba(0,0,0,0.1); margin:2px;">'
                '</a>',
                obj.image.url,
                obj.image.url
            )
        return format_html('<span style="color:gray;">No Image</span>')
    preview_png.short_description = "PNG Preview"


class RainMapDownloadLogInline(admin.TabularInline):
    model = RainMapDownloadLog
    extra = 0
    can_delete = False
    readonly_fields = ('user', 'ip_address', 'downloaded_at')
    show_change_link = False

    def has_add_permission(self, request, obj=None):
        return False
    
@admin.register(RainMapImage)
class RainMapImageAdmin(admin.ModelAdmin):
    list_display = ('time', 'created_at', 'preview_image', 'download_image')
    list_filter = ('time', 'created_at')
    search_fields = ('image__icontains',)
    ordering = ('-time',)
    readonly_fields = ('created_at', 'preview_image', 'download_image')
    inlines = [RainMapDownloadLogInline]

    def preview_image(self, obj):
        if obj.image and hasattr(obj.image, 'url'):
            return format_html(
                '<a href="{}" target="_blank" title="Preview RainMap">'
                '<img src="{}" width="80" style="border-radius:4px; box-shadow:0 2px 4px rgba(0,0,0,0.1); margin:2px;">'
                '</a>',
                obj.image.url,
                obj.image.url
            )
        return format_html('<span style="color:gray;">No Image</span>')
    preview_image.short_description = "RainMap Preview"

    def download_image(self, obj):
        if obj.image and hasattr(obj.image, 'url'):
            return format_html(
                '<a href="{}" download title="Download JPEG file">'
                '<span class="inline-block px-3 py-1 text-sm font-semibold text-white bg-green-600 hover:bg-green-500 rounded">'
                'Download JPEG</span></a>',
                obj.image.url
            )
        return format_html('<span style="color:gray;">No Image</span>')
    download_image.short_description = "Download"

@admin.register(RainMapDownloadLog)
class RainMapDownloadLogAdmin(admin.ModelAdmin):
    list_display = (
        'rainmap_link', 'user', 'ip_address', 'downloaded_at'
    )
    list_filter = ('downloaded_at', 'user')
    search_fields = ('user__username', 'ip_address', 'rainmap__id')
    ordering = ('-downloaded_at',)
    readonly_fields = ('rainmap', 'user', 'ip_address', 'downloaded_at')

    def rainmap_link(self, obj):
        return format_html(
            '<a href="/admin/processor/rainmapimage/{}/change/" title="View RainMapImage record">{}</a>',
            obj.rainmap.id,
            f"RainMap {obj.rainmap.time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
    rainmap_link.short_description = "RainMap"
