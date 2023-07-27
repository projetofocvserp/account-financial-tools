from odoo import models, api
from odoo.tests.common import Form


class Picking(models.Model):

    _inherit = 'stock.picking'

    def _prepare_stock_move_vals(self, line_record) -> dict:
        return {
            "name": line_record.name,
            "product_id": line_record.product_id.id,
            "product_uom_category_id": line_record.product_uom_category_id,
            "product_uom": line_record.product_uom_id.id,
            "price_unit": line_record.price_unit,
            "location_id": self.location_id,
            "location_dest_id": self.location_dest_id,
        }

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        res.update({
            'picking_type_id': 5,
        })
        return res

    # @api.onchange('location_id')
    # def _onchange_location_id(self):
