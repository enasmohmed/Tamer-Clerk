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
    path("meeting-points-unlock/", meeting_points_unlock, name="meeting_points_unlock"),
    # dashboard/urls.py
    path('quarter-ajax/', UploadExcelViewRoche.as_view(), name='quarter_ajax'),



    path('meeting-points/', MeetingPointListCreateView.as_view(), name='meeting_points'),
    path('toggle-meeting-point/<int:pk>/', ToggleMeetingPointView.as_view(), name='toggle_meeting_point'),

    path('done-meeting-point/<int:pk>/', DoneMeetingPointView.as_view(), name='done_meeting_point'),


]