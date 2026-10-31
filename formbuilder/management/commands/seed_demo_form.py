from django.core.management.base import BaseCommand
from django.db import transaction

from formbuilder.models import Form, FormField, ValueList, ValueListItem


class Command(BaseCommand):
    help = (
        "Creates a demo form in the admin showing every feature: a plain "
        "field, a dropdown, a nested 'complex' field (a sub-form embedded "
        "inside the form), a sub-form repeated with an Add-another button, "
        "and a sub-form repeated once per item of a configured value list."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        # A reusable value list: drives the "list" style repeat.
        quarters, _ = ValueList.objects.get_or_create(
            name="Quarters", defaults={"description": "Fiscal quarters, used for quarterly report sections."}
        )
        quarters.items.all().delete()
        for i, (internal, external) in enumerate(
            [("q1", "Quarter 1"), ("q2", "Quarter 2"), ("q3", "Quarter 3"), ("q4", "Quarter 4")]
        ):
            ValueListItem.objects.create(value_list=quarters, internal_name=internal, external_name=external, order=i)

        # Sub-form #1: a small "Contact person" form, embedded once (not repeated).
        contact_form, _ = Form.objects.get_or_create(
            slug="contact-person-subform", defaults={"name": "Contact Person", "is_active": False}
        )
        contact_form.fields.all().delete()
        FormField.objects.create(form=contact_form, order=0, name="full_name", label="Full name", field_type="text", required=True)
        FormField.objects.create(form=contact_form, order=1, name="email", label="Email", field_type="email", required=True)

        # Sub-form #2: a "Team member" form, repeated with an Add-another button.
        member_form, _ = Form.objects.get_or_create(
            slug="team-member-subform", defaults={"name": "Team Member", "is_active": False}
        )
        member_form.fields.all().delete()
        FormField.objects.create(form=member_form, order=0, name="name", label="Name", field_type="text", required=True)
        FormField.objects.create(form=member_form, order=1, name="role", label="Role", field_type="text", required=False)

        # Sub-form #3: a "Quarterly update" form, repeated once per Quarters item.
        quarter_form, _ = Form.objects.get_or_create(
            slug="quarterly-update-subform", defaults={"name": "Quarterly Update", "is_active": False}
        )
        quarter_form.fields.all().delete()
        FormField.objects.create(form=quarter_form, order=0, name="summary", label="Summary", field_type="textarea", required=False)
        FormField.objects.create(form=quarter_form, order=1, name="hours_spent", label="Hours spent", field_type="number", required=False)

        # Top-level form that ties it all together.
        report_form, _ = Form.objects.get_or_create(
            slug="project-status-report",
            defaults={
                "name": "Project Status Report",
                "description": "Demo form: plain fields, a nested contact sub-form, a "
                                "button-repeated team roster, and a list-repeated quarterly section.",
                "is_active": True,
            },
        )
        report_form.fields.all().delete()
        FormField.objects.create(form=report_form, order=0, name="project_name", label="Project name", field_type="text", required=True)
        FormField.objects.create(
            form=report_form, order=1, name="status", label="Overall status", field_type="select", required=True,
            choices_text="green:On track\nyellow:At risk\nred:Off track",
        )
        FormField.objects.create(
            form=report_form, order=2, name="contact", label="Primary contact", field_type="subform",
            subform=contact_form,
        )
        FormField.objects.create(
            form=report_form, order=3, name="team_members", label="Team members", field_type="subform",
            subform=member_form, repeat_mode="button",
        )
        FormField.objects.create(
            form=report_form, order=4, name="quarterly_updates", label="Quarterly updates", field_type="subform",
            subform=quarter_form, repeat_mode="list", value_list=quarters,
        )

        self.stdout.write(self.style.SUCCESS(
            f"Demo form ready: /forms/{report_form.slug}/  (edit it in /admin/ under Formbuilder > Forms)"
        ))
