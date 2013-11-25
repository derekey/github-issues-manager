from django.utils.html import escape


class Renderer(object):
    USER_HTML_TEMPLATE = '<strong><img class="avatar-small img-circle" src="%(avatar_url)s">%(username)s</strong>'
    STRONG = '<strong>%s</strong>'

    def __init__(self, event):
        self.event = event

    def helper_render_user(self, user, mode):
        if mode == 'text':
            return user['username']
        else:
            return self.USER_HTML_TEMPLATE % user

    def helper_strong(self, value, mode, quote_if_text=True):
        if mode == 'text':
            return '"%s"' % value if quote_if_text else value
        else:
            return self.STRONG % escape(value)


class IssueRenderer(Renderer):

    def render_title(self, part, mode):
        title = 'Title is now "%(title)s"'
        params = {'title': self.helper_strong(part.new, mode, quote_if_text=False)}
        return title % params

    def render_state(self, part, mode):
        new, old = part.new_value, part.old_value

        title = 'Reopened' if new['state'] == 'open' else 'Closed'

        if 'by' in new:
            title += ' by %(by)s'
            params = {'by': self.helper_render_user(new['by'], mode)}
            title = title % params

        return title

    def render_mergeable(self, part, mode):
        return 'Now mergeable' if part.new_value else 'Not mergeable anymore'

    def render_merged(self, part, mode):
        new, old = part.new_value, part.old_value

        title = 'Merged' if new['state'] == 'open' else 'Unmerged ?!?'

        if 'by' in new:
            title += ' by %(by)s'
            params = {'by': self.helper_render_user(new['by'], mode)}
            title = title % params

        return title

    def render_assignee(self, part, mode):
        new, old = part.new_value, part.old_value

        if new and old:
            title = 'Assigned to %(new_assignee)s (previously %(old_assignee)s)'
        elif new:
            title = 'Assigned to %(new_assignee)s'
        else:
            title = '%(unassigned)s (previously assigned to %(old_assignee)s)'

        params = {'unassigned': self.helper_strong('Unassigned', mode, quote_if_text=False)}
        if new:
            params['new_assignee'] = self.helper_render_user(new['username'], mode)
        if old:
            params['old_assignee'] = self.helper_render_user(old['username'], mode)

        return title % params

    def render_milestone(self, part, mode):
        new, old = part.new_value, part.old_value

        if new and old:
            title = 'Milestone set to "%(new_milestone)s" (previously "%(old_milestone)s")'
        elif new:
            title = 'Milestone set to "%(new_milestone)s"'
        else:
            title = 'Milestone %(removed)s (previously set to "%(old_milestone)s")'

        params = {'removed': self.helper_strong('removed', mode, quote_if_text=False)}
        if new:
            params['new_milestone'] = self.helper_strong(new['title'], mode, quote_if_text=False)
        if old:
            params['old_milestone'] = self.helper_strong(old['title'], mode, quote_if_text=False)

        return title % params

    def helper_render_labels(self, labels, mode):
        if mode == 'text':
            return ', '.join(['"%s"' % l['name'] for l in labels])
        else:
            return '<ul class="unstyled labels">%s</ul>' % (''.join([
                '<li style="border-bottom-color: #%(color)s;">%(name)s</li>' % {
                    'name': escape(l['name']),
                    'color': l['color']
                } for l in labels
            ]))

    def render_labels(self, part, mode):
        new, old = part.new_value, part.old_value
        if new['labels']:
            title = 'Added label%(plural)s: %(labels)s'
            labels = new['labels']
        else:
            title = 'Removed label%(plural)s: %(labels)s'
            labels = old['labels']

        params = {
            'labels': self.helper_render_labels(labels, mode),
            'plural': 's' if len(labels) > 1 else '',
        }

        return title % params

    def render_label_type(self, part, mode):
        new, old = part.new_value, part.old_value

        params = {'type': self.helper_strong(new['label_type']['name'], mode, quote_if_text=False)}

        if new['labels'] and old['labels']:
            title = '%(type)s was set to %(added)s (previously %(removed)s)'
        elif new['labels']:
            title = '%(type)s was set to %(added)s'
        else:
            title = '%(type)s was unset (previously %(removed)s)'

        if new['labels']:
            params['added'] = self.helper_render_labels(new['labels'], mode)
        if old['labels']:
            params['removed'] = self.helper_render_labels(old['labels'], mode)

        return title % params
