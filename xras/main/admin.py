from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.admin.models import LogEntry
from django.contrib.contenttypes.admin import GenericTabularInline

from .models import User


# -------------------------------------------------------------------
# Inline Admin for LogEntry
# -------------------------------------------------------------------
class LogEntryInline(admin.TabularInline):
    model = LogEntry
    extra = 0
    readonly_fields = [field.name for field in LogEntry._meta.fields]
    can_delete = False
    show_change_link = True

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs.order_by('-action_time')
        return qs.filter(user=request.user).order_by('-action_time')


# -------------------------------------------------------------------
# Custom User Admin
# -------------------------------------------------------------------
@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    model = User
    inlines = [LogEntryInline]
    ordering = ('-date_joined',)
    list_display = ('email', 'username', 'first_name', 'last_name', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_superuser', 'is_active')
    search_fields = ('email', 'username', 'first_name', 'last_name')

    fieldsets = (
        (None, {'fields': ('email', 'username', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'avatar')}),
        ('Roles', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
        ('Permissions', {'fields': ('groups', 'user_permissions')}),
        ('Important Dates', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2')
        }),
    )