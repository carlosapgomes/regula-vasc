"""Services for accounts app."""

from django.contrib.auth import get_user_model

User = get_user_model()


def create_user(username, email, password, roles=None, **extra_fields):
    """Create a user with optional roles.

    Args:
        username: Username for the new user.
        email: Email address.
        password: Password (will be hashed).
        roles: Optional list of role names to assign.
        **extra_fields: Additional fields for User creation.

    Returns:
        The created User instance.
    """
    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        **extra_fields,
    )

    if roles:
        from .models import Role

        for role_name in roles:
            try:
                role = Role.objects.get(name=role_name)
                user.roles.add(role)
            except Role.DoesNotExist:
                pass

    return user
