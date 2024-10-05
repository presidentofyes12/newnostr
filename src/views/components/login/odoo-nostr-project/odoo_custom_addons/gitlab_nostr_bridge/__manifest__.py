{
    'name': 'GitLab-Nostr Bridge',
    'version': '1.2.0',
    'category': 'Productivity/Integrations',
    'summary': 'Integrate GitLab repositories with Nostr events',
    'sequence': 1,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',
    'description': """
GitLab-Nostr Bridge
===================
This module integrates GitLab repositories with Nostr events, allowing you to:
* Sync GitLab repositories, branches, and commits with Odoo
* Generate Nostr events for GitLab activities
* Publish Nostr events to configured relays
* Manage Nostr keys for users
* Configure GitLab and Nostr settings

Key Features:
-------------
* GitLab repository synchronization
* Nostr event generation and publication
* Multiple publishing strategies (original, alternative, and new relay management)
* User-specific Nostr key management
* Configurable GitLab and Nostr settings
* Automated relay testing and management
    """,
    'depends': [
        'base',
        'mail',
        'web',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/gitlab_repository_views.xml',
        'views/gitlab_branch_views.xml',
        'views/gitlab_commit_views.xml',
        'views/nostr_event_views.xml',
        'views/res_users_views.xml',
        'views/res_config_settings_views.xml',
        'data/gitlab_nostr_bridge_data.xml',
        'data/ir_cron_data.xml',
    ],
    'demo': [],
    'css': [
        'static/src/css/gitlab_nostr_bridge.css',
    ],
    'images': [
        'static/description/icon.png',
    ],
    'assets': {
        'web.assets_backend': [
            'gitlab_nostr_bridge/static/src/js/gitlab_nostr_bridge.js',
        ],
    },
    'external_dependencies': {
        'python': [
            'gitlab',
            'nostr',
            'requests',
            'websockets',
        ],
    },
    'application': True,
    'installable': True,
    'auto_install': False,
    'uninstall_hook': 'uninstall_hook',
}
