import os
import calendar
from datetime import datetime
from django.conf import settings
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import StreamingHttpResponse, HttpResponse
from django.shortcuts import render
from django.utils.timezone import localtime
from django.contrib.auth.decorators import login_required
from allauth.account.decorators import verified_email_required
from .models import XmprData, XmprDownloadLog
import zipstream
from django.utils.http import urlencode


def get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    return xff.split(',')[0] if xff else request.META.get('REMOTE_ADDR')


@login_required
@verified_email_required
def xmpr_data(request):
    # --- Filters ---
    search = request.GET.get('search', '').strip()
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    year = request.GET.get('year')
    month = request.GET.get('month')
    limit = int(request.GET.get('limit', 10))
    page_num = request.GET.get('page')

    # --- QuerySet: entries where at least one file exists and size > 0 ---
    qs = XmprData.objects.filter(
        Q(csv__isnull=False, csv_size__gt=0) |
        Q(png__isnull=False, png_size__gt=0) |
        Q(tiff__isnull=False, tiff_size__gt=0)
    )

    # --- Apply Filters ---
    if search:
        qs = qs.filter(
            Q(csv__icontains=search) |
            Q(png__icontains=search) |
            Q(tiff__icontains=search)
        )
    if date_from:
        qs = qs.filter(time__date__gte=date_from)
    if date_to:
        qs = qs.filter(time__date__lte=date_to)
    if year:
        qs = qs.filter(time__year=year)
    if month:
        qs = qs.filter(time__month=month)

    qs = qs.order_by('-time')  # Newest first

    # --- Pagination ---
    paginator = Paginator(qs, limit)
    page_obj = paginator.get_page(page_num)

    # --- Year & Month Choices ---
    years = XmprData.objects.dates('time', 'year', order='DESC')
    year_list = [d.year for d in years]
    month_choices = [(i, calendar.month_name[i]) for i in range(1, 13)]

    # --- Build query string for pagination links ---
    filter_params = {
        'search': search,
        'date_from': date_from,
        'date_to': date_to,
        'year': year,
        'month': month,
        'limit': limit,
    }
    query_string = urlencode({k: v for k, v in filter_params.items() if v})

    return render(request, 'xmpr_data.html', {
        'page_obj': page_obj,
        'search': search,
        'date_from': date_from,
        'date_to': date_to,
        'year': year,
        'month': month,
        'limit': limit,
        'page_sizes': [10, 25, 50, 100],
        'year_list': year_list,
        'month_choices': month_choices,
        'max_file_count': getattr(settings, 'XMPR_MAX_FILE_COUNT', 100),
        'max_total_size': getattr(settings, 'XMPR_MAX_TOTAL_SIZE_MB', 500),
        'query_string': query_string,  # 🔥 Pass this to template
    })


@login_required
@verified_email_required
def download_xmpr_data(request):
    max_file_count = getattr(settings, 'XMPR_MAX_FILE_COUNT', 100)
    max_total_size_bytes = getattr(settings, 'XMPR_MAX_TOTAL_SIZE_MB', 500) * 1024 * 1024

    selected_ids = request.GET.getlist('ids[]')
    if not selected_ids:
        return HttpResponse("No files selected for download.", status=400)

    # Query entries where at least one file exists
    qs = XmprData.objects.filter(
        id__in=selected_ids
    ).filter(
        Q(csv__isnull=False, csv_size__gt=0) |
        Q(png__isnull=False, png_size__gt=0) |
        Q(tiff__isnull=False, tiff_size__gt=0)
    )

    if not qs.exists():
        return HttpResponse("No valid files found to download.", status=404)

    if qs.count() > max_file_count:
        return HttpResponse(f"Too many files selected (Max {max_file_count})", status=400)

    total_size = sum(entry.total_file_size for entry in qs)
    if total_size > max_total_size_bytes:
        return HttpResponse(f"Total file size exceeds limit (Max {settings.XMPR_MAX_TOTAL_SIZE_MB} MB)", status=400)

    # --- Stream ZIP generation ---
    def generator():
        z = zipstream.ZipFile(mode='w', compression=zipstream.ZIP_DEFLATED)

        for entry in qs.iterator(chunk_size=50):
            timestamp = localtime(entry.time).strftime("%Y-%m-%d_%H-%M")
            y, m, d = entry.time.strftime("%Y"), entry.time.strftime("%m"), entry.time.strftime("%d")

            for ext, field in [('csv', entry.csv), ('png', entry.png), ('tiff', entry.tiff)]:
                if field and hasattr(field, 'path') and os.path.exists(field.path):
                    arcname = f"{y}/{m}/{d}/{ext}/{timestamp}.{ext}"
                    try:
                        z.write(field.path, arcname)
                        XmprDownloadLog.objects.create(
                            xmpr_data=entry,
                            user=request.user,
                            ip_address=get_client_ip(request)
                        )
                    except Exception as e:
                        # Don't stop for single file errors
                        print(f"Error adding {field.path}: {e}")

        for chunk in z:
            yield chunk

    filename = f"xmpr_{datetime.now():%Y%m%d_%H%M%S}.zip"
    response = StreamingHttpResponse(generator(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
