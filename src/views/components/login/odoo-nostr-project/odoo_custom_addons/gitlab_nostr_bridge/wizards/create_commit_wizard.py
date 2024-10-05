# wizards/create_commit_wizard.py

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import gitlab
import base64
import logging
from bech32 import bech32_decode, convertbits

_logger = logging.getLogger(__name__)

class CreateCommitWizard(models.TransientModel):
    _name = 'gitlab_nostr_bridge.create.commit.wizard'
    _description = 'Create Commit Wizard'

    repository_id = fields.Many2one('gitlab.repository', string='Repository', required=True)
    branch_name = fields.Char(string='Branch Name', required=True, default='main')
    commit_message = fields.Text(string='Commit Message', required=True)
    file_path = fields.Char(string='File Path', required=True)
    file_content = fields.Text(string='File Content', required=True)
    file_upload = fields.Binary(string='Upload File')
    is_new_file = fields.Boolean(string='Is New File', default=True)
    file_exists = fields.Boolean(string='File Exists', compute='_compute_file_exists')
    file_name = fields.Char(string='File Name')

    @api.depends('repository_id', 'branch_name', 'file_path')
    def _compute_file_exists(self):
        for record in self:
            record.file_exists = False
            if record.repository_id and record.branch_name and record.file_path:
                try:
                    gl = record._get_gitlab_client()
                    project = gl.projects.get(record.repository_id.project_id)
                    try:
                        project.files.get(file_path=record.file_path, ref=record.branch_name)
                        record.file_exists = True
                    except gitlab.exceptions.GitlabGetError as e:
                        if e.response_code == 404:
                            record.file_exists = False
                        else:
                            _logger.error(f"GitLab API error: {str(e)}")
                            raise UserError(_("Error checking file existence: %s") % str(e))
                except Exception as e:
                    _logger.error(f"Error in _compute_file_exists: {str(e)}")


    @api.model
    def default_get(self, fields_list):
        defaults = super(CreateCommitWizard, self).default_get(fields_list)
        active_id = self._context.get('active_id')
        if active_id:
            repository = self.env['gitlab.repository'].browse(active_id)
            defaults['repository_id'] = repository.id
        return defaults

    @api.depends('repository_id')
    def _get_branch_selection(self):
        branches = []
        repository_id = self._context.get('default_repository_id')
        if self:
            repository = self.env['gitlab.repository'].browse(repository_id)
            if repository:
                try:
                    gl = self._get_gitlab_client()
                    project = gl.projects.get(repository.project_id)
                    branches = [(branch.name, branch.name) for branch in project.branches.list()]
                except Exception as e:
                    _logger.error(f"Failed to fetch branches for repository {repository.name}: {str(e)}")
        if not branches:
            branches = [('main', 'main')]
        return branches

    @api.onchange('repository_id', 'branch_name', 'file_path')
    def _onchange_file_details(self):
        if self.repository_id and self.branch_name and self.file_path:
            if not self.file_path or '..' in self.file_path:
                return {'warning': {'title': _("Invalid File Path"), 'message': _("Please enter a valid file path.")}}
            
            gl = self._get_gitlab_client()
            project = gl.projects.get(self.repository_id.project_id)
            try:
                file_content = project.files.get(file_path=self.file_path, ref=self.branch_name)
                self.file_content = base64.b64decode(file_content.content).decode('utf-8')
                self.is_new_file = False
            except gitlab.exceptions.GitlabHttpError as e:
                if e.response_code == 404:
                    self.file_content = ''
                    self.is_new_file = True
                else:
                    return {'warning': {'title': _("GitLab Error"), 'message': str(e)}}
            except Exception as e:
                return {'warning': {'title': _("Error"), 'message': str(e)}}

    @api.onchange('file_upload')
    def _onchange_file_upload(self):
        if self.file_upload:
            self.file_content = base64.b64decode(self.file_upload).decode('utf-8')

    """@api.onchange('file_name')
    def _onchange_file_name(self):
        if self.file_name and not self.file_path:
            self.file_path = self.file_name"""

    @api.onchange('repository_id')
    def _onchange_repository_id(self):
        if self.repository_id:
            return {'domain': {'branch_name': []}, 'context': {'default_repository_id': self.repository_id.id}}

    def _get_gitlab_client(self):
        gitlab_url = self.env['ir.config_parameter'].sudo().get_param('gitlab_nostr_bridge.gitlab_url')
        gitlab_token = self.env['ir.config_parameter'].sudo().get_param('gitlab_nostr_bridge.gitlab_private_token')
        if not gitlab_url or not gitlab_token:
            raise UserError(_("GitLab URL or Private Token is not configured. Please check the settings."))
        try:
            return gitlab.Gitlab(gitlab_url, private_token=gitlab_token)
        except Exception as e:
            _logger.error(f"Failed to create GitLab client: {str(e)}")
            raise UserError(_("Failed to connect to GitLab. Please check your settings and network connection."))

    @api.constrains('file_path')
    def _check_file_path(self):
        for record in self:
            if not record.file_path or '..' in record.file_path:
                raise UserError(_("Invalid file path. Please provide a valid path without '..'"))

    def action_create_commit(self):
        self.ensure_one()
        gl = self._get_gitlab_client()
        project = gl.projects.get(self.repository_id.project_id)
        
        action = 'create' if self.is_new_file else 'update'
        
        commit_data = {
            'branch': self.branch_name,
            'commit_message': self.commit_message,
            'actions': [
                {
                    'action': action,
                    'file_path': self.file_path,
                    'content': self.file_content,
                }
            ]
        }
        
        try:
            commit = project.commits.create(commit_data)
        except gitlab.exceptions.GitlabCreateError as e:
            raise UserError(_("Failed to create commit: %s") % str(e))
        
        self.env['gitlab.commit'].create_or_update_from_gitlab(self.repository_id.id, commit)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Success"),
                'message': _("Commit created successfully"),
                'type': 'success',
            }
        }
