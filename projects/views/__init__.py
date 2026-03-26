from .dashboard import index
from .projects import project_create, project_delete, project_detail, project_edit
from .tasks import task_create, task_delete, task_edit, quick_add
from .report import report
from .projects_list import projects_list
from .profile import profile, user_profile
from .admin import admin_panel, admin_user_detail, admin_user_toggle, admin_reset_password, admin_user_delete, admin_tasks
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

from .chat import chat_list, chat_open, chat_room, chat_send, chat_poll, chat_unread, chat_edit, chat_delete, chat_mute, chat_create_group, chat_clear, chat_leave, chat_add_member, chat_forward, chat_search, chat_saved, chat_pin
from .invite import invite_create, invite_landing, invite_list, invite_delete
from .members import project_members, member_add, member_remove, member_role, my_tasks, shared_project_detail
