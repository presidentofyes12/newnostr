# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from nostr.key import PrivateKey
import secrets
import logging

_logger = logging.getLogger(__name__)

class ResUsers(models.Model):
    _inherit = 'res.users'

    nostr_private_key = fields.Char(string="Nostr Private Key", copy=False)
    nostr_public_key = fields.Char(string="Nostr Public Key", compute='_compute_nostr_public_key', store=True)

    @api.depends('nostr_private_key')
    def _compute_nostr_public_key(self):
        for user in self:
            if user.nostr_private_key:
                try:
                    private_key = PrivateKey.from_nsec(user.nostr_private_key)
                    user.nostr_public_key = private_key.public_key.bech32()
                except Exception as e:
                    _logger.error(f"Error computing public key for user {user.id}: {str(e)}")
                    user.nostr_public_key = False
            else:
                user.nostr_public_key = False

    @api.model
    def create(self, vals):
        if 'nostr_private_key' not in vals:
            vals['nostr_private_key'] = self._generate_nostr_key()
        return super(ResUsers, self).create(vals)

    def _generate_nostr_key(self):
        private_key = PrivateKey()
        return private_key.bech32()

    def action_generate_nostr_key(self):
        self.ensure_one()
        private_key = PrivateKey()
        self.nostr_private_key = private_key.bech32()
        self._compute_nostr_public_key()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Nostr Key Generated"),
                'message': _("A new Nostr key pair has been generated."),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_clear_nostr_key(self):
        self.ensure_one()
        self.nostr_private_key = False
        self._compute_nostr_public_key()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Nostr Key Cleared"),
                'message': _("The Nostr key pair has been cleared."),
                'type': 'warning',
                'sticky': False,
            }
        }
