from odoo import models, api, fields


class Picking(models.Model):

    _inherit = 'stock.picking'

    create_from_move = fields.Boolean(
        string="Create From Move", store=False, readonly=True
    )

    def _prepare_stock_move_vals(self, line_record) -> dict:
        return {
            "name": line_record.name,
            "product_id": line_record.product_id.id,
            "product_uom_qty": line_record.quantity,
            "product_uom_category_id": line_record.product_uom_category_id,
            "product_uom": line_record.product_uom_id.id,
            "price_unit": line_record.price_unit,
            "company_id": self.env.company.id,
        }

    def _get_line_records(self, ids: list):
        return self.env['account.move.line'].browse(ids)

    @api.model
    def default_get(self, fields_list) -> dict:
        res = super().default_get(fields_list)

        if self.env.context.get('create_from_move', False):
            if not self.move_ids_without_package:
                stock_move_records = []
                line_records = self._get_line_records(
                    self.env.context.get('line_ids', [])
                )

                for line in line_records:
                    stock_move_vals = self._prepare_stock_move_vals(
                        line_record=line
                    )

                    stock_move_obj = self.env['stock.move']\
                        .with_context(create_from_move=True)\
                        .create(stock_move_vals)

                    stock_move_records.append(stock_move_obj.id)

                self.move_ids_without_package = [
                    (6, 0, stock_move_records)]

            res.update({
                'picking_type_id': 5,
                'create_from_move': True
            })

        return res

    def write(self, vals):
        return super().write(vals)

    # TODO: No método create, setar o location_id e o location_dest_id,
    # para todos os stock moves.
