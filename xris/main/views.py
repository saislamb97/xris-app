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
from django.core.cache import cache
from django.db.models.functions import TruncDate, Coalesce
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
import logging
from django.core.paginator import Paginator
from .models import ProjectConfig, HeroSection, AboutXMPR, GalleryImage
from subscriptions.tasks import trigger_subscription_update
from processor.tasks import trigger_xmpr_pipeline

logger = logging.getLogger(__name__)


def landing(request):
    context = {
        "project_config": ProjectConfig.get_cached(),
        "hero": HeroSection.objects.filter(is_active=True).first(),
        "about": AboutXMPR.objects.filter(is_active=True).first(),
        "gallery": GalleryImage.objects.all(),
    }
    return render(request, "landing.html", context)

def live_radar(request):
    xmpr_triggered = trigger_xmpr_pipeline()
    logger.info(f"XMPR triggered: {xmpr_triggered}")
    return render(request, 'live_radar.html')

@login_required
@verified_email_required
def home(request):
    user = request.user

    xmpr_triggered = trigger_xmpr_pipeline()
    subs_triggered = trigger_subscription_update()

    logger.info(f"XMPR triggered: {xmpr_triggered}, Subscription triggered: {subs_triggered}")

    # --- Recent admin activity logs ---
    recent_logs = LogEntry.objects.filter(user=user).order_by('-action_time')[:5]

    # --- XMPR data count (with at least one file and size > 0) ---
    xmpr_queryset = XmprData.objects.filter(
        Q(csv__isnull=False, csv_size__gt=0) |
        Q(png__isnull=False, png_size__gt=0) |
        Q(tiff__isnull=False, tiff_size__gt=0)
    )
    xmpr_count = xmpr_queryset.count()

    # --- Downloads by current user ---
    user_downloads = XmprDownloadLog.objects.select_related('xmpr_data').filter(user=user)
    download_count = user_downloads.count()

    # --- Total downloaded size (count repeated downloads too) ---
    total_downloaded_size = sum(
        (log.xmpr_data.csv_size or 0) +
        (log.xmpr_data.png_size or 0) +
        (log.xmpr_data.tiff_size or 0)
        for log in user_downloads if log.xmpr_data
    )

    # --- Recent uploads and downloads ---
    recent_uploads = XmprData.objects.order_by('-created_at')[:5]
    recent_downloads = user_downloads.order_by('-downloaded_at')[:5]

    # --- Download counts per day (7 days) ---
    downloads_7 = (
        user_downloads
        .filter(downloaded_at__gte=now() - timedelta(days=7))
        .annotate(day=TruncDate('downloaded_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    chart_labels_7 = [entry['day'].strftime('%Y-%m-%d') for entry in downloads_7]
    chart_data_7 = [entry['count'] for entry in downloads_7]

    # --- Download counts per day (30 days) ---
    downloads_30 = (
        user_downloads
        .filter(downloaded_at__gte=now() - timedelta(days=30))
        .annotate(day=TruncDate('downloaded_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    chart_labels_30 = [entry['day'].strftime('%Y-%m-%d') for entry in downloads_30]
    chart_data_30 = [entry['count'] for entry in downloads_30]

    # --- Subscription info ---
    active_subscription = Subscription.objects.filter(
        user=user, status=Subscription.STATUS_ACTIVE
    ).first()

    return render(request, 'home.html', {
        'project_config': ProjectConfig.get_cached(),
        'recent_logs': recent_logs,
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
        "project_config": ProjectConfig.get_cached(),
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
        "project_config": ProjectConfig.get_cached(),
        'profile_form': profile_form,
        'user': user,
    }
    return render(request, 'profile.html', context)
