from odoo import models, fields, api

class CreateBranchWizard(models.TransientModel):
    _name = 'gitlab_nostr_bridge.create.branch.wizard'
    _description = 'Create Branch Wizard'

    repository_id = fields.Many2one('gitlab.repository', string='Repository', required=True)
    branch_name = fields.Char(string='Branch Name', required=True)
    branch_name = fields.Char(string='Branch Name', required=True)
    source_branch = fields.Char(string='Source Branch', default='master')

    def action_create_branch(self):
        self.ensure_one()
        gl = gitlab.Gitlab(self.repository_id.url, private_token=self.env['ir.config_parameter'].sudo().get_param('gitlab.private_token'))
        project = gl.projects.get(self.repository_id.project_id)
        branch = project.branches.create({'branch': self.branch_name, 'ref': self.source_branch})
        
        self.env['gitlab.branch'].create_or_update_from_gitlab(self.repository_id.id, branch)
        
        self.env['nostr.event'].create_gitlab_event('branch', {
            'project_id': self.repository_id.project_id,
            'branch_name': self.branch_name,
            'action': 'create',
        })
        
        return {'type': 'ir.actions.act_window_close'}
