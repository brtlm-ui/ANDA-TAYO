from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

from core.icons import svg

register = template.Library()


@register.simple_tag
def icon(name, css='h-4 w-4'):
    """{% icon 'wifi' 'h-5 w-5' %} -> inline SVG from core/icons.py (safe: the markup is our own)."""
    return mark_safe(svg(str(name), escape(css)))
