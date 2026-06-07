from django.urls import path
from . import views
from .views import (
    UploadExcelViewRoche,
    MeetingPointListCreateView,
    ToggleMeetingPointView,
    DoneMeetingPointView,
    meeting_points_unlock,
)

app_name = "dashboard"

urlpatterns = [
    path("", UploadExcelViewRoche.as_view(), name="upload_excel"),
    path("portal/", views.pmo_portal_login_view, name="pmo_portal_login"),
    path("portal/logout/", views.pmo_portal_logout_view, name="pmo_portal_logout"),
    path("meeting-points-unlock/", meeting_points_unlock, name="meeting_points_unlock"),
    # dashboard/urls.py
    path('quarter-ajax/', UploadExcelViewRoche.as_view(), name='quarter_ajax'),
    path("project-portfolio/add-project/", views.project_portfolio_add_project, name="project_portfolio_add_project"),
    path("project-portfolio/approve/", views.project_portfolio_approve, name="project_portfolio_approve"),
    path(
        "project-portfolio/approval-deadline/",
        views.project_portfolio_approval_set_deadline,
        name="project_portfolio_approval_set_deadline",
    ),
    path("project-portfolio/update/", views.project_portfolio_update_project, name="project_portfolio_update_project"),
    path("projects-tab/save-tasks/", views.projects_tab_save_tasks, name="projects_tab_save_tasks"),
    path("projects-tab/add-project/", views.projects_tab_add_project, name="projects_tab_add_project"),
    path("projects-tab/update-project/", views.projects_tab_update_project, name="projects_tab_update_project"),



    path('meeting-points/', MeetingPointListCreateView.as_view(), name='meeting_points'),
    path('toggle-meeting-point/<int:pk>/', ToggleMeetingPointView.as_view(), name='toggle_meeting_point'),

    path('done-meeting-point/<int:pk>/', DoneMeetingPointView.as_view(), name='done_meeting_point'),


]