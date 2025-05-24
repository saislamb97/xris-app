from django.contrib import admin
from django.utils.html import format_html
from .models import XmprData, XmprDownloadLog


class XmprDownloadLogInline(admin.TabularInline):
    model = XmprDownloadLog
    extra = 0
    can_delete = False
    readonly_fields = ('user', 'ip_address', 'downloaded_at')
    show_change_link = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(XmprData)
class XmprDataAdmin(admin.ModelAdmin):
    list_display = (
        'time', 'created_at', 'updated_at', 'file_size',
        'download_csv', 'download_tiff', 'preview_png'
    )
    list_filter = ('time', 'created_at', 'updated_at')
    search_fields = ('time',)
    ordering = ('-time',)
    readonly_fields = (
        'created_at', 'updated_at', 'preview_png',
        'download_tiff', 'download_csv'
    )
    inlines = [XmprDownloadLogInline]

    def file_size(self, obj):
        return obj.total_file_size_display
    file_size.short_description = "Total Size"

    def download_csv(self, obj):
        if obj.csv_url:
            return format_html(
                '<a href="{}" target="_blank" download title="Download CSV file">'
                '<span class="inline-block px-3 py-1 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-500 rounded">'
                'Download CSV</span></a>',
                obj.csv_url
            )
        return format_html('<span style="color:gray;">No CSV</span>')
    download_csv.short_description = "CSV"

    def download_tiff(self, obj):
        if obj.tiff_url:
            return format_html(
                '<a href="{}" target="_blank" download title="Download TIFF file">'
                '<span class="inline-block px-3 py-1 text-sm font-semibold text-white bg-amber-600 hover:bg-amber-500 rounded">'
                'Download TIFF</span></a>',
                obj.tiff_url
            )
        return format_html('<span style="color:gray;">No TIFF</span>')
    download_tiff.short_description = "TIFF"

    def preview_png(self, obj):
        if obj.png_url:
            return format_html(
                '<a href="{}" target="_blank" title="Preview PNG">'
                '<img src="{}" width="60" style="border-radius:4px; box-shadow:0 2px 4px rgba(0,0,0,0.1); margin:2px;">'
                '</a>',
                obj.png_url,
                obj.png_url
            )
        return format_html('<span style="color:gray;">No Image</span>')
    preview_png.short_description = "PNG Preview"


@admin.register(XmprDownloadLog)
class XmprDownloadLogAdmin(admin.ModelAdmin):
    list_display = (
        'xmpr_data_link', 'user', 'ip_address', 'downloaded_at'
    )
    list_filter = ('downloaded_at', 'user')
    search_fields = ('user__username', 'ip_address', 'xmpr_data__id')
    ordering = ('-downloaded_at',)
    readonly_fields = ('xmpr_data', 'user', 'ip_address', 'downloaded_at')

    def xmpr_data_link(self, obj):
        return format_html(
            '<a href="/admin/dataset/xmprdata/{}/change/" title="View XmprData record">{}</a>',
            obj.xmpr_data.id,
            f"XmprData {obj.xmpr_data.time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
    xmpr_data_link.short_description = "XmprData"
