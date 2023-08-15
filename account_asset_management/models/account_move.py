# Copyright 2009-2018 Noviat
# Copyright 2021 Tecnativa - João Marques
# Copyright 2021 Tecnativa - Víctor Martínez
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import Form
from typing import Dict, Any, List, Literal

_logger = logging.getLogger(__name__)

# List of move's fields that can't be modified if move is linked
# with a depreciation line
FIELDS_AFFECTS_ASSET_MOVE = {"journal_id", "date"}
# List of move line's fields that can't be modified if move is linked
# with a depreciation line
FIELDS_AFFECTS_ASSET_MOVE_LINE = {
    "credit",
    "debit",
    "account_id",
    "journal_id",
    "date",
    "asset_profile_id",
    "asset_ids",
}


class AccountMove(models.Model):
    _inherit: str = "account.move"

    asset_count = fields.Integer(compute="_compute_asset_count")

    @staticmethod
    def _quantity_is_valid(quantity: float) -> bool:
        return (quantity % 2) in [0, 1]

    @staticmethod
    def _get_filtered_move_lines(move_line_records) -> Any:
        return move_line_records.filtered(
            lambda line: line.asset_profile_id and not line.tax_line_id
        )

    def _reverse_move_vals(self, default_values, cancel=True) -> Any:
        move_vals = super()._reverse_move_vals(default_values, cancel)
        if move_vals["move_type"] not in ("out_invoice", "out_refund"):

            for line_command in move_vals.get("line_ids", []):
                line_vals = line_command[2]  # (0, 0, {...})
                assets = self.env["account.asset"].browse(
                    line_vals["asset_ids"]
                )

                # We remove the asset if we recognize that we are reversing
                # the asset creation

                if assets:
                    for asset in assets:
                        asset_line: Any = self.env["account.asset.line"]\
                            .search([
                                    ("asset_id", "=", asset.id),
                                    ("type", "=", "create")], limit=1
                                )
                        if asset_line and asset_line.move_id == self:
                            asset.unlink()
                    line_vals.update(asset_profile_id=False, asset_id=False)
        return move_vals

    def _compute_asset_count(self) -> None:
        for rec in self:

            assets: Any = (
                self.env["account.asset.line"]
                .search([("move_id", "=", rec.id)])
                .mapped("asset_id")
            )

            rec.asset_count = len(assets)

    def _prepare_asset_vals(
            self, move_line: Any, quantity: float = 1.0) -> Dict[str, Any]:
        depreciation_base = move_line.balance

        return {
            "name": "{} ({})".format(move_line.name, quantity),
            "code": self.name,
            "profile_id": move_line.asset_profile_id,
            "purchase_value": depreciation_base / quantity,
            "partner_id": move_line.partner_id,
            "date_start": self.date,
            "account_analytic_id": move_line.analytic_account_id,
        }

    @staticmethod
    def _prepare_stock_picking_vals() -> Dict[str, Any]:
        return {
            'picking_type_id': 5,
            'location_id': 17,
            'location_dest_id': 19,
            'move_type': 'direct',
        }

    def _create_product_asset(self, move_line: Any) -> None:
        vals: Dict[str, Any] = self._prepare_asset_vals(
            move_line, quantity=move_line.quantity
        )

        asset_form = Form(
            self.env["account.asset"]
            .with_company(self.company_id)
            .with_context(
                create_asset_from_move_line=True,
                move_id=self.id
            )
        )

        for key, val in vals.items():
            setattr(asset_form, key, val)

        asset: Any = asset_form.save()
        asset.analytic_tag_ids = move_line.analytic_tag_ids

        move_line.with_context(
            allow_asset=True, allow_asset_removal=True
        ).asset_ids = [(4, asset.id, 0)]

    def _create_product_asset_refs(self) -> List[str]:
        return [
            "<a href=# data-oe-model=account.asset data-oe-id=%s>%s</a>"
            % tuple(name_get)
            for name_get in self.line_ids.filtered("asset_profile_id")
            .asset_ids.name_get()
        ]

    def _create_stock_picking_for_move(self) -> None:
        line_ids: Any = self._get_filtered_move_lines(
            self.invoice_line_ids
        ).ids

        stock_picking_object: Any = self.env['stock.picking'].with_context(
            created_from_move=True,
            line_ids=line_ids,
        )

        stock_picking_vals: Dict[str, Any] = self._prepare_stock_picking_vals()

        stock_picking_object.create(stock_picking_vals)

    @api.model
    def create(self, vals_list) -> Any:
        res: Any = super().create(vals_list)

        return res

    def write(self, vals) -> Any:
        if set(vals).intersection(FIELDS_AFFECTS_ASSET_MOVE):
            deprs: Any = (
                self.env["account.asset.line"]
                .sudo()
                .search([
                    ("move_id", "in", self.ids),
                    ("type", "=", "depreciate")
                ])
            )

            if deprs:
                raise UserError(
                    _(
                        "You cannot change an accounting entry "
                        "linked to an asset depreciation line."
                    )
                )
        return super().write(vals)

    def unlink(self) -> Literal[True]:
        # for move in self:
        deprs = self.env["account.asset.line"].search(
            [("move_id", "in", self.ids),
             ("type", "in", ["depreciate", "remove"])]
        )

        if deprs and not self.env.context.get("unlink_from_asset"):
            raise UserError(
                _(
                    "You are not allowed to remove an accounting entry "
                    "linked to an asset."
                    "\nYou should remove such entries from the asset."
                )
            )
        # trigger store function
        deprs.write({"move_id": False})

        return super().unlink()

    def action_post(self) -> None:
        super().action_post()

        for move in self:
            lines_filtered: Any = self._get_filtered_move_lines(move.line_ids)

            if not bool(lines_filtered):
                break

            for move_line in lines_filtered:

                if not move._quantity_is_valid(move_line.quantity):
                    raise ValidationError(_(
                        "Product %s has an invalid "
                        "quantity value. \nPlease check the product "
                        "quantity and fix it."
                    ) % move_line.name)
                elif move_line.quantity == len(move_line.asset_ids):
                    continue

                if not move_line.name:
                    raise UserError(
                        _("Asset name must be set in the label of the line.")
                    )

                for __ in range(int(move_line.quantity)):
                    move._create_product_asset(move_line)

            refs: List[str] = move._create_product_asset_refs()

            if refs:
                message: Any | str = _(
                    "This invoice created the asset(s): %s") % ", ".join(refs)
                move.message_post(body=message)

            # move._create_stock_picking_for_move()

    def button_draft(self) -> None:
        invoices = self.filtered(lambda r: r.is_purchase_document())

        if invoices:
            invoices.line_ids.asset_ids.unlink()

        return super().button_draft()

    def action_view_assets(self):
        assets = (
            self.env["account.asset.line"]
            .search([("move_id", "=", self.id)])
            .mapped("asset_id")
        )

        action = self.env.ref(
            "account_asset_management.account_asset_action")

        action_dict = action.sudo().read()[0]

        if len(assets) == 1:
            res = self.env.ref(
                "account_asset_management.account_asset_view_form", False
            )
            action_dict["views"] = [(res and res.id or False, "form")]
            action_dict["res_id"] = assets.id
        elif assets:
            action_dict["domain"] = [("id", "in", assets.ids)]
        else:
            action_dict = {"type": "ir.actions.act_window_close"}
        return action_dict


