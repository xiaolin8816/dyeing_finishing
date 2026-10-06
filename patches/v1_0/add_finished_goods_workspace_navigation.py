from dyeing_finishing.patches.v1_0.configure_dyeing_workspace_sidebar import execute as sync_sidebar
from dyeing_finishing.patches.v1_0.delete_child_workspace_desktop_icons import execute as clean_desktop_icons
from dyeing_finishing.patches.v1_0.sync_dyeing_home_workspace import execute as sync_home


def execute():
	sync_home()
	sync_sidebar()
	clean_desktop_icons()
