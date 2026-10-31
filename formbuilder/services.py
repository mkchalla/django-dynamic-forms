"""
Turns a Form's admin-configured field definitions into HTML on the way out,
and turns a submitted POST back into the matching nested JSON structure on
the way in.

Path convention
---------------
Every field gets a dotted "path" that doubles as its HTML ``name``:

* plain field at the top level        -> "field_name"
* field inside a subform               -> "parent_field.child_field"
* one 'button' repeat, instance N      -> "field_name.<N>"          (N = 0, 1, 2, ...)
* one 'list' repeat, list item X       -> "field_name.<internal_name_of_X>"

A subform field simply continues the path one level deeper for its own
fields, so nesting, and either repeat style, compose freely at any depth.

MAX_DEPTH is a last-resort guard: normal use never approaches it, it only
protects the server if a form is ever misconfigured with a subform cycle.
"""
from django.utils.html import escape, format_html, format_html_join
from django.utils.safestring import mark_safe

from .models import FormField

MAX_DEPTH = 25

TEMPLATE_INDEX = "__INDEX__"


def _path(prefix, name):
    return f"{prefix}.{name}" if prefix else name


def _dom_id(path):
    return "id_" + path.replace(".", "_")


# --------------------------------------------------------------------------
# Rendering (definition -> HTML)
# --------------------------------------------------------------------------

def render_form_fields(form, prefix="", _depth=0):
    """Render every field of ``form`` (a Form instance) at the given path prefix."""
    if _depth > MAX_DEPTH:
        return mark_safe(
            "<p class='text-danger'>Form nesting is too deep to render "
            "(check for a sub-form loop in the admin).</p>"
        )
    parts = [render_field(field, prefix, _depth) for field in form.fields.all().order_by("order", "id")]
    return mark_safe("".join(parts))


def render_field(field, prefix, _depth=0):
    base = _path(prefix, field.name)

    if field.repeat_mode == FormField.RepeatMode.LIST:
        items = list(field.value_list.items.all().order_by("order", "id")) if field.value_list_id else []
        blocks = "".join(
            _render_repeat_block(
                field, _path(base, item.internal_name), heading=item.external_name, depth=_depth
            )
            for item in items
        )
        return format_html(
            '<fieldset class="mb-4 border rounded p-3">'
            '<legend class="fs-6 fw-semibold">{label}</legend>'
            '{help}'
            '<div>{blocks}</div>'
            '</fieldset>',
            label=field.label,
            help=_help_html(field),
            blocks=mark_safe(blocks),
        )

    if field.repeat_mode == FormField.RepeatMode.BUTTON:
        first_block = _render_repeat_block(field, _path(base, "0"), heading=None, depth=_depth, extra_class="repeat-item")
        template_block = _render_repeat_block(
            field, _path(base, TEMPLATE_INDEX), heading=None, depth=_depth, extra_class="repeat-item"
        )
        return format_html(
            '<div class="mb-4 border rounded p-3 repeat-container" data-base-name="{base}" data-next-index="1">'
            '<div class="d-flex justify-content-between align-items-center mb-2">'
            '<span class="fs-6 fw-semibold">{label}</span>'
            '<button type="button" class="btn btn-sm btn-outline-secondary repeat-add">+ Add another</button>'
            '</div>'
            '{help}'
            '<div class="repeat-items">{first}</div>'
            '<template class="repeat-template">{tmpl}</template>'
            '</div>',
            base=base,
            label=field.label,
            help=_help_html(field),
            first=mark_safe(first_block),
            tmpl=mark_safe(template_block),
        )

    # Not repeated: render exactly one unit.
    return mark_safe(_render_unit(field, base, heading=None, depth=_depth))


def _render_repeat_block(field, item_path, heading, depth, extra_class=""):
    inner = _render_unit(field, item_path, heading=heading, depth=depth)
    remove_button = (
        '<button type="button" class="btn btn-sm btn-outline-danger repeat-remove">Remove</button>'
        if heading is None else ""
    )
    return format_html(
        '<div class="{cls} position-relative mb-2">{inner}{remove}</div>',
        cls=("repeat-item " + extra_class).strip(),
        inner=mark_safe(inner),
        remove=mark_safe(remove_button),
    )


