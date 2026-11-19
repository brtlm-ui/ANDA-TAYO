from django import forms

from .models import Review, Spot

# Shared component classes from static/css/style.css (same look as every other input on the site)
INPUT = 'field'
CHECK = 'h-4 w-4 rounded'
FILE = ('block w-full text-sm text-stone-600 file:mr-3 file:rounded-full file:border-0 '
        'file:bg-ink file:px-4 file:py-2 file:text-xs file:font-bold file:text-white')


class TailwindMixin:
    """Adds Tailwind classes to every widget so the forms look right without extra template work."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
                css = CHECK
            elif isinstance(widget, forms.ClearableFileInput):
                css = FILE
            else:
                css = INPUT
            widget.attrs['class'] = (widget.attrs.get('class', '') + ' ' + css).strip()


class SpotForm(TailwindMixin, forms.ModelForm):
    class Meta:
        model = Spot
        fields = [
            'name', 'category', 'mood', 'area', 'address', 'description',
            'cover_image', 'photo_url',
            'starts_at_price', 'min_spend_note',
            'opening_time', 'closing_time', 'is_24_hours',
            'amenities', 'wifi_speed_mbps',
            'latitude', 'longitude',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'opening_time': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
            'closing_time': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
            'photo_url': forms.URLInput(attrs={'placeholder': 'https://...'}),
            'cover_image': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
            'amenities': forms.CheckboxSelectMultiple,
            'latitude': forms.NumberInput(attrs={'step': 'any', 'placeholder': 'e.g. 6.9128'}),
            'longitude': forms.NumberInput(attrs={'step': 'any', 'placeholder': 'e.g. 122.0631'}),
        }
        labels = {
            'starts_at_price': 'Starts at (PHP)',
            'wifi_speed_mbps': 'WiFi speed (Mbps)',
            'is_24_hours': 'Open 24 hours',
            'cover_image': 'Cover photo',
            'photo_url': 'Photo link (optional)',
        }


class ReviewForm(TailwindMixin, forms.ModelForm):
    rating = forms.TypedChoiceField(
        choices=[(5, '5 - Loved it'), (4, '4 - Great'), (3, '3 - Okay'), (2, '2 - Meh'), (1, '1 - Not for me')],
        coerce=int,
    )

    class Meta:
        model = Review
        fields = ['reviewer_name', 'reviewer_note', 'rating', 'comment']
        widgets = {'comment': forms.Textarea(attrs={'rows': 3, 'maxlength': 500})}
        labels = {
            'reviewer_name': 'Your name',
            'reviewer_note': 'School / course (optional)',
            'comment': 'Your tambayan tale',
        }
