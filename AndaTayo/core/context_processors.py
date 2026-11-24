from .roles import account_menu


def account(request):
    """`me` = the signed-in user's name, role badge and menu links (used by the header and dashboards)."""
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated:
        return {'me': account_menu(user)}
    return {}