class AccountMoveLine(models.Model):
    _inherit: str = "account.move.line"

    asset_profile_id = fields.Many2one(
        comodel_name="account.asset.profile",
        string="Asset Profile",
        compute="_compute_asset_profile",
        store=True,
        readonly=False,
    )
    asset_ids = fields.One2many(
        comodel_name="account.asset",
        inverse_name="account_move_line_id",
        string="Assets",
    )

    @api.depends("account_id", "asset_ids")
    def _compute_asset_profile(self) -> None:
        for rec in self:

            if rec.account_id.asset_profile_id and not rec.asset_ids:
                rec.asset_profile_id = rec.account_id.asset_profile_id
            elif rec.asset_ids:
                rec.asset_profile_id = rec.asset_ids[0].profile_id

    @api.onchange("asset_profile_id")
    def _onchange_asset_profile_id(self) -> None:
        if self.asset_profile_id.account_asset_id:
            self.account_id = self.asset_profile_id.account_asset_id

    @api.model_create_multi
    def create(self, vals_list) -> Any:
        for vals in vals_list:
            move: Any = self.env["account.move"].browse(vals.get("move_id"))

            if not move.is_sale_document():

                if vals.get("asset_ids") and not \
                        self.env.context.get("allow_asset"):
                    raise UserError(
                        _(
                            "You are not allowed to link "
                            "an accounting entry to an asset."
                            "\nYou should generate such entries "
                            "from the asset."
                        )
                    )
        records: Any = super().create(vals_list)

        for record in records:
            record._expand_asset_line()

        return records

    def write(self, vals) -> Literal[True]:
        if set(vals).intersection(FIELDS_AFFECTS_ASSET_MOVE_LINE) and not (
            self.env.context.get("allow_asset_removal")
            and list(vals.keys()) == ["asset_ids"]
        ):
            # Check if at least one asset is linked to a move
            linked_asset = False

            for move_line in self.filtered(
                    lambda r: not r.move_id.is_sale_document()):

                linked_asset: Any = move_line.asset_ids

                if linked_asset:
                    raise UserError(
                        _(
                            "You cannot change an accounting item "
                            "linked to an asset depreciation line."
                        )
                    )

        if (
            self.filtered(lambda r: not r.move_id.is_sale_document())
            and vals.get("asset_ids")
            and not self.env.context.get("allow_asset")
        ):
            raise UserError(
                _(
                    "You are not allowed to link "
                    "an accounting entry to an asset."
                    "\nYou should generate such entries from the asset."
                )
            )
        super().write(vals)

        if "quantity" in vals or "asset_profile_id" in vals:
            for record in self:
                record._expand_asset_line()

        return True

    def _expand_asset_line(self) -> None:
        self.ensure_one()

        if self.asset_profile_id and self.quantity > 1.0:
            profile: Any = self.asset_profile_id

            if profile.asset_product_item:
                aml = self.with_context(check_move_validity=False)

                qty = self.quantity
                name = self.name

                aml.write({"quantity": 1, "name": "{} {}".format(name, 1)})
                aml._onchange_price_subtotal()

                for i in range(1, int(qty)):
                    aml.copy({"name": "{} {}".format(name, i + 1)})

                aml.move_id._onchange_invoice_line_ids()
