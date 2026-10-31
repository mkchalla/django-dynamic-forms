from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from .models import Form, FormSubmission
from .services import parse_form_data, render_form_fields, validate_required


def form_list(request):
    forms = Form.objects.filter(is_active=True).order_by("name")
    return render(request, "formbuilder/form_list.html", {"forms": forms})


def form_detail(request, slug):
    form = get_object_or_404(Form, slug=slug, is_active=True)

    if request.method == "POST":
        data = parse_form_data(form, request.POST)
        errors = validate_required(form, data)
        if not errors:
            FormSubmission.objects.create(
                form=form,
                data=data,
                submitted_by=request.user if request.user.is_authenticated else None,
            )
            messages.success(request, form.success_message or "Thank you, your submission has been received.")
            return redirect("formbuilder:form_thanks", slug=form.slug)
        for error in errors:
            messages.error(request, error)

    rendered_fields = render_form_fields(form)
    return render(request, "formbuilder/form_detail.html", {"form_obj": form, "rendered_fields": rendered_fields})


def form_thanks(request, slug):
    form = get_object_or_404(Form, slug=slug)
    return render(request, "formbuilder/form_thanks.html", {"form_obj": form})
