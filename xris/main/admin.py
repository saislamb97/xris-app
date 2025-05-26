from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.admin.models import LogEntry
from django.contrib.contenttypes.admin import GenericTabularInline
from django.core.cache import cache
from .models import User, ProjectConfig, HeroSection, AboutXMPR, GalleryImage

# -------------------------------------------------------------------
# Inline Admin for LogEntry (inside User)
# -------------------------------------------------------------------
class LogEntryInline(admin.TabularInline):
    model = LogEntry
    extra = 0
    can_delete = False
    show_change_link = True
    readonly_fields = [field.name for field in LogEntry._meta.get_fields() if field.concrete]

    def get_queryset(self, request):
        qs = super().get_queryset(request).order_by('-action_time')
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)

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
            'fields': ('email', 'password1', 'password2'),
        }),
    )

# -------------------------------------------------------------------
# Separate LogEntry Admin
# -------------------------------------------------------------------
# Unregister the default LogEntry admin first
admin.site.unregister(LogEntry)

@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'content_type', 'object_repr', 'action_flag', 'change_message', 'action_time')
    list_filter = ('action_flag', 'content_type')
    search_fields = ('object_repr', 'change_message', 'user__email')
    ordering = ('-action_time',)
    readonly_fields = [field.name for field in LogEntry._meta.get_fields() if field.concrete]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

@admin.register(ProjectConfig)
class ProjectConfigAdmin(admin.ModelAdmin):
    list_display = ("site_name", "updated_at")

@admin.register(HeroSection)
class HeroSectionAdmin(admin.ModelAdmin):
    list_display = ("title", "is_active")

@admin.register(AboutXMPR)
class AboutXMPRAdmin(admin.ModelAdmin):
    list_display = ("heading", "is_active")

@admin.register(GalleryImage)
class GalleryImageAdmin(admin.ModelAdmin):
    list_display = ("caption", "order")
    ordering = ("order",)
