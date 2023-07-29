from odoo import models, fields


class StockMove(models.Model):

    _inherit = "stock.move"

    create_from_move = fields.Boolean(
        string='Create From Move', store=False,
        readonly=True, default=lambda self: self.env.context.get(
            'create_from_move', False)
    )