def _render_unit(field, path, heading, depth):
    """Render one instance of a field: either a plain input, or (for a
    subform field) a nested fieldset containing that subform's own fields."""
    if field.field_type == FormField.FieldType.SUBFORM:
        legend = heading if heading is not None else field.label
        return format_html(
            '<fieldset class="border rounded p-3 mb-2">'
            '<legend class="fs-6">{legend}</legend>'
            '{help}'
            '{inner}'
            '</fieldset>',
            legend=legend,
            help=_help_html(field) if heading is None else "",
            inner=render_form_fields(field.subform, path, depth + 1),
        )
    return mark_safe(_render_input(field, path, heading))


def _help_html(field):
    if not field.help_text:
        return ""
    return format_html('<div class="form-text mb-2">{}</div>', field.help_text)


def _render_input(field, path, heading):
    dom_id = _dom_id(path)
    required_attr = mark_safe(" required") if field.required else ""
    label_text = heading if heading is not None else field.label
    label_html = format_html(
        '<label for="{id}" class="form-label">{label}{req}</label>',
        id=dom_id, label=label_text,
        req=mark_safe(' <span class="text-danger">*</span>') if field.required else "",
    )
    help_html = _help_html(field) if heading is None else ""

    if field.field_type == FormField.FieldType.TEXTAREA:
        control = format_html(
            '<textarea class="form-control" id="{id}" name="{name}" rows="3"{req}></textarea>',
            id=dom_id, name=path, req=required_attr,
        )
    elif field.field_type == FormField.FieldType.CHECKBOX:
        return format_html(
            '<div class="form-check mb-3">'
            '<input class="form-check-input" type="checkbox" id="{id}" name="{name}"{req}>'
            '<label class="form-check-label" for="{id}">{label}{reqmark}</label>'
            '{help}'
            '</div>',
            id=dom_id, name=path, req=required_attr, label=label_text,
            reqmark=mark_safe(' <span class="text-danger">*</span>') if field.required else "",
            help=help_html,
        )
    elif field.field_type in (FormField.FieldType.SELECT, FormField.FieldType.RADIO):
        choices = field.get_choices()
        if field.field_type == FormField.FieldType.SELECT:
            options = format_html_join(
                "", '<option value="{}">{}</option>', ((v, l) for v, l in choices)
            )
            control = format_html(
                '<select class="form-select" id="{id}" name="{name}"{req}>'
                '<option value="">— Select —</option>{opts}</select>',
                id=dom_id, name=path, req=required_attr, opts=options,
            )
        else:
            radios = format_html_join(
                "",
                '<div class="form-check">'
                '<input class="form-check-input" type="radio" name="{name}" value="{val}" id="{id}"{req}>'
                '<label class="form-check-label" for="{id}">{lbl}</label>'
                '</div>',
                (
                    (path, v, f"{dom_id}_{i}", required_attr, l)
                    for i, (v, l) in enumerate(choices)
                ),
            )
            return format_html(
                '<div class="mb-3"><span class="form-label d-block">{label}{reqmark}</span>{radios}{help}</div>',
                label=label_text,
                reqmark=mark_safe(' <span class="text-danger">*</span>') if field.required else "",
                radios=radios, help=help_html,
            )
    elif field.field_type == FormField.FieldType.NUMBER:
        control = format_html(
            '<input type="number" class="form-control" id="{id}" name="{name}"{req}>',
            id=dom_id, name=path, req=required_attr,
        )
    elif field.field_type == FormField.FieldType.EMAIL:
        control = format_html(
            '<input type="email" class="form-control" id="{id}" name="{name}"{req}>',
            id=dom_id, name=path, req=required_attr,
        )
    elif field.field_type == FormField.FieldType.DATE:
        control = format_html(
            '<input type="date" class="form-control" id="{id}" name="{name}"{req}>',
            id=dom_id, name=path, req=required_attr,
        )
    else:  # TEXT and fallback
        control = format_html(
            '<input type="text" class="form-control" id="{id}" name="{name}"{req}>',
            id=dom_id, name=path, req=required_attr,
        )

    return format_html('<div class="mb-3">{label}{control}{help}</div>', label=label_html, control=control, help=help_html)


