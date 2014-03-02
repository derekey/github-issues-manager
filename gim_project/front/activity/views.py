import re


class ActivityViewMixin(object):
    RE_VALIDATE_SCORE = re.compile(r'^\d{14}\.0$')
    partial_template_name = 'front/activity/include_activity.html'

    @classmethod
    def _validate_score(cls, score):
        if score and len(score) == 16 and cls.RE_VALIDATE_SCORE.match(score):
            return score
        return None

    @property
    def activity_args(self):
        if not hasattr(self, '_activity_args'):
            min = self._validate_score(self.request.GET.get('min'))
            max = self._validate_score(self.request.GET.get('max'))
            self._activity_args = {
                'min': min,
                'max': max,
                'withscores': True
            }
        return self._activity_args

    def get_context_data(self, *args, **kwargs):
        context = super(ActivityViewMixin, self).get_context_data(**kwargs)
        context['activity_args'] = self.activity_args
        context['partial_activity'] = bool(self.request.GET.get('partial'))
        return context

    def get_template_names(self):
        if self.request.GET.get('partial'):
            return self.partial_template_name
        return super(ActivityViewMixin, self).get_template_names()
