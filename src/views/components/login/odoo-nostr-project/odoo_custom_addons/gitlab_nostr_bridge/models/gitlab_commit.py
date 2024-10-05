from odoo import models, fields, api
from dateutil import parser
from datetime import datetime, timezone
from nostr.event import Event
import time
import asyncio
import json
import logging

_logger = logging.getLogger(__name__)

class GitlabCommit(models.Model):
    _name = 'gitlab.commit'
    _description = 'GitLab Commit'

    name = fields.Char(string='Commit Hash', required=True)
    message = fields.Text(string='Commit Message')
    author = fields.Char(string='Author')
    date = fields.Datetime(string='Commit Date')
    repository_id = fields.Many2one('gitlab.repository', string='Repository', required=True)
    branch_ids = fields.Many2many('gitlab.branch', string='Branches')

    @api.model
    def create_or_update_from_gitlab(self, repository_id, gitlab_commit):
        existing_commit = self.search([('name', '=', gitlab_commit.id), ('repository_id', '=', repository_id)])
        commit_date = self._convert_to_naive_datetime(gitlab_commit.committed_date)
        if existing_commit:
            return existing_commit.write({
                'message': gitlab_commit.message,
                'author': gitlab_commit.author_name,
                'date': commit_date,
            })
        else:
            return self.create({
                'name': gitlab_commit.id,
                'message': gitlab_commit.message,
                'author': gitlab_commit.author_name,
                'date': commit_date,
                'repository_id': repository_id,
            })

    def _create_and_publish_nostr_event(self, commit):
        user = self.env.user
        if not user.nostr_private_key:
            _logger.error("Nostr private key is not set for the current user.")
            return

        try:
            from nostr.key import PrivateKey
            private_key = PrivateKey.from_nsec(user.nostr_private_key)
            pub_key = private_key.public_key.hex()

            event = Event(
                public_key=pub_key,
                created_at=int(time.time()),
                kind=1,
                tags=[],
                content=f"New commit in repository {commit.repository_id.name}: {commit.message}"
            )
            private_key.sign_event(event)

            relay_urls = self.env['ir.config_parameter'].sudo().get_param('nostr_bridge.relay_urls', '').split(',')
            relay_urls = [url.strip() for url in relay_urls if url.strip()]

            if not relay_urls:
                _logger.error("No Nostr relay URLs configured.")
                return

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            results = loop.run_until_complete(self._publish_to_relays(relay_urls, event))

            successes = [result for result in results if result['success']]
            if successes:
                _logger.info(f"Successfully published Nostr event for commit {commit.name} to {len(successes)} relays.")
            else:
                _logger.error(f"Failed to publish Nostr event for commit {commit.name} to any relay.")

        except Exception as e:
            _logger.error(f"Error creating and publishing Nostr event: {str(e)}")

    async def _publish_to_relays(self, relay_urls, event):
        import websockets

        async def publish_to_relay(url, event):
            try:
                async with websockets.connect(url.strip(), ping_interval=None) as websocket:
                    message = event.to_message()
                    await websocket.send(message)
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    return {'success': True, 'url': url, 'response': response}
            except Exception as e:
                return {'success': False, 'url': url, 'error': str(e)}

        tasks = [publish_to_relay(url, event) for url in relay_urls]
        return await asyncio.gather(*tasks)

    def _convert_to_naive_datetime(self, date_string):
        dt = parser.parse(date_string)
        return dt.replace(tzinfo=None)
