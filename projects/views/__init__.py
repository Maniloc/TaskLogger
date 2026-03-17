from .dashboard import index
from .projects import project_create, project_delete, project_detail, project_edit
from .tasks import task_create, task_delete, task_edit, quick_add
from .report import report
from .projects_list import projects_list
from .profile import profile
from .admin import admin_panel, admin_user_detail
from .analytics import analytics

__all__ = [
    'index',
    'project_create', 'project_delete', 'project_detail', 'project_edit',
    'task_create', 'task_delete', 'task_edit', 'quick_add',
    'report',
    'projects_list',
    'profile',
    'admin_panel', 'admin_user_detail',
    'analytics',
]
