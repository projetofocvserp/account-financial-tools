from odoo import models, api, fields


class StockMove(models.Model):

    _inherit = "stock.move"

    create_from_move = fields.Boolean(
        string='Create From Move', store=False,
        readonly=True, default=lambda self: self.env.context.get(
            'create_from_move', False)
    )

    location_id = fields.Many2one(
        'stock.location', 'Source Location',
        auto_join=True, index=True, required=[(
            'create_from_move', '=', False
        )],
        check_company=True,
        help="Sets a location if you produce at a fixed location. \
            This can be a partner location if you subcontract the\
                manufacturing operations."
    )
    location_dest_id = fields.Many2one(
        'stock.location', 'Destination Location',
        auto_join=True, index=True, required=[(
            'create_from_move', '=', False
        )],
        check_company=True,
        help="Location where the system will stock the finished products."
    )

    def write(self, vals):
        if self.create_from_move:
            print('Estou na stock move')
            print(vals)

        return super().write(vals)

    @api.model
    def create(self, vals_list):
        if self.create_from_move:
            print('Testando')
        return super().create(vals_list)
