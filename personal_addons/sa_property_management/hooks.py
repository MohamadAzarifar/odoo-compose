# -*- coding: utf-8 -*-
from odoo import release

# XML IDs of the security groups that should be grouped under the
# "Property Management" category / privilege heading in Settings > Users.
_GROUP_XMLIDS = (
    "sa_property_management.group_sa_property_agent",
    "sa_property_management.group_sa_property_user",
    "sa_property_management.group_sa_property_manager",
    "sa_property_management.group_sa_construction_user",
    "sa_property_management.group_sa_construction_manager",
)
_CATEGORY_XMLID = "sa_property_management.module_category_sa_property"
_MANAGER_XMLID = "sa_property_management.group_sa_property_manager"
_CONSTRUCTION_MANAGER_XMLID = "sa_property_management.group_sa_construction_manager"


def post_init_hook(env):
    """Attach the property groups to their category in a version-safe way.

    Odoo 19 replaced ``res.groups.category_id`` (a link to
    ``ir.module.category``) with ``res.groups.privilege_id`` (a link to the new
    ``res.groups.privilege`` model, which itself carries ``category_id``).
    To keep a single codebase compatible with Odoo 18 *and* 19+, the linkage is
    set here in Python instead of in static XML.
    """
    category = env.ref(_CATEGORY_XMLID, raise_if_not_found=False)
    if not category:
        return

    groups = env["res.groups"].browse(
        [
            ref.id
            for ref in (
                env.ref(xmlid, raise_if_not_found=False) for xmlid in _GROUP_XMLIDS
            )
            if ref
        ]
    )
    if not groups:
        return

    if release.version_info[0] >= 19:
        privilege_model = env["res.groups.privilege"]
        privilege = privilege_model.search(
            [("category_id", "=", category.id)], limit=1
        )
        if not privilege:
            privilege = privilege_model.create(
                {"name": category.name, "category_id": category.id}
            )
        groups.privilege_id = privilege.id
    else:
        groups.category_id = category.id

    # Grant the Manager group to the admin/root users. The relevant field was
    # renamed from ``users`` (<= 18) to ``user_ids`` (>= 19), so detect it.
    manager = env.ref(_MANAGER_XMLID, raise_if_not_found=False)
    if manager:
        users_field = "user_ids" if "user_ids" in manager._fields else "users"
        admins = env["res.users"].browse(
            [
                ref.id
                for ref in (
                    env.ref("base.user_root", raise_if_not_found=False),
                    env.ref("base.user_admin", raise_if_not_found=False),
                )
                if ref
            ]
        )
        if admins:
            manager.write({users_field: [(4, uid) for uid in admins.ids]})
            construction_manager = env.ref(
                _CONSTRUCTION_MANAGER_XMLID, raise_if_not_found=False)
            if construction_manager:
                construction_manager.write(
                    {users_field: [(4, uid) for uid in admins.ids]})
