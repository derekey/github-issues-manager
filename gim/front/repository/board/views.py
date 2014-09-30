from gim.front.repository.views import BaseRepositoryView


class BoardView(BaseRepositoryView):
    name = 'Board'
    url_name = 'board'
    template_name = 'front/repository/board/base.html'
