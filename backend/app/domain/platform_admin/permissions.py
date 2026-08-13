"""Known platform-admin permission codes.

Unlike tenant RBAC's permissions/roles tables (app/domain/identity),
this is a plain constant tuple, not a DB reference table — there are
only three codes, they never vary per tenant, and a whole reference
table would be pure overhead for something this small and static.
Enforcement never queries this list; it only checks whether a code is
present in a specific PlatformAdminGrant.permission_codes (see
require_platform_permission in app/api/dependencies.py). This list
exists so the admin UI has something to render as togglable checkboxes,
and so a typo'd permission code is easy to catch by eye.
"""

from __future__ import annotations

PLATFORM_SETTINGS_VIEW = "platform.settings.view"
PLATFORM_SETTINGS_EDIT = "platform.settings.edit"
PLATFORM_ADMINS_MANAGE = "platform.admins.manage"

ALL_PLATFORM_PERMISSIONS: tuple[tuple[str, str], ...] = (
    (PLATFORM_SETTINGS_VIEW, "View platform-wide configuration settings."),
    (PLATFORM_SETTINGS_EDIT, "Edit platform-wide configuration settings."),
    (PLATFORM_ADMINS_MANAGE, "Grant, update, or revoke platform admin access for other users."),
)

ALL_PLATFORM_PERMISSION_CODES: frozenset[str] = frozenset(
    code for code, _ in ALL_PLATFORM_PERMISSIONS
)