# --------------------------------------------------------------------------
# Parsing (POST -> nested dict)
# --------------------------------------------------------------------------

def _discover_button_indices(post_data, base):
    prefix = base + "."
    seen = set()
    for key in post_data.keys():
        if key.startswith(prefix):
            rest = key[len(prefix):]
            token = rest.split(".", 1)[0]
            if token.isdigit():
                seen.add(int(token))
    return sorted(seen)


def _get_value(post_data, path, field):
    if field.field_type == FormField.FieldType.CHECKBOX:
        return post_data.get(path) is not None
    return post_data.get(path, "")


def parse_form_data(form, post_data, prefix="", _depth=0):
    """Walk ``form``'s field definitions and pull matching values out of
    ``post_data`` (a QueryDict or plain dict), returning a nested dict keyed
    by field name exactly the way FormSubmission.data is meant to look."""
    if _depth > MAX_DEPTH:
        return {}

    result = {}
    for field in form.fields.all().order_by("order", "id"):
        base = _path(prefix, field.name)

        if field.repeat_mode == FormField.RepeatMode.LIST:
            obj = {}
            items = field.value_list.items.all().order_by("order", "id") if field.value_list_id else []
            for item in items:
                item_path = _path(base, item.internal_name)
                if field.field_type == FormField.FieldType.SUBFORM:
                    obj[item.internal_name] = parse_form_data(field.subform, post_data, item_path, _depth + 1)
                else:
                    obj[item.internal_name] = _get_value(post_data, item_path, field)
            result[field.name] = obj

        elif field.repeat_mode == FormField.RepeatMode.BUTTON:
            values = []
            for idx in _discover_button_indices(post_data, base):
                item_path = _path(base, str(idx))
                if field.field_type == FormField.FieldType.SUBFORM:
                    values.append(parse_form_data(field.subform, post_data, item_path, _depth + 1))
                else:
                    values.append(_get_value(post_data, item_path, field))
            result[field.name] = values

        else:
            if field.field_type == FormField.FieldType.SUBFORM:
                result[field.name] = parse_form_data(field.subform, post_data, base, _depth + 1)
            else:
                result[field.name] = _get_value(post_data, base, field)

    return result


def validate_required(form, data):
    """Best-effort required-field check against the already-parsed nested
    data. Returns a flat list of human-readable error strings."""
    errors = []
    _walk_required(form, data, errors, path_label=form.name)
    return errors


def _walk_required(form, data, errors, path_label):
    for field in form.fields.all().order_by("order", "id"):
        value = data.get(field.name)

        if field.repeat_mode == FormField.RepeatMode.LIST:
            items = field.value_list.items.all().order_by("order", "id") if field.value_list_id else []
            for item in items:
                sub_value = (value or {}).get(item.internal_name)
                _check_one(field, sub_value, errors, f"{path_label} → {field.label} → {item.external_name}")
        elif field.repeat_mode == FormField.RepeatMode.BUTTON:
            entries = value or []
            if field.required and not entries:
                errors.append(f"{path_label} → {field.label}: at least one entry is required.")
            for entry in entries:
                _check_one(field, entry, errors, f"{path_label} → {field.label}")
        else:
            _check_one(field, value, errors, f"{path_label} → {field.label}")


def _check_one(field, value, errors, label):
    if field.field_type == FormField.FieldType.SUBFORM:
        if isinstance(value, dict):
            _walk_required(field.subform, value, errors, label)
        return
    if field.required and not value:
        errors.append(f"{label} is required.")
