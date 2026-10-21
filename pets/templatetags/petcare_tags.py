
import copy

from django import template
from django.forms.boundfield import BoundField
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name="add_class", is_safe=True)
def add_class(field, css_classes):
    if not isinstance(field, BoundField):
        return field

    widget = copy.copy(field.field.widget)
    attrs = {
        "class": " ".join(
            part for part in (widget.attrs.get("class", ""), css_classes) if part
        ).strip()
    }

    described_by = []
    if field.help_text:
        described_by.append(f"{field.auto_id}_helptext")
    if field.errors:
        described_by.append(f"{field.auto_id}_error")
    if described_by:
        attrs["aria-describedby"] = " ".join(described_by)

    return mark_safe(field.as_widget(widget=widget, attrs=attrs))


@register.simple_tag(takes_context=True)
def query_transform(context, **kwargs):
    query = context["request"].GET.copy()

    for key, value in kwargs.items():
        if value in (None, ""):
            query.pop(key, None)
        else:
            query[key] = value

    return query.urlencode()


@register.simple_tag
def concat(*args):
    return "".join(str(part) for part in args if part is not None)


@register.filter
def get_species_label(species_choices, code):
    for value, label in species_choices or []:
        if value == code:
            return label
    return ""
