import os
import calendar
from datetime import datetime
from django.conf import settings
from django.shortcuts import render, redirect
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from allauth.account.decorators import verified_email_required
from django.contrib import messages
from django.http import StreamingHttpResponse
from django.utils.http import urlencode
from django.core.cache import cache
import zipstream
from main.models import ProjectConfig
from processor.models import RainMapImage, RainMapDownloadLog
from subscriptions.models import Subscription, SubscriptionPackage


def get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    return xff.split(',')[0] if xff else request.META.get('REMOTE_ADDR')


@login_required
@verified_email_required
def rainmap_data(request):
    user = request.user

    search = request.GET.get('search', '').strip()
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    year = request.GET.get('year')
    month = request.GET.get('month')
    limit = int(request.GET.get('limit', 10))
    page_num = request.GET.get('page')

    qs = RainMapImage.objects.all()

    if search:
        qs = qs.filter(image__icontains=search)
    if date_from:
        qs = qs.filter(time__date__gte=date_from)
    if date_to:
        qs = qs.filter(time__date__lte=date_to)
    if year:
        qs = qs.filter(time__year=year)
    if month:
        qs = qs.filter(time__month=month)

    paginator = Paginator(qs.order_by('-time'), limit)
    page_obj = paginator.get_page(page_num)

    year_list = [d.year for d in RainMapImage.objects.dates('time', 'year', order='DESC')]
    month_choices = [(i, calendar.month_name[i]) for i in range(1, 13)]
    active_subscription = Subscription.objects.filter(user=user, status=Subscription.STATUS_ACTIVE).first()

    context = {
        'project_config': ProjectConfig.get_cached(),
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
    return render(request, 'rainmap_data.html', context)


@login_required
@verified_email_required
def download_rainmap_data(request):

    user = request.user

    # --- Subscription check ---
    subscription = Subscription.objects.filter(user=user, status=Subscription.STATUS_ACTIVE).first()
    if not subscription or subscription.package.name != SubscriptionPackage.PACKAGE_PREMIUM:
        messages.error(request, "Premium subscription is required to download files.")
        return redirect('processor:rainmap_data')

    selected_ids = request.GET.getlist('ids[]')
    if not selected_ids:
        messages.error(request, "No rainmap files selected.")
        return redirect('processor:rainmap_data')

    qs = RainMapImage.objects.filter(id__in=selected_ids)
    if not qs.exists():
        messages.error(request, "Selected rainmap files not found.")
        return redirect('processor:rainmap_data')
    
    # --- Limit validations ---
    max_file_count = getattr(settings, 'XMPR_MAX_FILE_COUNT', 100)
    max_total_size_bytes = getattr(settings, 'XMPR_MAX_TOTAL_SIZE_MB', 500) * 1024 * 1024

    if qs.count() > max_file_count:
        messages.error(request, f"You can download up to {max_file_count} files at once.")
        return redirect('processor:rainmap_data')
    
    total_size = sum(entry.file_size_bytes for entry in qs)
    if total_size > max_total_size_bytes:
        messages.error(
            request,
            f"Total selected file size exceeds {max_total_size_bytes // (1024 * 1024)} MB."
        )
        return redirect('processor:rainmap_data')

    # --- Zip stream generator ---
    def zip_generator():
        z = zipstream.ZipFile(mode='w', compression=zipstream.ZIP_DEFLATED)
        for entry in qs:
            if not entry.image:
                continue
            full_path = os.path.join(settings.MEDIA_ROOT, entry.image.name)
            if not os.path.exists(full_path):
                continue

            arcname = f"{entry.time:%Y/%m/%d}/{os.path.basename(full_path)}"
            z.write(full_path, arcname)

            # Log download (avoid duplicates within 5s)
            log_key = f"rainmap_log_{user.id}_{entry.id}"
            if not cache.get(log_key):
                RainMapDownloadLog.objects.create(
                    rainmap=entry,
                    user=user,
                    ip_address=get_client_ip(request)
                )
                cache.set(log_key, True, timeout=5)

        yield from z

    zip_filename = f"rainmaps_{datetime.now():%Y%m%d_%H%M%S}.zip"
    response = StreamingHttpResponse(zip_generator(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{zip_filename}"'
    return response
