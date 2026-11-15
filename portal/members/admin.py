from django.contrib import admin

from .models import Member, MemberLink, PendingLink


class MemberLinkInline(admin.TabularInline):
    model = MemberLink
    extra = 0
    autocomplete_fields = ("user",)


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("last_name", "first_name", "member_number", "birth_date", "grade", "left_on")
    search_fields = ("first_name", "last_name", "member_number")
    list_filter = ("grade",)
    inlines = (MemberLinkInline,)


@admin.register(PendingLink)
class PendingLinkAdmin(admin.ModelAdmin):
    list_display = ("invitation", "member", "kind")
