from django import forms
from django.contrib.auth import authenticate, get_user_model, password_validation
from django.contrib.auth.forms import PasswordChangeForm

from .models import Profile, Review, Spot

User = get_user_model()

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


# --------------------------------------------------------------------------- spots & reviews

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


class AdminSpotForm(SpotForm):
    """Admins can also choose the Spot Owner account and mark a Top Pick."""

    class Meta(SpotForm.Meta):
        fields = SpotForm.Meta.fields + ['owner', 'is_top_pick']
        labels = {**SpotForm.Meta.labels, 'owner': 'Spot Owner account', 'is_top_pick': 'Top Pick'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        owner = self.fields['owner']
        owner.queryset = User.objects.filter(profile__role=Profile.OWNER).order_by('first_name', 'email')
        owner.label_from_instance = lambda u: f'{u.get_full_name() or u.email} ({u.email})'
        owner.help_text = 'Only accounts with the Spot Owner role are listed.'


class ReviewForm(TailwindMixin, forms.ModelForm):
    rating = forms.TypedChoiceField(
        choices=[(5, '5 - Loved it'), (4, '4 - Great'), (3, '3 - Okay'), (2, '2 - Meh'), (1, '1 - Not for me')],
        coerce=int,
    )

    class Meta:
        model = Review
        fields = ['rating', 'comment', 'reviewer_note']    # your name comes from your account
        widgets = {'comment': forms.Textarea(attrs={'rows': 3, 'maxlength': 500})}
        labels = {
            'reviewer_note': 'School / course (optional)',
            'comment': 'Your tambayan tale',
        }


# --------------------------------------------------------------------------- accounts

class LoginForm(TailwindMixin, forms.Form):
    email = forms.CharField(
        label='Email', max_length=254,
        widget=forms.EmailInput(attrs={'autocomplete': 'email', 'placeholder': 'you@example.com', 'autofocus': True}),
    )
    password = forms.CharField(
        label='Password', strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password', 'placeholder': 'Your password'}),
    )
    remember = forms.BooleanField(label='Remember me on this device', required=False, initial=True)

    error_messages = {'invalid': "That email and password don't match. Try again, or reset your password."}

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user = None
        super().__init__(*args, **kwargs)

    def clean(self):
        email, password = self.cleaned_data.get('email'), self.cleaned_data.get('password')
        if email and password:
            self.user = authenticate(self.request, username=email, password=password)
            if self.user is None:
                raise forms.ValidationError(self.error_messages['invalid'], code='invalid')
        return self.cleaned_data


class SignupForm(TailwindMixin, forms.Form):
    full_name = forms.CharField(
        label='Full name', max_length=150,
        widget=forms.TextInput(attrs={'autocomplete': 'name', 'placeholder': 'Juan Dela Cruz'}),
    )
    email = forms.EmailField(
        label='Email', max_length=254,
        widget=forms.EmailInput(attrs={'autocomplete': 'email', 'placeholder': 'you@example.com'}),
    )
    password1 = forms.CharField(
        label='Password', strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'placeholder': 'At least 8 characters'}),
    )
    password2 = forms.CharField(
        label='Confirm password', strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'placeholder': 'Type it again'}),
    )
    wants_owner = forms.BooleanField(label='I own a café or hangout spot', required=False)
    agree = forms.BooleanField(required=True, error_messages={'required': 'Please agree to continue.'})

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists() or User.objects.filter(username__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists. Try logging in instead.')
        return email

    def clean(self):
        data = super().clean()
        p1, p2 = data.get('password1'), data.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', "The passwords don't match.")
        elif p1:
            temp = User(username=data.get('email') or '', email=data.get('email') or '',
                        first_name=data.get('full_name') or '')
            try:
                password_validation.validate_password(p1, temp)
            except forms.ValidationError as e:
                self.add_error('password1', e)
        return data

    def save(self):
        d = self.cleaned_data
        # username = email, so the default Django machinery (and /admin/) keeps working
        return User.objects.create_user(username=d['email'], email=d['email'], password=d['password1'],
                                        first_name=d['full_name'].strip()[:150])


class AccountForm(TailwindMixin, forms.Form):
    full_name = forms.CharField(label='Full name', max_length=150)
    email = forms.EmailField(label='Email', max_length=254)
    school = forms.CharField(label='School / course', max_length=100, required=False,
                             help_text='Shown next to your reviews, e.g. WMSU CS Student')

    def __init__(self, user, *args, **kwargs):
        self.user = user
        kwargs.setdefault('initial', {
            'full_name': user.get_full_name(), 'email': user.email, 'school': user.profile.school,
        })
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        others = User.objects.exclude(pk=self.user.pk)
        if others.filter(email__iexact=email).exists() or others.filter(username__iexact=email).exists():
            raise forms.ValidationError('Another account already uses this email.')
        return email

    def save(self):
        user, d = self.user, self.cleaned_data
        if user.username.lower() == (user.email or '').lower():
            user.username = d['email']           # keep "username = email" accounts in step
        user.email = d['email']
        user.first_name, user.last_name = d['full_name'].strip()[:150], ''
        user.save()
        user.profile.school = d['school']
        user.profile.save(update_fields=['school'])
        return user


class StyledPasswordChangeForm(TailwindMixin, PasswordChangeForm):
    pass
