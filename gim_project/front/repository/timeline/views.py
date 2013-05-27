from ..views import BaseRepositoryView


class TimelineView(BaseRepositoryView):
    name = 'Timeline'
    url_name = 'timeline'
    template_name = 'front/repository/timeline/base.html'
