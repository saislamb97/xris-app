import os
import calendar
import json
import numpy as np
from datetime import datetime
from django.conf import settings
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render, redirect
from django.utils.timezone import localtime
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from allauth.account.decorators import verified_email_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.utils.http import urlencode
from subscriptions.models import Subscription, SubscriptionPackage
from .models import XmprData, XmprDownloadLog
import zipstream


def get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    return xff.split(',')[0] if xff else request.META.get('REMOTE_ADDR')


@login_required
@verified_email_required
def xmpr_data(request):
    user = request.user
    search = request.GET.get('search', '').strip()
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    year = request.GET.get('year')
    month = request.GET.get('month')
    limit = int(request.GET.get('limit', 10))
    page_num = request.GET.get('page')

    qs = XmprData.objects.filter(
        Q(csv__isnull=False, csv_size__gt=0) |
        Q(png__isnull=False, png_size__gt=0) |
        Q(tiff__isnull=False, tiff_size__gt=0)
    )

    if search:
        qs = qs.filter(Q(csv__icontains=search) | Q(png__icontains=search) | Q(tiff__icontains=search))
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

    year_list = [d.year for d in XmprData.objects.dates('time', 'year', order='DESC')]
    month_choices = [(i, calendar.month_name[i]) for i in range(1, 13)]
    active_subscription = Subscription.objects.filter(user=user, status=Subscription.STATUS_ACTIVE).first()

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
    active_subscription = Subscription.objects.filter(user=user, status=Subscription.STATUS_ACTIVE).first()

    if not active_subscription or active_subscription.package.name != SubscriptionPackage.PACKAGE_PREMIUM:
        messages.error(request, "Premium subscription required to download files.")
        return redirect('datasets:xmpr_data')

    selected_ids = request.GET.getlist('ids[]')
    if not selected_ids:
        messages.error(request, "No files selected.")
        return redirect('datasets:xmpr_data')

    qs = XmprData.objects.filter(id__in=selected_ids).filter(
        Q(csv__isnull=False, csv_size__gt=0) |
        Q(png__isnull=False, png_size__gt=0) |
        Q(tiff__isnull=False, tiff_size__gt=0)
    )

    max_file_count = getattr(settings, 'XMPR_MAX_FILE_COUNT', 100)
    max_total_size_bytes = getattr(settings, 'XMPR_MAX_TOTAL_SIZE_MB', 500) * 1024 * 1024

    if not qs.exists() or qs.count() > max_file_count:
        messages.error(request, "Invalid or too many files selected.")
        return redirect('datasets:xmpr_data')

    total_size = sum(entry.total_file_size for entry in qs)
    if total_size > max_total_size_bytes:
        messages.error(request, "Selected files exceed allowed size.")
        return redirect('datasets:xmpr_data')

    def generator():
        z = zipstream.ZipFile(mode='w', compression=zipstream.ZIP_DEFLATED)
        for entry in qs.iterator(chunk_size=50):
            timestamp = localtime(entry.time).strftime("%Y-%m-%d_%H-%M")
            for ext, rel_path in [('csv', entry.csv), ('png', entry.png), ('tiff', entry.tiff)]:
                if rel_path:
                    full_path = os.path.join(settings.MEDIA_ROOT, rel_path)
                    if os.path.exists(full_path):
                        original_filename = os.path.basename(rel_path)
                        arcname = f"{entry.time:%Y/%m/%d}/{ext}/{original_filename}"
                        z.write(full_path, arcname)

                        XmprDownloadLog.objects.create(
                            xmpr_data=entry,
                            user=user,
                            ip_address=get_client_ip(request)
                        )
        yield from z

    filename = f"xmpr_{datetime.now():%Y%m%d_%H%M%S}.zip"
    response = StreamingHttpResponse(generator(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

# Thresholds & Color Labels (from rainfallLegend)
RAINFALL_THRESHOLDS = [
    (80, "Extreme"),
    (50, "Heavy"),
    (30, "Very High"),
    (20, "Moderate"),
    (10, "Mild"),
    (5,  "Light"),
    (1,  "Very Light"),
    (0,  "None"),
]

def is_float(value):
    try:
        float(value)
        return True
    except ValueError:
        return False

def get_rain_zone_comment(percent, label):
    if percent > 10:
        return f"\u26a0\ufe0f High {label.lower()} rainfall coverage"
    elif percent > 5:
        return f"Noticeable {label.lower()} rainfall"
    elif percent > 0:
        return f"Minimal {label.lower()} rainfall"
    return f"No {label.lower()} rainfall detected"

def read_and_analyze_csv(path):
    try:
        full_path = os.path.join(settings.MEDIA_ROOT, path)
        with open(full_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        metadata = {}
        matrix = []
        max_len = 0

        for line in lines[:10]:
            parts = [x.strip() for x in line.split(",") if x.strip()]
            if not parts:
                continue
            try:
                if "/" in parts[0] and ":" not in parts[0]:
                    metadata["datetime"] = parts[0]
                elif len(parts) == 1 and is_float(parts[0]):
                    val = float(parts[0])
                    for key in ["lat", "lon", "alt"]:
                        if key not in metadata:
                            metadata[key] = val
                            break
            except:
                continue

        for line in lines:
            try:
                row = [float(x) for x in line.strip().split(",") if is_float(x)]
                if row:
                    max_len = max(max_len, len(row))
                    matrix.append(row)
            except:
                continue

        if not matrix:
            return {"file": path, "error": "No valid matrix data"}

        matrix = [r + [0.0] * (max_len - len(r)) for r in matrix]
        arr = np.array(matrix)

        arr_min = float(np.min(arr))
        arr_max = float(np.max(arr))
        arr_mean = float(np.mean(arr))
        arr_std = float(np.std(arr))
        nonzero_count = int(np.count_nonzero(arr))
        nonzero_percent = round(nonzero_count / arr.size * 100, 2)

        total_cells = arr.size
        rain_distribution = {}
        for i, (threshold, label) in enumerate(RAINFALL_THRESHOLDS):
            upper = RAINFALL_THRESHOLDS[i - 1][0] if i > 0 else float('inf')
            mask = (arr >= threshold) & (arr < upper)
            rain_distribution[label] = round(np.count_nonzero(mask) / total_cells * 100, 2)

        extreme_percent = rain_distribution.get("Extreme", 0.0)
        heavy_percent = rain_distribution.get("Heavy", 0.0)

        if arr_mean >= 80:
            rain_class = "Extreme"
        elif arr_mean >= 50:
            rain_class = "Heavy"
        elif arr_mean >= 20:
            rain_class = "Moderate"
        elif arr_mean >= 1:
            rain_class = "Light"
        else:
            rain_class = "None"

        if arr_max > 100 and extreme_percent > 10:
            decision = "\ud83d\uded8 Extreme rainfall alert"
        elif extreme_percent + heavy_percent > 10:
            decision = "\u26a0\ufe0f Significant rainfall detected"
        elif arr_max >= 5:
            decision = "\u2614\ufe0f Some rainfall observed"
        else:
            decision = "\u2705 No significant rainfall"

        preview = arr[::max(1, len(arr)//20)][:20, ::max(1, arr.shape[1]//50)][:, :50].tolist()

        return {
            **metadata,
            "file": path,
            "shape": arr.shape,
            "min": arr_min,
            "max": arr_max,
            "mean": arr_mean,
            "std": arr_std,
            "nonzero_count": nonzero_count,
            "nonzero_percent": nonzero_percent,
            "extreme_zone_percent": {
                "value": extreme_percent,
                "comment": get_rain_zone_comment(extreme_percent, "Extreme")
            },
            "rain_class": rain_class,
            "decision": decision,
            "rain_distribution": rain_distribution,
            "matrix": arr.tolist(),          # full matrix
            "preview": preview               # keep preview for default display
        }

    except Exception as e:
        return {"file": path, "error": str(e)}

@csrf_exempt
@login_required
@verified_email_required
def analyze_xmpr_data(request):
    try:
        data = json.loads(request.body)
        ids = data.get('ids', [])
        if not ids:
            return JsonResponse({'error': 'No IDs provided'}, status=400)

        entries = XmprData.objects.filter(id__in=ids)
        results = []
        total_files, total_bytes = 0, 0

        for entry in entries:
            if entry.csv:
                analysis = read_and_analyze_csv(entry.csv)
                results.append(analysis)
                total_files += 1
                total_bytes += entry.csv_size or 0

        avg_size = total_bytes / total_files if total_files else 0
        total_size_mb = round(total_bytes / (1024 ** 2), 2)

        return JsonResponse({
            'data': results,
            'summary': {
                'total_files': total_files,
                'total_size_bytes': total_bytes,
                'average_file_size_bytes': avg_size,
                'total_size_mb': total_size_mb,
                'message': f"{total_files} file(s) analyzed ({total_size_mb:.2f} MB)"
            }
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)