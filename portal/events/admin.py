from django.contrib import admin

from .models import Event, EventStaff, Occurrence, Registration, Schedule, Staffing, TargetGroup


class ScheduleInline(admin.TabularInline):
    model = Schedule
    extra = 0


class EventStaffInline(admin.TabularInline):
    model = EventStaff
    extra = 0


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "location", "capacity")
    list_filter = ("kind",)
    inlines = (ScheduleInline, EventStaffInline)


@admin.register(TargetGroup)
class TargetGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "min_age", "max_age")


class RegistrationInline(admin.TabularInline):
    model = Registration
    extra = 0
    raw_id_fields = ("member",)


class StaffingInline(admin.TabularInline):
    model = Staffing
    extra = 0


@admin.register(Occurrence)
class OccurrenceAdmin(admin.ModelAdmin):
    list_display = ("event", "starts_at", "cancelled_at")
    list_filter = ("event",)
    date_hierarchy = "starts_at"
    inlines = (RegistrationInline, StaffingInline)
