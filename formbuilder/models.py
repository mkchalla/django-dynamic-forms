"""
Models for the dynamic form builder.

Core idea
---------
A ``Form`` is just a named container of ordered ``FormField`` rows, configured
entirely through the admin. A field can be a simple input (text, number,
date, choice, ...) or a "complex" field whose type is ``subform`` -- it
points at *another* ``Form``. Because a subform field points at the same
``Form``/``FormField`` models, nesting is naturally recursive and can go as
deep as an admin configures it (Form -> field -> subform -> field -> subform
-> ...).

Any field (simple or subform) can also be made repeatable in one of two
ways:

* ``button``  -- rendered once, with an "Add another" button the end user
  clicks to add more copies (classic dynamic/formset-style repeat, user
  controls how many).
* ``list``    -- rendered once per row of a configured ``ValueList``. The
  admin defines a fixed list of entries (each with an internal name used as
  the stored key, and an external name used as the on-screen heading for
  that block); the count and labels come from that list, the end user does
  not pick anything, they just fill in one block per list entry.

Every submission -- whatever shape the form happens to have -- is stored as
a single JSON blob on ``FormSubmission.data``, so no schema migration is
needed when an admin reshapes a form.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Form(models.Model):
    """A top-level form, or a sub-form reusable inside another form."""

    name = models.CharField(max_length=150)
    slug = models.SlugField(
        max_length=150,
        unique=True,
        help_text="Used in the public form URL, e.g. /forms/<slug>/. Sub-forms "
                   "that are only ever embedded inside another form still need "
                   "a unique slug, but it doesn't need to be shared with anyone.",
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(
        default=True,
        help_text="Only active top-level forms are reachable at /forms/<slug>/. "
                   "Sub-forms embedded inside another form work regardless of this flag.",
    )
    success_message = models.CharField(
        max_length=255,
        blank=True,
        default="Thank you, your submission has been received.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        # Guard against the most common accident: a field on a form that
        # points straight back at the same form as its subform, which would
        # make rendering recurse forever. Deeper cycles (A -> B -> A) are the
        # admin's responsibility to avoid; the renderer/parser also carry a
        # depth guard as a last-resort safety net.
        if self.pk is None:
            # Unsaved form: it has no fields yet, and nothing can point at it.
            return
        for field in self.fields.filter(field_type=FormField.FieldType.SUBFORM):
            if field.subform_id == self.id:
                raise ValidationError(
                    f"Field '{field.label}' cannot use its own form as a sub-form."
                )


class ValueList(models.Model):
    """
    A reusable, admin-configured list of (internal name, external name)
    pairs. Used to drive "list" style repeats: a field/sub-form tagged with
    a ValueList is repeated once per item below, headed by that item's
    external name.
    """

    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ValueListItem(models.Model):
    """One repeat-unit inside a ValueList."""

    value_list = models.ForeignKey(ValueList, on_delete=models.CASCADE, related_name="items")
    internal_name = models.SlugField(
        max_length=100,
        help_text="Stored as the key for this repeat's data, e.g. 'q1'.",
    )
    external_name = models.CharField(
        max_length=150,
        help_text="Shown to the end user as the heading for this repeat, e.g. 'Quarter 1'.",
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        unique_together = [("value_list", "internal_name")]

    def __str__(self):
        return f"{self.external_name} ({self.internal_name})"


class FormField(models.Model):
    """One configured field (or embedded sub-form) belonging to a Form."""

    class FieldType(models.TextChoices):
        TEXT = "text", "Text"
        TEXTAREA = "textarea", "Long text"
        NUMBER = "number", "Number"
        EMAIL = "email", "Email"
        DATE = "date", "Date"
        CHECKBOX = "checkbox", "Checkbox (yes/no)"
        SELECT = "select", "Dropdown"
        RADIO = "radio", "Radio buttons"
        SUBFORM = "subform", "Complex field (embed another form)"

    class RepeatMode(models.TextChoices):
        NONE = "none", "Not repeatable"
        BUTTON = "button", "User adds copies with an 'Add another' button"
        LIST = "list", "Repeats once per item in a value list"

    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name="fields")
    name = models.SlugField(
        max_length=100,
        help_text="Internal key, unique within this form. Used as the JSON key "
                   "for this field's stored value.",
    )
    label = models.CharField(max_length=200)
    help_text = models.CharField(max_length=255, blank=True)
    field_type = models.CharField(max_length=20, choices=FieldType.choices, default=FieldType.TEXT)
    required = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    # Only used when field_type == SELECT/RADIO: one option per line, either
    # "label" or "internal:label".
    choices_text = models.TextField(
        blank=True,
        help_text="Only for Dropdown/Radio fields. One option per line, as "
                   "'internal_value:Visible label', or just 'Visible label'.",
    )

    # Only used when field_type == SUBFORM: which Form to embed here. This is
    # what makes a field "complex" -- filling it in means filling in another
    # whole form, which can itself contain further subform fields, to any depth.
    subform = models.ForeignKey(
        Form,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="used_as_subform_by",
        help_text="Only for 'Complex field' type: the form to embed here.",
    )

    repeat_mode = models.CharField(max_length=10, choices=RepeatMode.choices, default=RepeatMode.NONE)
    value_list = models.ForeignKey(
        ValueList,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        help_text="Only when repeat mode is 'list': which value list drives the repeats.",
    )

    class Meta:
        ordering = ["order", "id"]
        unique_together = [("form", "name")]

    def __str__(self):
        return f"{self.label} ({self.form.name})"

    def clean(self):
        if self.field_type == self.FieldType.SUBFORM and not self.subform_id:
            raise ValidationError("Complex fields must select a sub-form to embed.")
        if self.field_type != self.FieldType.SUBFORM and self.subform_id:
            raise ValidationError("Only 'Complex field' type fields may embed a sub-form.")
        if self.repeat_mode == self.RepeatMode.LIST and not self.value_list_id:
            raise ValidationError("Repeat mode 'list' requires a value list.")
        if self.repeat_mode != self.RepeatMode.LIST and self.value_list_id:
            raise ValidationError("A value list is only used when repeat mode is 'list'.")
        if self.field_type == self.FieldType.SUBFORM and self.form_id and self.subform_id == self.form_id:
            raise ValidationError("A field cannot embed its own form as a sub-form.")

    def get_choices(self):
        """Return [(internal_value, label), ...] parsed from choices_text."""
        result = []
        for raw_line in self.choices_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if ":" in line:
                internal, label = line.split(":", 1)
                result.append((internal.strip(), label.strip()))
            else:
                result.append((line, line))
        return result


def _default_submitted_by():
    return ""


class FormSubmission(models.Model):
    """One completed submission of a top-level Form, stored as JSON."""

    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name="submissions")
    submitted_at = models.DateTimeField(auto_now_add=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    data = models.JSONField(
        default=dict,
        help_text="The full nested submission, keyed by field name. Repeated "
                   "fields/sub-forms become JSON lists (button repeat) or "
                   "objects keyed by internal name (list repeat).",
    )

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.form.name} submission #{self.pk} ({self.submitted_at:%Y-%m-%d %H:%M})"
