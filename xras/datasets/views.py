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
from django.contrib import messages
from subscriptions.models import Subscription, SubscriptionPackage
from .models import XmprData, XmprDownloadLog
import zipstream
from django.utils.http import urlencode
from django.shortcuts import redirect


def get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    return xff.split(',')[0] if xff else request.META.get('REMOTE_ADDR')


@login_required
@verified_email_required
def xmpr_data(request):
    user = request.user

    # --- Filters ---
    search = request.GET.get('search', '').strip()
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    year = request.GET.get('year')
    month = request.GET.get('month')
    limit = int(request.GET.get('limit', 10))
    page_num = request.GET.get('page')

    # --- QuerySet ---
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

    qs = qs.order_by('-time')

    # --- Pagination ---
    paginator = Paginator(qs, limit)
    page_obj = paginator.get_page(page_num)

    # --- Year & Month Choices ---
    years = XmprData.objects.dates('time', 'year', order='DESC')
    year_list = [d.year for d in years]
    month_choices = [(i, calendar.month_name[i]) for i in range(1, 13)]

    # --- Active Subscription Only ---
    active_subscription = Subscription.objects.filter(
        user=user, 
        status=Subscription.STATUS_ACTIVE
    ).first()

    context = {
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
        'query_string': urlencode({k: v for k, v in {
            'search': search,
            'date_from': date_from,
            'date_to': date_to,
            'year': year,
            'month': month,
            'limit': limit,
        }.items() if v}),
        'active_subscription': active_subscription,
        'PACKAGE_FREE': SubscriptionPackage.PACKAGE_FREE,
    }
    return render(request, 'xmpr_data.html', context)


@login_required
@verified_email_required
def download_xmpr_data(request):
    user = request.user

    # --- Check Subscription ---
    active_subscription = Subscription.objects.filter(user=user, status=Subscription.STATUS_ACTIVE).first()

    if not active_subscription:
        messages.error(request, "You must have an active Premium subscription to download files.")
        return redirect('datasets:xmpr_data')  # 🔥 Redirect nicely

    if active_subscription.package.name != SubscriptionPackage.PACKAGE_PREMIUM:
        messages.error(request, "Only Premium subscribers can download XMPR data.")
        return redirect('datasets:xmpr_data')

    # --- Max limits ---
    max_file_count = getattr(settings, 'XMPR_MAX_FILE_COUNT', 100)
    max_total_size_bytes = getattr(settings, 'XMPR_MAX_TOTAL_SIZE_MB', 500) * 1024 * 1024

    selected_ids = request.GET.getlist('ids[]')
    if not selected_ids:
        messages.error(request, "No files selected for download.")
        return redirect('datasets:xmpr_data')

    qs = XmprData.objects.filter(
        id__in=selected_ids
    ).filter(
        Q(csv__isnull=False, csv_size__gt=0) |
        Q(png__isnull=False, png_size__gt=0) |
        Q(tiff__isnull=False, tiff_size__gt=0)
    )

    if not qs.exists():
        messages.error(request, "No valid files found to download.")
        return redirect('datasets:xmpr_data')

    if qs.count() > max_file_count:
        messages.error(request, f"Too many files selected (Max {max_file_count}).")
        return redirect('datasets:xmpr_data')

    total_size = sum(entry.total_file_size for entry in qs)
    if total_size > max_total_size_bytes:
        messages.error(request, f"Total file size exceeds limit (Max {settings.XMPR_MAX_TOTAL_SIZE_MB} MB).")
        return redirect('datasets:xmpr_data')

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
                            user=user,
                            ip_address=get_client_ip(request)
                        )
                    except Exception as e:
                        print(f"Error adding {field.path}: {e}")

        for chunk in z:
            yield chunk

    filename = f"xmpr_{datetime.now():%Y%m%d_%H%M%S}.zip"
    response = StreamingHttpResponse(generator(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response