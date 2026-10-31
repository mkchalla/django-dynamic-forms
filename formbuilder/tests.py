from django.test import TestCase

from .models import Form, FormField, FormSubmission, ValueList, ValueListItem


class DynamicFormTests(TestCase):
    """End-to-end coverage of nesting, both repeat modes, and submission storage."""

    def setUp(self):
        quarters = ValueList.objects.create(name="Quarters")
        ValueListItem.objects.create(value_list=quarters, internal_name="q1", external_name="Quarter 1", order=0)
        ValueListItem.objects.create(value_list=quarters, internal_name="q2", external_name="Quarter 2", order=1)

        self.contact_form = Form.objects.create(name="Contact", slug="contact-sub", is_active=False)
        FormField.objects.create(form=self.contact_form, order=0, name="full_name", label="Full name", field_type="text", required=True)

        self.member_form = Form.objects.create(name="Member", slug="member-sub", is_active=False)
        FormField.objects.create(form=self.member_form, order=0, name="name", label="Name", field_type="text", required=True)

        self.quarter_form = Form.objects.create(name="Quarter Update", slug="quarter-sub", is_active=False)
        FormField.objects.create(form=self.quarter_form, order=0, name="summary", label="Summary", field_type="textarea")

        self.report = Form.objects.create(name="Report", slug="report", is_active=True)
        FormField.objects.create(form=self.report, order=0, name="project_name", label="Project name", field_type="text", required=True)
        FormField.objects.create(form=self.report, order=1, name="contact", label="Contact", field_type="subform", subform=self.contact_form)
        FormField.objects.create(form=self.report, order=2, name="members", label="Members", field_type="subform", subform=self.member_form, repeat_mode="button")
        FormField.objects.create(form=self.report, order=3, name="quarters", label="Quarters", field_type="subform", subform=self.quarter_form, repeat_mode="list", value_list=quarters)

    def test_form_detail_renders_nesting_and_both_repeat_modes(self):
        response = self.client.get("/forms/report/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('name="contact.full_name"', html)
        self.assertIn('data-base-name="members"', html)
        self.assertIn('name="members.0.name"', html)
        self.assertIn("__INDEX__", html)
        self.assertIn('name="quarters.q1.summary"', html)
        self.assertIn('name="quarters.q2.summary"', html)

    def test_submission_is_parsed_into_matching_nested_json(self):
        payload = {
            "project_name": "Atlas",
            "contact.full_name": "Priya Shah",
            "members.0.name": "Alex Kim",
            "members.1.name": "Sam Lee",
            "quarters.q1.summary": "Kickoff",
            "quarters.q2.summary": "Build",
        }
        response = self.client.post("/forms/report/", payload, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(FormSubmission.objects.count(), 1)

        data = FormSubmission.objects.get().data
        self.assertEqual(data["project_name"], "Atlas")
        self.assertEqual(data["contact"]["full_name"], "Priya Shah")
        self.assertEqual([m["name"] for m in data["members"]], ["Alex Kim", "Sam Lee"])
        self.assertEqual(data["quarters"]["q1"]["summary"], "Kickoff")
        self.assertEqual(data["quarters"]["q2"]["summary"], "Build")

    def test_missing_required_field_is_not_saved(self):
        payload = {
            "contact.full_name": "Priya Shah",
            "members.0.name": "Alex Kim",
            "quarters.q1.summary": "Kickoff",
            "quarters.q2.summary": "Build",
        }
        response = self.client.post("/forms/report/", payload, follow=True)
        self.assertEqual(FormSubmission.objects.count(), 0)
        self.assertIn(b"is required", response.content)
