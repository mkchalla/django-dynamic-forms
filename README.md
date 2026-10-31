# Django Dynamic Form Builder

A Django app where forms are configured entirely in the admin — no code or
migration needed to add, remove, or reshape a form. Supports nested
("complex") fields, two kinds of repeatable sections, and stores every
submission as JSON.

## Features

- **Configure forms in the admin.** Create a `Form`, add ordered `FormField`
  rows to it (text, textarea, number, email, date, checkbox, dropdown, radio,
  or a "complex" field), all from the Django admin.
- **Complex / nested fields.** A field can be typed `Complex field` and
  point at another `Form`. That sub-form is embedded inline where the field
  is; a sub-form can itself contain complex fields, so forms nest to any
  depth (a "show another form" field, recursively).
- **Repeatable by button.** Any field or sub-form can be set to repeat mode
  `button`. The end user sees an "Add another" button and can add (or
  remove) as many copies as they like — stored as a JSON list.
- **Repeatable by list of values.** Any field or sub-form can instead be set
  to repeat mode `list`, tied to a `ValueList`. The admin configures the
  list once (each entry has an **internal name**, used as the storage key,
  and an **external name**, shown as that block's heading) — e.g. a
  "Quarters" list with `q1 → Quarter 1` … `q4 → Quarter 4`. The field/sub-form
  is then rendered once per list entry automatically; the end user doesn't
  pick anything, they just fill in each labeled block. Stored as a JSON
  object keyed by internal name.
- **Submissions saved to a table.** Every completed form is stored as one
  `FormSubmission` row: which form, when, who (if logged in), and the whole
  answer as a `data` JSON field whose shape mirrors the form's configured
  fields. Because it's JSON, changing a form's fields later never requires a
  database migration.

## Project layout

```
formbuilder_project/   Django project settings/urls
formbuilder/
  models.py            Form, FormField, ValueList, ValueListItem, FormSubmission
  admin.py             Admin config (inline field editor, value-list editor, read-only submissions)
  services.py          Renders a Form's fields to HTML; parses a POST back into nested JSON
  views.py, urls.py     Public form list / detail / thank-you pages
  static/formbuilder/repeat.js   Client-side "Add another" / "Remove" behaviour
  templates/formbuilder/        Bootstrap-styled templates
  management/commands/seed_demo_form.py   Creates a demo form exercising every feature
```

## Setup (macOS / any machine with Python 3.11+)

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser  # follow the prompts

# Optional but recommended: creates a ready-made example form
# that exercises a plain field, a nested contact sub-form, a
# button-repeated team roster, and a list-repeated quarterly section.
python manage.py seed_demo_form

python manage.py runserver
```

Then visit:

- `http://127.0.0.1:8000/admin/` — configure forms, fields, and value lists;
  browse submissions (read-only) under **Formbuilder → Form submissions**.
- `http://127.0.0.1:8000/forms/` — the public list of active forms.
- `http://127.0.0.1:8000/forms/project-status-report/` — the seeded demo
  form, if you ran `seed_demo_form`.

## Configuring a form in the admin

1. **Formbuilder → Forms → Add form.** Give it a name and slug (the slug is
   the public URL, e.g. `/forms/customer-intake/`).
2. In the inline **Form fields** table on that same page, add one row per
   field: internal `name` (used as the JSON key), `label` (shown to users),
   `field type`, whether it's `required`, and its `order`.
   - For a **dropdown/radio** field, put one option per line in
     `choices_text`, either `label` or `internal_value:Visible label`.
   - For a **complex field**, set `field type` to *Complex field* and pick
     the sub-form in `subform`. Build that sub-form the same way first (it
     can be marked inactive — `is_active` only controls whether a form is
     reachable directly at its own `/forms/<slug>/` URL; a sub-form embedded
     inside another form works regardless).
   - To make any row repeat with an **Add another** button, set
     `repeat mode` to *button*.
   - To make any row repeat **once per item of a value list**, first create
     that list under **Formbuilder → Value lists** (each item has an
     internal name + external/display name), then set the field's
     `repeat mode` to *list* and pick that `value list`.
3. Submissions appear under **Formbuilder → Form submissions** as they come
   in, with the submitted data pretty-printed as JSON.

## Known simplifications

- If a submission is missing a required field, the form re-renders with an
  error message but does **not** re-populate what the user already typed
  (re-hydrating arbitrarily nested/repeated values from JSON back into the
  HTML is possible to add, just left out of this first pass to keep the
  renderer simple).
- File-upload field types aren't included; add one by extending
  `FormField.FieldType` and the two branches in `services.py`
  (`_render_input` / `_get_value`) that switch on it.
- Styling uses Bootstrap 5 via CDN for a clean look out of the box — swap
  `templates/formbuilder/base.html` for your own if you'd rather bundle it
  or use a different framework.
