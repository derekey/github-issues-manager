from ghdiff import GHDiff


class HtmlDiff(GHDiff):
    html_start = '<table class="table table-normal diff">'
    html_end = '</table>'
    html_line = '<tr class="%(css_class)s"><td class="code">%(prefix)s%(content)s</td></tr>'
    html_highlight = '<span class="%(css_class)s">%(content)s</span>'

    css_classes = {
        'control': 'comment',
        'insert': 'added',
        'delete': 'removed',
    }


class HtmlDiffWithoutControl(HtmlDiff):
    @classmethod
    def _make_line(cls, css_class, content, prefix=''):
        if css_class == 'control':
            return ''
        return super(HtmlDiffWithoutControl, cls)._make_line(css_class, content, prefix)
