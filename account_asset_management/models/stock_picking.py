from typing import Any, Dict, List, Tuple
from odoo import _, models, api
from traitlets import Bool


class Picking(models.Model):

    _inherit: str = 'stock.picking'

    # def _get_current_move(self) -> Any:
    #     current_move_id = self.env.context.get('active_id')
    #     return self.env['account.move'].browse(
    #         current_move_id
    #     )

    # def _set_account_move_picking_id(self, picking_id: int) -> None:
    #     move_object = self._get_current_move()

    #     move_object.write({
    #         'picking_id': picking_id
    #     })

    def _process_quantity_done(self, move_lines_records) -> None:

        for move_line in move_lines_records:
            move_line.qty_done = move_line.product_uom_qty

    def _get_line_records(self, ids: List[int]) -> Any:
        return self.env['account.move.line'].browse(ids)

    def _prepare_stock_move_vals(self, line_record) -> Dict[str, Any]:
        return {
            "name": line_record.name,
            "product_id": line_record.product_id.id,
            "product_uom_qty": line_record.quantity,
            "product_uom_category_id": line_record.product_uom_category_id,
            "product_uom": line_record.product_uom_id.id,
            "price_unit": line_record.price_unit,
            "company_id": self.env.company.id,
            "location_id": 17,
            "location_dest_id": 19,
        }

    def _compute_stock_move_products(self) -> List[Tuple]:

        stock_move_records: list = []

        line_records = self._get_line_records(
            self.env.context.get('line_ids', [])
        )

        for line in line_records:
            stock_move_vals: Dict[str, Any] = self._prepare_stock_move_vals(
                line_record=line
            )

            stock_move_obj: Any = self.move_ids_without_package\
                .create(stock_move_vals)

            stock_move_records.append(stock_move_obj.id)

        return [(6, 0, stock_move_records)]

    @api.model
    def create(self, vals_list):
        stock_picking = super().create(vals_list)

        if self.env.context.get('created_from_move'):

            stock_move_records: List[Tuple[Any]] = \
                self._compute_stock_move_products()

            stock_picking.move_ids_without_package = stock_move_records

            stock_picking.action_confirm()

            stock_picking.action_assign()

            move_lines_records = stock_picking.\
                move_line_ids_without_package

            if stock_picking.state == 'assigned':
                self._process_quantity_done(move_lines_records)

                # stock_picking.button_validate()

        return stock_picking
