import os
from django.shortcuts import render, redirect
from django.contrib import messages
from allauth.account.decorators import verified_email_required, login_required
from django.contrib.admin.models import LogEntry
from datetime import timedelta
from django.utils.timezone import now
from django.contrib.admin.models import LogEntry
from django.shortcuts import render
from datasets.models import XmprData, XmprDownloadLog
from subscriptions.models import Subscription, SubscriptionPackage
from .forms import ProfileForm
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.core.paginator import Paginator


def landing(request):
    return render(request, 'landing.html')

def live_radar(request):
    return render(request, 'live_radar.html')

@login_required
@verified_email_required
def home(request):
    user = request.user

    # --- Recent activity logs ---
    logs = LogEntry.objects.filter(user=user).order_by('-action_time')[:5]

    # --- XMPR data count ---
    qs = XmprData.objects.filter(
        Q(csv__isnull=False, csv_size__gt=0) |
        Q(png__isnull=False, png_size__gt=0) |
        Q(tiff__isnull=False, tiff_size__gt=0)
    )
    xmpr_count = qs.count()

    # --- Download statistics (for current user only) ---
    user_downloads = XmprDownloadLog.objects.filter(user=user)

    download_count = user_downloads.count()

    downloaded_size_agg = user_downloads.select_related('xmpr_data').aggregate(
        csv=Coalesce(Sum('xmpr_data__csv_size'), 0),
        png=Coalesce(Sum('xmpr_data__png_size'), 0),
        tiff=Coalesce(Sum('xmpr_data__tiff_size'), 0),
    )
    total_downloaded_size = (
        downloaded_size_agg['csv'] +
        downloaded_size_agg['png'] +
        downloaded_size_agg['tiff']
    )

    # --- Recent uploads and user downloads ---
    recent_uploads = XmprData.objects.order_by('-created_at')[:5]
    recent_downloads = user_downloads.select_related('xmpr_data').order_by('-downloaded_at')[:5]

    # --- Downloads in the last 7 days ---
    last_7_days = now() - timedelta(days=7)
    downloads_7 = (
        user_downloads
        .filter(downloaded_at__gte=last_7_days)
        .extra({'day': "date(downloaded_at)"})
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    chart_labels_7 = [entry['day'].strftime('%Y-%m-%d') for entry in downloads_7]
    chart_data_7 = [entry['count'] for entry in downloads_7]

    # --- Downloads in the last 30 days ---
    last_30_days = now() - timedelta(days=30)
    downloads_30 = (
        user_downloads
        .filter(downloaded_at__gte=last_30_days)
        .extra({'day': "date(downloaded_at)"})
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    chart_labels_30 = [entry['day'].strftime('%Y-%m-%d') for entry in downloads_30]
    chart_data_30 = [entry['count'] for entry in downloads_30]

    # --- Active subscription ---
    active_subscription = Subscription.objects.filter(user=user, status=Subscription.STATUS_ACTIVE).first()

    return render(request, 'home.html', {
        'recent_logs': logs,
        'xmpr_count': xmpr_count,
        'download_count': download_count,
        'total_downloaded_size': total_downloaded_size,
        'recent_uploads': recent_uploads,
        'recent_downloads': recent_downloads,
        'chart_labels_7': chart_labels_7,
        'chart_data_7': chart_data_7,
        'chart_labels_30': chart_labels_30,
        'chart_data_30': chart_data_30,
        'active_subscription': active_subscription,
        'PACKAGE_FREE': SubscriptionPackage.PACKAGE_FREE,
    })

@login_required
@verified_email_required
def activity(request):
    activity_logs_qs = LogEntry.objects.filter(user=request.user) \
        .select_related('content_type') \
        .order_by('-action_time')

    page_num = request.GET.get('page')
    limit = int(request.GET.get('limit', 10))  # Default 10 per page

    paginator = Paginator(activity_logs_qs, limit)
    activity_logs = paginator.get_page(page_num)

    context = {
        'activity_logs': activity_logs,
        'limit': limit,
        'page_sizes': [10, 25, 50, 100],  # Choices for page size
    }
    return render(request, 'activity.html', context)


@login_required
@verified_email_required
def profile(request):
    user = request.user

    if request.method == 'POST' and 'profileForm-submit' in request.POST:
        profile_form = ProfileForm(request.POST, request.FILES, instance=user)
        if profile_form.is_valid():
            profile_form.save()
            messages.success(request, 'Your information was successfully updated.')
            return redirect('main:profile')
    else:
        profile_form = ProfileForm(instance=user)

    context = {
        'profile_form': profile_form,
        'user': user,
    }
    return render(request, 'profile.html', context)
