import logging
from odoo.exceptions import UserError
from odoo import _, api, fields, models
import gitlab
import requests

_logger = logging.getLogger(__name__)

class GitlabRepository(models.Model):
    _name = 'gitlab.repository'
    _description = 'GitLab Repository'

    name = fields.Char(string='Repository Name', required=True)
    gitlab_id = fields.Integer(string='GitLab Repository ID', required=True)
    url = fields.Char(string='GitLab URL', required=True)
    project_id = fields.Integer(string='GitLab Project ID', required=True)
    branch_ids = fields.One2many('gitlab.branch', 'repository_id', string='Branches')
    commit_ids = fields.One2many('gitlab.commit', 'repository_id', string='Commits')

    def action_create_commit(self):
        return {
            'name': 'Create Commit',
            'type': 'ir.actions.act_window',
            'res_model': 'gitlab_nostr_bridge.create.commit.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    @api.model
    def sync_all_repositories(self):
        repositories = self.search([])
        for repo in repositories:
            repo.sync_with_gitlab()

    def sync_with_gitlab(self):
        self.ensure_one()
        gitlab_url = self.env['ir.config_parameter'].sudo().get_param('gitlab_nostr_bridge.gitlab_url')
        gitlab_token = self.env['ir.config_parameter'].sudo().get_param('gitlab_nostr_bridge.gitlab_private_token')

        if not gitlab_url or not gitlab_token:
            raise UserError(_("GitLab URL or Private Token is not configured. Please check the settings."))

        try:
            gl = gitlab.Gitlab(gitlab_url, private_token=gitlab_token, timeout=30)
            gl.auth()
            project = gl.projects.get(self.project_id)
            
            # Sync branches
            for branch in project.branches.list():
                self.env['gitlab.branch'].create_or_update_from_gitlab(self.id, branch)
            
            # Sync commits
            for commit in project.commits.list():
                self.env['gitlab.commit'].create_or_update_from_gitlab(self.id, commit)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Sync Successful"),
                    'message': _("Repository synced successfully with GitLab."),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            _logger.error(f"Failed to sync with GitLab: {str(e)}")
            raise UserError(_("Failed to sync with GitLab: %s") % str(e))

    @api.model
    def create(self, vals):
        repo = super(GitlabRepository, self).create(vals)
        gitlab_url = self.env['ir.config_parameter'].sudo().get_param('gitlab_nostr_bridge.gitlab_url')
        gitlab_token = self.env['ir.config_parameter'].sudo().get_param('gitlab_nostr_bridge.gitlab_private_token')

        if not gitlab_url or not gitlab_token:
            raise UserError(_("GitLab URL or Private Token is not configured. Please check the settings."))

        _logger.info(f"Attempting to connect to GitLab at {gitlab_url}")

        try:
            gl = gitlab.Gitlab(gitlab_url, private_token=gitlab_token, timeout=10)
            gl.auth()
            _logger.info("Successfully authenticated with GitLab")
        except gitlab.exceptions.GitlabAuthenticationError:
            _logger.error("GitLab authentication failed")
            raise UserError(_("Failed to authenticate with GitLab. Please check your GitLab private token."))
        except requests.exceptions.RequestException as e:
            _logger.error(f"Failed to connect to GitLab: {str(e)}")
            raise UserError(_("Failed to connect to GitLab. Please check the GitLab URL and your network connection."))
        except Exception as e:
            _logger.error(f"Unexpected error when connecting to GitLab: {str(e)}")
            raise UserError(_("An unexpected error occurred: %s") % str(e))

        try:
            project = gl.projects.get(repo.project_id)
            _logger.info(f"Successfully retrieved GitLab project: {project.name}")
        except gitlab.exceptions.GitlabGetError:
            _logger.info(f"Project not found. Attempting to create new project: {repo.name}")
            try:
                project = gl.projects.create({'name': repo.name})
                repo.write({'project_id': project.id})
                _logger.info(f"Successfully created GitLab project: {project.name}")
            except gitlab.exceptions.GitlabCreateError as e:
                _logger.error(f"Failed to create GitLab project: {str(e)}")
                raise UserError(_("Failed to create GitLab project. Error: %s") % str(e))

        return repo
