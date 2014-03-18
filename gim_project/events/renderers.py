
from front.diff import HtmlDiff, HtmlDiffWithoutControl

from django.utils.html import escape


class Renderer(object):
    USER_HTML_TEMPLATE = '<strong><img class="avatar-tiny img-circle" src="%(avatar_url)s"> %(username)s</strong>'
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

    def render_event_title(self, mode):
        return '[%(is_update)s] %(type)s #%(number)s "%(title)s"' % {
            'is_update': 'changed' if self.event.is_update else 'created',
            'type': self.event.issue.type.capitalize(),
            'number': self.event.issue.number,
            'title': self.event.issue.title,
        }

    def render_part_title(self, part, mode):
        new, old = part.new_value, part.old_value

        if mode == 'html':
            diff = HtmlDiffWithoutControl.diff(old['title'], new['title'], n=0, css=False)
            return '<span>Title has changed:</span>' + diff

        # part must not be created if no old title
        title = 'Old title was "%(title)s"'
        params = {'title': self.helper_strong(old['title'], mode, quote_if_text=False)}
        return title % params

    def render_part_body(self, part, mode):
        new, old = part.new_value, part.old_value

        if mode == 'html':
            diff = HtmlDiff.diff(old['body'], new['body'], n=2, css=False)
            return '<span>Body has changed:</span>' + diff

        raise NotImplementedError()

    def render_part_state(self, part, mode):
        new, old = part.new_value, part.old_value

        title = 'Reopened' if new['state'] == 'open' else 'Closed'

        if 'by' in new:
            title += ' by %(by)s'
            params = {'by': self.helper_render_user(new['by'], mode)}
            title = title % params

        return title

    def render_part_mergeable(self, part, mode):
        new, old = part.new_value, part.old_value

        mergeable_state = ''
        if 'mergeable_state' in new:
            mergeable_state = (' (reason: %s)' if mode == 'text' else ' (reason: <strong>%s</strong>)') % new['mergeable_state']

        if old:
            title = 'Now mergeable' if new['mergeable'] else 'Not mergeable anymore'
        else:
            title = 'Mergeable' if new['mergeable'] else 'Not mergeable'

        if mode == 'html':
            klass = 'open' if new['mergeable'] else 'closed'
            title = '<strong class="text-%s">%s</strong>' % (klass, title)
        if not new['mergeable']:
            title += mergeable_state

        return title

    def render_part_mergeable_state(self, part, mode):
        new, old = part.new_value, part.old_value

        # let the mergeable part display all if it exists
        if part.event.get_part('mergeable'):
            return None

        klass = 'open' if new['mergeable'] else 'closed'
        title = ('New mergeable status: %s, reason: %s'
                 if mode == 'text'
                else 'New mergeable status: <strong class="text-%s">%s</strong>, reason: <strong>%s</strong>') % (
                        klass,
                        'Mergeable' if new['mergeable'] else 'Not mergeable',
                        new['mergeable_state'])

        if old.get('mergeable_state') != 'unknown':
            title += (' (was %s)' if mode == 'text' else ' (was: <strong>%s</strong>)') % old['mergeable_state']

        return title

    def render_part_merged(self, part, mode):
        new, old = part.new_value, part.old_value

        if old and old['merged'] is False:
            title = 'Merged' if new['merged'] else 'Unmerged ?!?'
        else:
            title = 'Merged' if new['merged'] else 'Not merged'

        if 'by' in new:
            title += ' by %(by)s'
            params = {'by': self.helper_render_user(new['by'], mode)}
            title = title % params

        return title

    def render_part_assignee(self, part, mode):
        new, old = part.new_value, part.old_value

        if new and old:
            title = 'Assigned to %(new_assignee)s (previously %(old_assignee)s)'
        elif new:
            title = 'Assigned to %(new_assignee)s'
        elif old:
            title = '%(unassigned)s (previously assigned to %(old_assignee)s)'
        else:
            title = '%(unassigned)s'

        params = {'unassigned': self.helper_strong('Unassigned', mode, quote_if_text=False)}
        if new:
            params['new_assignee'] = self.helper_render_user(new, mode)
        if old:
            params['old_assignee'] = self.helper_render_user(old, mode)

        return title % params

    def render_part_milestone(self, part, mode):
        new, old = part.new_value, part.old_value

        if new and old:
            title = 'Milestone set to "%(new_milestone)s" (previously "%(old_milestone)s")'
        elif new:
            title = 'Milestone set to "%(new_milestone)s"'
        elif old:
            title = 'Milestone %(removed)s (previously set to "%(old_milestone)s")'
        else:
            title = 'No milestone set'

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
            return '<ul class="unstyled">%s</ul>' % (''.join([
                '<li style="border-bottom-color: #%(color)s;">%(name)s</li>' % {
                    'name': escape(l['name']),
                    'color': l['color']
                } for l in labels
            ]))

    def render_part_labels(self, part, mode):
        new, old = part.new_value, part.old_value
        if new and new.get('labels'):
            title = '<span>Added label%(plural)s:</span> %(labels)s'
            labels = new['labels']
        else:
            title = '<span>Removed label%(plural)s:</span> %(labels)s'
            labels = old['labels']

        params = {
            'labels': self.helper_render_labels(labels, mode),
            'plural': 's' if len(labels) > 1 else '',
        }

        return title % params

    def render_part_label_type(self, part, mode):
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
