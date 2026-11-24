from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailBackend(ModelBackend):
    """Log in with your email (or, for older accounts like the first superuser, your username)."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        login = (username or kwargs.get('email') or '').strip()
        if not login or password is None:
            return None
        User = get_user_model()
        user = User.objects.filter(Q(email__iexact=login) | Q(username__iexact=login)).order_by('id').first()
        if user is None:
            User().set_password(password)   # same work as a real check, so timing doesn't reveal unknown emails
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
