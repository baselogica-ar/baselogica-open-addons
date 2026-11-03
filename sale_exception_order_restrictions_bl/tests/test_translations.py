# Copyright 2026 Base Lógica (baselogica.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import re

from odoo.tests import TransactionCase, tagged
from odoo.tools.translate import TranslationModuleReader

MODULE = "sale_exception_order_restrictions_bl"


@tagged("post_install", "-at_install")
class TestTranslations(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Spanish of the companies this module is for: es_AR and es_419 load
        # i18n/es_419.po (odoo/tools/translate.py).
        cls.env["res.lang"]._activate_lang("es_419")
        cls.env["ir.module.module"]._load_module_terms(
            [MODULE], ["es_419"], overwrite=True
        )

    def test_module_name(self):
        """The name of the module, in English in the code and in Spanish on the
        screen."""
        module = self.env.ref(f"base.module_{MODULE}")
        self.assertEqual(
            module.with_context(lang="en_US").shortdesc,
            "Sale Exception Order Restrictions",
        )
        self.assertEqual(
            module.with_context(lang="es_419").shortdesc,
            "Restricciones del pedido con las excepciones de venta",
        )

    def test_every_text_in_spanish(self):
        """Each screen text of the module has its Spanish in i18n/es_419.po. The
        description (README.rst) is not translated, and what has no lowercase letters
        (an acronym, a number) is not either: Odoo does not store a translation equal
        to the original."""
        reader = TranslationModuleReader(self.env.cr, modules=[MODULE], lang="es_419")
        missing = sorted(
            {
                source
                for _module, _type, name, _res_id, source, value, _comments in reader
                if not value
                and name != "ir.module.module,description"
                and re.search("[a-z]", source)
            }
        )
        self.assertFalse(missing, f"Without Spanish in i18n/es_419.po: {missing}")
