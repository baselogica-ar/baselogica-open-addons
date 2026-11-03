# Copyright 2026 Base Lógica (baselogica.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from . import models


def post_init_hook(env):
    """The native lock of confirmed orders, for everyone, like the Settings option
    ("Lock Confirmed Sales"): unlocking belongs to the Sales administrator. On
    uninstall, the option stays as it is."""
    env.ref("base.group_user").sudo()._apply_group(
        env.ref("sale.group_auto_done_setting")
    )
