"""Portal-scoped usernames — parent, staff, and admin can reuse the same login name."""

from django.contrib.auth import get_user_model

PORTAL_PREFIXES = {
    "parent": "parent:",
    "staff": "staff:",
    "admin": "admin:",
}


def normalize_login_name(value):
    return (value or "").strip()


def portal_username(portal_type, login_name):
    login_name = normalize_login_name(login_name)
    prefix = PORTAL_PREFIXES[portal_type]
    lowered = login_name.lower()
    for existing_prefix in PORTAL_PREFIXES.values():
        if lowered.startswith(existing_prefix):
            if lowered.startswith(prefix):
                return login_name
            break
    return f"{prefix}{login_name}"


def display_username(stored_username):
    stored_username = normalize_login_name(stored_username)
    lowered = stored_username.lower()
    for prefix in PORTAL_PREFIXES.values():
        if lowered.startswith(prefix):
            return stored_username[len(prefix) :]
    return stored_username


def portal_username_taken(portal_type, login_name):
    User = get_user_model()
    return User.objects.filter(username__iexact=portal_username(portal_type, login_name)).exists()


def user_matches_portal(portal_type, user):
    from .parent_auth import get_parent_account
    from .staff_auth import get_staff_account, is_portal_admin

    if portal_type == "parent":
        return bool(get_parent_account(user))
    if portal_type == "staff":
        return bool(get_staff_account(user))
    if portal_type == "admin":
        return is_portal_admin(user)
    return False


def resolve_auth_username(portal_type, login_name):
    """Map what the user typed to the stored Django username for authenticate()."""
    login_name = normalize_login_name(login_name)
    User = get_user_model()
    prefixed = portal_username(portal_type, login_name)
    if User.objects.filter(username__iexact=prefixed).exists():
        return prefixed
    if portal_type == "admin":
        staff_prefixed = portal_username("staff", login_name)
        staff_user = User.objects.filter(username__iexact=staff_prefixed).first()
        if staff_user and user_matches_portal("admin", staff_user):
            return staff_prefixed
    if portal_type == "staff":
        admin_prefixed = portal_username("admin", login_name)
        admin_user = User.objects.filter(username__iexact=admin_prefixed).first()
        if admin_user and user_matches_portal("staff", admin_user):
            return admin_prefixed
    legacy = User.objects.filter(username__iexact=login_name).first()
    if legacy and user_matches_portal(portal_type, legacy):
        return login_name
    return prefixed


def allocate_portal_username(portal_type, login_name):
    base = normalize_login_name(login_name)
    candidate = base
    counter = 1
    while portal_username_taken(portal_type, candidate):
        candidate = f"{base}{counter}"
        counter += 1
    return portal_username(portal_type, candidate)


def migrate_user_username(user, portal_type):
    """Rename a legacy unprefixed user to portal-scoped storage."""
    current = normalize_login_name(user.username)
    lowered = current.lower()
    target_prefix = PORTAL_PREFIXES[portal_type]
    if lowered.startswith(target_prefix):
        return current, False
    for prefix in PORTAL_PREFIXES.values():
        if lowered.startswith(prefix):
            return current, False
    stored = allocate_portal_username(portal_type, current)
    user.username = stored
    user.save(update_fields=["username"])
    return stored, True
