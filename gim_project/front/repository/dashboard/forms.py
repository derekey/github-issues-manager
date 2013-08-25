import re

from django import forms
from django.core import validators

from core.models import LabelType, LABELTYPE_EDITMODE, Label


class LabelTypeEditForm(forms.ModelForm):

    format_string = forms.CharField(
                        required=False,
                        label=u'Format',
                        help_text=u'Write the format for labels to match this group, inserting the strings <strong>{label}</strong> for the part to display, and optionnally <strong>{order}</strong> if your labels include a number to order them',
                    )
    format_string_validators = [
        validators.RegexValidator(
            re.compile('\{label\}'),
            'Must contain a "{label}" part',
            'no-label'
        ),
    ]

    labels_list = forms.CharField(
                    required=False,
                    label=u'Labels',
                    help_text=u'Choose which labels to add in this group. You can also add new ones (use a coma to separate them)',
                )

    class Meta:
        model = LabelType
        fields = ('name', 'edit_mode', 'regex', 'format_string', 'labels_list', )
        widgets = {
            'regex': forms.TextInput,
        }

    def __init__(self, *args, **kwargs):

        self.repository = kwargs.pop('repository')

        if kwargs.get('instance') and kwargs['instance'].edit_mode != LABELTYPE_EDITMODE.REGEX and kwargs['instance'].edit_details:
            if 'initial' not in kwargs:
                kwargs['initial'] = {}
            if kwargs['instance'].edit_mode == LABELTYPE_EDITMODE.FORMAT:
                kwargs['initial']['format_string'] = kwargs['instance'].edit_details.get('format_string', '')
            elif kwargs['instance'].edit_mode == LABELTYPE_EDITMODE.LIST:
                kwargs['initial']['labels_list'] = kwargs['instance'].edit_details.get('labels_list', '')

        super(LabelTypeEditForm, self).__init__(*args, **kwargs)

        self.fields['name'].widget.attrs['placeholder'] = 'Choose a name for this group'

        self.fields['regex'].required = False  # will be tested depending on the edit_mode

        self.fields['edit_mode'].widget.attrs['class'] = 'uniform'
        self.fields['edit_mode'].help_text = 'Changing mode don\'t keep your configuration, except when changing to "Regular Expression" (each mode convert its configuration to a regular expression)'

    def _clean_fields(self):
        """
        First check the edit_mode then set required flag, and validators, for
        the edit field corresponding to the chosen edit_mode
        """
        self.edit_mode_value = None

        try:
            # get the value of the edit_mode field
            edit_mode_field = self.fields['edit_mode']
            self.edit_mode_value = edit_mode_field.widget.value_from_datadict(
                            self.data, self.files, self.add_prefix('edit_mode'))
            self.edit_mode_value = edit_mode_field.clean(self.edit_mode_value)

            # adapt required attribute and validators of other fields
            if self.edit_mode_value == LABELTYPE_EDITMODE.REGEX:
                self.fields['regex'].required = True

            elif self.edit_mode_value == LABELTYPE_EDITMODE.FORMAT:
                self.fields['format_string'].required = True
                self.fields['format_string'].validators = self.format_string_validators

            elif self.edit_mode_value == LABELTYPE_EDITMODE.LIST:
                self.fields['labels_list'].required = True
        except:
            pass

        # then finally launch the real clean_field process
        super(LabelTypeEditForm, self)._clean_fields()

    def clean(self):
        """
        Create final regex based on input values for other modes
        """
        data = self.cleaned_data

        if self.edit_mode_value == LABELTYPE_EDITMODE.FORMAT and data.get('format_string'):
            data['regex'] = '^%s$' % re.escape(data['format_string'])\
                                .replace('\\{label\\}', '(?P<label>.+)', 1) \
                                .replace('\\{order\\}', '(?P<order>\d+)', 1)

        if self.edit_mode_value == LABELTYPE_EDITMODE.LIST and data.get('labels_list'):
            data['regex'] = '^(?P<label>%s)$' % u'|'.join(
                            map(re.escape, data['labels_list'].split(u',')))

        return data

    def save(self, *args, **kwargs):
        """
        Reset the edit_details json field that keep edit
        """
        self.instance.repository = self.repository
        self.instance.edit_details = {}

        if self.instance.edit_mode == LABELTYPE_EDITMODE.FORMAT:
            self.instance.edit_details = {'format_string': self.cleaned_data['format_string']}

        elif self.instance.edit_mode == LABELTYPE_EDITMODE.LIST:
            self.instance.edit_details = {'labels_list': self.cleaned_data['labels_list']}

        return super(LabelTypeEditForm, self).save(*args, **kwargs)


class LabelEditForm(forms.ModelForm):
    color_validator = validators.RegexValidator(
            re.compile('^[0-9a-f]{6}$', flags=re.IGNORECASE),
            'Must be a valid hex color (without the #)',
            'invalid-color'
        )

    class Meta:
        model = Label
        fields = ('name', 'color', )

    def __init__(self, *args, **kwargs):
        self.repository = kwargs.pop('repository')

        super(LabelEditForm, self).__init__(*args, **kwargs)

        self.fields['color'].validators = [self.color_validator]

    def save(self, *args, **kwargs):
        """
        Reset the edit_details json field that keep edit
        """
        self.instance.repository = self.repository

        return super(LabelEditForm, self).save(*args, **kwargs)
