import json

from django.contrib import admin
from django.utils.html import format_html

from .models import Form, FormField, FormSubmission, ValueList, ValueListItem


class FormFieldInline(admin.TabularInline):
    model = FormField
    fk_name = "form"
    extra = 1
    fields = [
        "order", "name", "label", "field_type", "required",
        "subform", "repeat_mode", "value_list", "choices_text", "help_text",
    ]
    ordering = ["order"]
    autocomplete_fields = ["subform"]


@admin.register(Form)
class FormAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "is_active", "field_count", "submission_count", "updated_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "slug", "description"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [FormFieldInline]

    def field_count(self, obj):
        return obj.fields.count()
    field_count.short_description = "Fields"

    def submission_count(self, obj):
        return obj.submissions.count()
    submission_count.short_description = "Submissions"


class ValueListItemInline(admin.TabularInline):
    model = ValueListItem
    extra = 1
    fields = ["order", "internal_name", "external_name"]
    ordering = ["order"]


@admin.register(ValueList)
class ValueListAdmin(admin.ModelAdmin):
    list_display = ["name", "item_count"]
    search_fields = ["name"]
    inlines = [ValueListItemInline]

    def item_count(self, obj):
        return obj.items.count()
    item_count.short_description = "Items"


@admin.register(FormSubmission)
class FormSubmissionAdmin(admin.ModelAdmin):
    list_display = ["id", "form", "submitted_by", "submitted_at"]
    list_filter = ["form"]
    date_hierarchy = "submitted_at"
    readonly_fields = ["form", "submitted_by", "submitted_at", "pretty_data"]
    fields = ["form", "submitted_by", "submitted_at", "pretty_data"]

    def has_add_permission(self, request):
        # Submissions are only ever created by the public-facing form view.
        return False

    def pretty_data(self, obj):
        formatted = json.dumps(obj.data, indent=2, ensure_ascii=False, sort_keys=True)
        return format_html("<pre style='white-space:pre-wrap'>{}</pre>", formatted)
    pretty_data.short_description = "Submitted data"
