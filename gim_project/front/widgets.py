from django.forms import TextInput
from django.utils.safestring import mark_safe


class HTML5Input(TextInput):
    """
    Supports any HTML5 input
    http://www.w3schools.com/html/html5_form_input_types.asp
    """
    def __init__(self, attrs=None, input_type='text', **kwargs):
        self.input_type = input_type
        super(HTML5Input, self).__init__(attrs, **kwargs)


class NumberInput(HTML5Input):
    """
    Helper to quickly set a HTML5Input for numbers
    """
    def __init__(self, attrs=None):
        super(NumberInput, self).__init__(attrs, input_type='number')


class EnclosedInput(HTML5Input):
    """
    Widget for bootstrap appended/prepended inputs
    Ex usage:
    """

    def __init__(self, attrs=None, input_type='text', prepend=None, append=None, **kwargs):
        """
        For prepend, append parameters use string like %, $ or html
        """
        self.prepend = prepend
        self.append = append

        self.parent_classes = kwargs.pop('parent_classes', None)
        self.addons_titles = kwargs.pop('addons_titles', {})

        if isinstance(self.parent_classes, basestring):
            self.parent_classes = self.parent_classes.split(',')
        elif isinstance(self.parent_classes, (tuple, list)):
            self.parent_classes = list(self.parent_classes)

        super(EnclosedInput, self).__init__(attrs=attrs, input_type=input_type, **kwargs)

    def enclose_value(self, value, title=None):
        """
        If value doesn't starts with html open sign "<", enclose in add-on tag
        """
        if value.startswith("<"):
            return value
        if value.startswith("icon-"):
            value = '<i class="%s"></i>' % value
        if title:
            title = ' title="%s"' % title
        return '<span class="add-on"%s>%s</span>' % (title, value)

    def render(self, name, value, attrs=None):
        output = super(EnclosedInput, self).render(name, value, attrs)
        div_classes = []

        if self.prepend:
            div_classes.append('input-prepend')
            self.prepend = self.enclose_value(self.prepend, self.addons_titles.get('prepend'))
            output = ''.join((self.prepend, output))

        if self.append:
            div_classes.append('input-append')
            self.append = self.enclose_value(self.append, self.addons_titles.get('append'))
            output = ''.join((output, self.append))

        if self.parent_classes:
            div_classes.extend(self.parent_classes)

        return mark_safe(
            '<div class="%s">%s</div>' % (' '.join(div_classes), output))
