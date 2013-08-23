from django.conf.urls import patterns, url

from .views import (DashboardView, MilestonesPart, CountersPart, LabelsPart,
                    LabelsEditor, LabelTypeEdit, LabelTypePreview)

urlpatterns = patterns('',
    url(r'^$', DashboardView.as_view(), name=DashboardView.url_name),
    url(r'^milestones/$', MilestonesPart.as_view(), name=MilestonesPart.url_name),
    url(r'^counters/$', CountersPart.as_view(), name=CountersPart.url_name),
    url(r'^labels/$', LabelsPart.as_view(), name=LabelsPart.url_name),

    url(r'^labels/editor/$', LabelsEditor.as_view(), name=LabelsEditor.url_name),
    url(r'^labels/editor/group/(?P<label_type_id>\d+)/edit/$', LabelTypeEdit.as_view(), name=LabelTypeEdit.url_name),
    url(r'^labels/editor/group/preview/$', LabelTypePreview.as_view(), name=LabelTypePreview.url_name),
)
