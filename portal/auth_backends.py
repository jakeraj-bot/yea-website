"""Accept portal login names without the stored parent:/staff:/admin: prefix."""

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class PortalUsernameBackend(ModelBackend):
    """Django /admin/ and other stock logins do not use PortalAuthenticationForm.

    Stored usernames are namespaced (admin:yeaadmin). This backend still accepts
    the name people type (yeaadmin) so website admin and portal admin stay in sync.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if username is None or password is None:
            return None

        from .usernames import PORTAL_PREFIXES, resolve_auth_username

        candidates = []
        seen = set()

        def add(value):
            value = (value or "").strip()
            key = value.casefold()
            if value and key not in seen:
                seen.add(key)
                candidates.append(value)

        add(username)
        for portal_type in PORTAL_PREFIXES:
            add(resolve_auth_username(portal_type, username))

        found_user = False
        for candidate in candidates:
            user = UserModel.objects.filter(username__iexact=candidate).first()
            if user is None:
                continue
            found_user = True
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        if not found_user:
            UserModel().set_password(password)
        return None
