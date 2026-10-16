"""Template helpers for the VetLink design system."""

import copy

from django import template
from django.forms.boundfield import BoundField
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name="add_class", is_safe=True)
def add_class(field, css_classes):
    """Render a form field with design-system classes and ARIA wiring.

    Keeping this in a filter (rather than pasting long ``class`` attributes into
    six form templates) means the input styling is defined once.

    Usage::

        {{ form.name|add_class:"field" }}
        {{ form.name|add_class:"field field-error" }}

    The widget instance is copied before mutation: Django reuses a single widget
    object per form, so modifying ``widget.attrs`` in place would leak classes
    into any later render of the same form.
    """
    if not isinstance(field, BoundField):
        return field

    widget = copy.copy(field.field.widget)
    attrs = {
        "class": " ".join(
            part for part in (widget.attrs.get("class", ""), css_classes) if part
        ).strip()
    }

    # Point the control at its help text and/or error message so screen readers
    # announce them with the field.
    described_by = []
    if field.help_text:
        described_by.append(f"{field.auto_id}_helptext")
    if field.errors:
        described_by.append(f"{field.auto_id}_error")
    if described_by:
        attrs["aria-describedby"] = " ".join(described_by)

    # Django's BoundField.as_widget adds required / disabled / aria-invalid.
    return mark_safe(field.as_widget(widget=widget, attrs=attrs))


@register.simple_tag(takes_context=True)
def query_transform(context, **kwargs):
    """Rebuild the current query string, overriding the given parameters.

    Used by pagination and filter controls so that moving between pages or
    switching filters does not lose the other active parameters.

    Usage::

        ?{% query_transform page=2 %}
    """
    query = context["request"].GET.copy()

    for key, value in kwargs.items():
        if value in (None, ""):
            query.pop(key, None)
        else:
            query[key] = value

    return query.urlencode()


@register.simple_tag
def concat(*args):
    """Join values into a single string.

    Useful for composing a subtitle from parts the template already has::

        {% concat prefix pet.name as subtitle %}

    Prefer ``{% blocktranslate %}`` whenever the composed text is prose: a
    concatenation of a literal and a variable cannot be reordered by a
    translator, so the sentence would stay Bulgarian word order in every
    language. This tag is for gluing values, not for building sentences.
    """
    return "".join(str(part) for part in args if part is not None)


@register.filter
def get_species_label(species_choices, code):
    """Resolve a species code to its human-readable label.

    Usage: ``{{ species_choices|get_species_label:selected_species }}``
    """
    for value, label in species_choices or []:
        if value == code:
            return label
    return ""
