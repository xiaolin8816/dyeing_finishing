app_name = "dyeing_finishing"
app_title = "印染整理"
app_publisher = "Xiaolin Hang"
app_description = "印染与后整理业务管理"
app_email = "674199886@qq.com"
app_license = "mit"
# APP图标
app_logo_url = "/assets/dyeing_finishing/images/dyeing_finishing-logo.svg"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "dyeing_finishing",
# 		"logo": "/assets/dyeing_finishing/logo.png",
# 		"title": "dyeing_finishing",
# 		"route": "/dyeing_finishing",
# 		"has_permission": "dyeing_finishing.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = "/assets/dyeing_finishing/css/dyeing_finishing.css"
# app_include_js = "/assets/dyeing_finishing/js/dyeing_finishing.js"

# include js, css files in header of web template
# web_include_css = "/assets/dyeing_finishing/css/dyeing_finishing.css"
# web_include_js = "/assets/dyeing_finishing/js/dyeing_finishing.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "dyeing_finishing/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "dyeing_finishing/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "dyeing_finishing.utils.jinja_methods",
# 	"filters": "dyeing_finishing.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "dyeing_finishing.install.before_install"
# after_install = "dyeing_finishing.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "dyeing_finishing.uninstall.before_uninstall"
# after_uninstall = "dyeing_finishing.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "dyeing_finishing.utils.before_app_install"
# after_app_install = "dyeing_finishing.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "dyeing_finishing.utils.before_app_uninstall"
# after_app_uninstall = "dyeing_finishing.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "dyeing_finishing.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "dyeing_finishing.notifications.get_notification_config"

# Awesome Bar
# -----------
# Extra search results: list of dicts with label, description, route, index.
# route: ["List", "ToDo"], "/desk/docs/some/page", or "https://example.com"
# awesomebar_search = ["dyeing_finishing.search.awesomebar_results"]

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"dyeing_finishing.tasks.all"
# 	],
# 	"daily": [
# 		"dyeing_finishing.tasks.daily"
# 	],
# 	"hourly": [
# 		"dyeing_finishing.tasks.hourly"
# 	],
# 	"weekly": [
# 		"dyeing_finishing.tasks.weekly"
# 	],
# 	"monthly": [
# 		"dyeing_finishing.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "dyeing_finishing.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "dyeing_finishing.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "dyeing_finishing.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "dyeing_finishing.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["dyeing_finishing.utils.before_request"]
# after_request = ["dyeing_finishing.utils.after_request"]

# Job Events
# ----------
# before_job = ["dyeing_finishing.utils.before_job"]
# after_job = ["dyeing_finishing.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"dyeing_finishing.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

# 物料列表视图
doctype_list_js = {"Item": "public/js/item_list.js"}

# 销售订单印染扩展字段与显示名称
fixtures = [
    {"dt": "Custom Field", "filters": [["module", "=", "dyeing_finishing"]]},
    {"dt": "Property Setter", "filters": [["module", "=", "dyeing_finishing"]]},
]

# 销售订单客户订单号同步
doctype_js = {
    "Sales Order": "public/js/sales_order.js",
}
doc_events = {
    "Sales Order": {
        "validate": "dyeing_finishing.dyeing_finishing.dyeing_finishing.sales_order.validate",
    },
}
