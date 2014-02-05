import re


class ActivityMixin(object):
    RE_VALIDATE_SCORE = re.compile(r'^\d{14}\.0$')
    partial_template_name = 'front/activity/include_activity.html'

    @classmethod
    def _validate_score(cls, score):
        if score and len(score) == 16 and cls.RE_VALIDATE_SCORE.match(score):
            return score
        return None

    @property
    def activity_arguments(self):
        min = self._validate_score(self.request.GET.get('min'))
        max = self._validate_score(self.request.GET.get('max'))
        return {
            'min': min,
            'max': max,
            'withscores': True
        }

    def get_template_names(self):
        if self.request.GET.get('partial'):
            return self.partial_template_name
        return super(ActivityMixin, self).get_template_names()
