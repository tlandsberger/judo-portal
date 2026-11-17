from django.contrib import admin

from .models import (
    Event,
    EventType,
    Occurrence,
    ParticipantRole,
    Participation,
    Schedule,
    ScheduleTeam,
    TargetGroup,
    TargetGroupTemplate,
)


class TargetGroupInline(admin.StackedInline):
    model = TargetGroup
    extra = 0


class ScheduleInline(admin.TabularInline):
    model = Schedule
    extra = 0


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "event_type", "location", "capacity")
    list_filter = ("event_type",)
    inlines = (TargetGroupInline, ScheduleInline)


@admin.register(EventType)
class EventTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "order", "is_active")


@admin.register(ParticipantRole)
class ParticipantRoleAdmin(admin.ModelAdmin):
    list_display = ("name", "order", "is_team", "is_billable", "is_default", "is_active")


class ScheduleTeamInline(admin.TabularInline):
    model = ScheduleTeam
    extra = 0
    raw_id_fields = ("member",)


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ("event", "weekday", "start_time", "valid_from", "valid_until")
    inlines = (ScheduleTeamInline,)


@admin.register(TargetGroupTemplate)
class TargetGroupTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "min_age", "max_age")


class ParticipationInline(admin.TabularInline):
    model = Participation
    extra = 0
    raw_id_fields = ("member",)


@admin.register(Occurrence)
class OccurrenceAdmin(admin.ModelAdmin):
    list_display = ("event", "starts_at", "cancelled_at")
    list_filter = ("event",)
    date_hierarchy = "starts_at"
    inlines = (ParticipationInline,)
