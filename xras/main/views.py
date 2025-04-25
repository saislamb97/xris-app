from django.shortcuts import render, redirect
from django.contrib import messages
from allauth.account.decorators import verified_email_required, login_required
from django.contrib.admin.models import LogEntry

from datasets.models import XmprData
from .forms import ProfileForm  # Assuming you have a form called ProfileForm


def landing(request):
    return render(request, 'landing.html')

def live_radar(request):
    return render(request, 'live_radar.html')

@login_required
@verified_email_required
def home(request):
    user = request.user
    logs = LogEntry.objects.filter(user=user).order_by('-action_time')[:5]
    xmpr_count = XmprData.objects.count()
    
    return render(request, 'home.html', {
        'recent_logs': logs,
        'xmpr_count': xmpr_count,
    })


@login_required
@verified_email_required
def activity(request):
    activity_logs = LogEntry.objects.filter(user=request.user) \
        .select_related('content_type') \
        .order_by('-action_time')

    context = {
        'activity_logs': activity_logs,
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
