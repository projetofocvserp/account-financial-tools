from typing import Any, Dict, Union, List
from odoo import _, models, api, fields
from odoo.exceptions import ValidationError


class Picking(models.Model):

    _inherit: str = 'stock.picking'

    create_from_move = fields.Boolean(
        string="Create From Move", store=False, readonly=True,
        default=False
    )

    def _prepare_stock_move_vals(self, line_record) -> Dict[str, Any]:
        return {
            "name": line_record.name,
            "product_id": line_record.product_id.id,
            "product_uom_qty": line_record.quantity,
            "product_uom_category_id": line_record.product_uom_category_id,
            "product_uom": line_record.product_uom_id.id,
            "price_unit": line_record.price_unit,
            "company_id": self.env.company.id,
            "location_id": self.location_id.id,
            "location_dest_id": self.location_dest_id.id,
        }

    def _get_line_records(self, ids: List[int]) -> Any:
        return self.env['account.move.line'].browse(ids)

    def _get_current_move(self) -> Any:
        current_move_id = self.env.context.get('active_id')
        return self.env['account.move'].browse(
            current_move_id
        )

    def _set_account_move_picking_id(self, picking_id: int) -> None:
        move_object = self._get_current_move()

        move_object.write({
            'picking_id': picking_id
        })

    def action_open_created_stock_picking(self) -> Dict[str, Any]:
        context = dict(self.env.context)

        if 'create_from_move' in context.keys():

            context.pop('create_from_move')
            context.pop('line_ids')

        return {
            "name": _("Create Transfer"),
            "res_model": "stock.picking",
            "type": "ir.actions.act_window",
            "context": context,
            "view_mode": "form",
            "view_type": "form",
            "view_id": self.env.ref(
                    'stock.view_picking_form').id,
            "target": "current",
            "res_id": self.id or context.get('picking_id'),
        }

    def action_open_stock_picking_form(self) -> Dict[str, Union[str, Any]]:

        return {
            "name": _("Create Transfer"),
            "res_model": "stock.picking",
            "type": "ir.actions.act_window",
            "context": self.env.context,
            "view_mode": "form",
            "view_type": "form",
            "view_id": self.env.ref(
                    'account_asset_management.stock_picking_inherit_view').id,
            "target": "new",
            "res_id": False,
        }

    def action_compute_stock_move_products(self):
        stock_move_records: list = []

        line_records = self._get_line_records(
            self.env.context.get('line_ids', [])
        )

        for line in line_records:
            stock_move_vals: Dict[str, Any] = self._prepare_stock_move_vals(
                line_record=line
            )

            stock_move_obj: Any = self.move_ids_without_package\
                .with_context(
                    create_from_move=True
                ).create(stock_move_vals)

            stock_move_records.append(stock_move_obj.id)

        self.move_ids_without_package: Any = [
            (6, 0, stock_move_records)
        ]

        self._set_account_move_picking_id(self.id)

        return self.action_open_created_stock_picking()

    @api.model
    def default_get(self, fields_list) -> Dict[str, Any]:
        res = super().default_get(fields_list)

        if self.env.context.get('create_from_move', False):
            res.update({
                'move_type': 'direct',
                'create_from_move': True
            })

        return res

    def write(self, vals):
        return super().write(vals)

    # TODO: No método create, setar o location_id e o location_dest_id,
    # para todos os stock moves.

    @api.model
    def create(self, vals_list):
        stock_picking = super().create(vals_list)

        stock_picking.action_confirm()

        context = dict(self.env.context)

        context.pop('create_from_move')
        context.pop('line_ids')

        return stock_picking
