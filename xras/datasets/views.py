import os
import calendar
from datetime import datetime
from django.http import StreamingHttpResponse, HttpResponse
from django.utils.timezone import localtime
from django.contrib.auth.decorators import login_required
from allauth.account.decorators import verified_email_required
from django.shortcuts import render
from django.core.paginator import Paginator
from .models import XmprData, XmprDownloadLog
import zipstream


def get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    return xff.split(',')[0] if xff else request.META.get('REMOTE_ADDR')


@login_required
@verified_email_required
def xmpr_data(request):
    # --- Filters ---
    search    = request.GET.get('search', '').strip()
    date_from = request.GET.get('date_from')
    date_to   = request.GET.get('date_to')
    year      = request.GET.get('year')
    month     = request.GET.get('month')
    limit     = int(request.GET.get('limit', 10))
    page_num  = request.GET.get('page')

    # --- QuerySet: Only where all 3 files exist ---
    qs = XmprData.objects.exclude(csv='').exclude(png='').exclude(tiff='')

    if search:
        qs = qs.filter(time__icontains=search)
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
    page_obj  = paginator.get_page(page_num)

    # --- Year & Month choices ---
    years = XmprData.objects.dates('time', 'year', order='DESC')
    year_list = [d.year for d in years]
    month_choices = [(i, calendar.month_name[i]) for i in range(1, 13)]

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
    })


@login_required
@verified_email_required
def download_xmpr_data(request):
    # either download_all with date range, or specific ids[]
    selected_ids = request.GET.getlist('ids[]')
    download_all = request.GET.get('download_all') == 'true'
    start = request.GET.get('start')
    end   = request.GET.get('end')

    qs = XmprData.objects.all()

    if download_all and start and end:
        try:
            sd = datetime.strptime(start, "%Y-%m-%d").date()
            ed = datetime.strptime(end,   "%Y-%m-%d").date()
        except ValueError:
            return HttpResponse("Dates must be YYYY-MM-DD", status=400)
        qs = qs.filter(time__date__range=(sd, ed))

    elif selected_ids:
        qs = qs.filter(id__in=selected_ids)
    else:
        return HttpResponse("No download parameters", status=400)

    if not qs.exists():
        return HttpResponse("No data found to download", status=404)

    z = zipstream.ZipFile(mode='w', compression=zipstream.ZIP_DEFLATED)
    for entry in qs:
        ts = localtime(entry.time).strftime("%Y-%m-%d_%H-%M")
        y, m, d = entry.time.strftime("%Y"), entry.time.strftime("%m"), entry.time.strftime("%d")
        for ext, field in [('csv', entry.csv), ('png', entry.png), ('tiff', entry.tiff)]:
            if field and hasattr(field, 'path') and os.path.exists(field.path):
                arc = f"{y}/{m}/{d}/{ext}/{ts}.{ext}"
                z.write(field.path, arc)
                XmprDownloadLog.objects.create(
                    xmpr_data=entry,
                    user=request.user,
                    ip_address=get_client_ip(request)
                )

    fname = f"xmpr_{datetime.now():%Y%m%d_%H%M%S}.zip"
    resp = StreamingHttpResponse(z, content_type='application/zip')
    resp['Content-Disposition'] = f'attachment; filename="{fname}"'
    return resp
