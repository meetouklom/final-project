from django.contrib import admin

from .models import RepairComment, RepairRequest


@admin.register(RepairRequest)
class RepairRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'reported_by', 'location', 'category', 'status', 'created_at')
    list_filter = ('status', 'category', 'created_at')
    search_fields = ('title', 'description', 'location', 'reported_by__username')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('reported_by', 'assigned_to')


@admin.register(RepairComment)
class RepairCommentAdmin(admin.ModelAdmin):
    list_display = ('repair', 'author', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('body', 'repair__title', 'author__username')
    readonly_fields = ('created_at',)
