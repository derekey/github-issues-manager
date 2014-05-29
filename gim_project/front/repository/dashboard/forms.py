import json
import re

from django import forms
from django.core import validators

from core.models import (LabelType, LABELTYPE_EDITMODE, Label,
                         GITHUB_STATUS_CHOICES, Milestone)

from front.widgets import EnclosedInput
from front.mixins.forms import LinkedToRepositoryFormMixin, LinkedToUserFormMixin


class LabelTypeEditForm(LinkedToRepositoryFormMixin):

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

        self.fields['labels_list'].widget.attrs.update({
            'data-labels': self.get_labels_json(),
        })

    def get_labels_json(self):
        data = {l.name: {'name': l.name, 'color': l.color}
                for l in self.repository.labels.all()}
        return json.dumps(data)

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
        data = super(LabelTypeEditForm, self).clean()

        if self.edit_mode_value == LABELTYPE_EDITMODE.FORMAT and data.get('format_string'):
            data['regex'] = LabelType.regex_from_format(data['format_string'])

        if self.edit_mode_value == LABELTYPE_EDITMODE.LIST and data.get('labels_list'):
            data['regex'] = LabelType.regex_from_list(data['labels_list'])

        return data

    def save(self, *args, **kwargs):
        """
        Reset the edit_details json field that keep edit
        """
        self.instance.edit_details = {}

        if self.instance.edit_mode == LABELTYPE_EDITMODE.FORMAT:
            self.instance.edit_details = {'format_string': self.cleaned_data['format_string']}

        elif self.instance.edit_mode == LABELTYPE_EDITMODE.LIST:
            labels = ','.join(sorted(self.cleaned_data['labels_list'].split(','), key=unicode.lower))
            self.instance.edit_details = {'labels_list': labels}

        return super(LabelTypeEditForm, self).save(*args, **kwargs)


class LabelTypePreviewForm(LabelTypeEditForm):
    def clean(self):
        # do not do any unicity check
        cleaned_data = super(LabelTypePreviewForm, self).clean()
        self._validate_unique = False
        return cleaned_data


class LabelEditForm(LinkedToRepositoryFormMixin):
    color_validator = validators.RegexValidator(
            re.compile('^[0-9a-f]{6}$', flags=re.IGNORECASE),
            'Must be a valid hex color (without the #)',
            'invalid-color'
        )
    label_name_validator = validators.RegexValidator(
            re.compile('^[^\,]+$'),
            'Must not contain a comma (",")',
            'comma-refused'
        )

    class Meta:
        model = Label
        fields = ('name', 'color', )

    def __init__(self, *args, **kwargs):
        super(LabelEditForm, self).__init__(*args, **kwargs)

        if 'name' in self.fields:
            self.fields['name'].validators = [self.label_name_validator]
        self.fields['color'].validators = [self.color_validator]

    def save(self, commit=True):
        """
        Set the github status
        """
        if self.instance.pk:
            self.instance.github_status = GITHUB_STATUS_CHOICES.WAITING_UPDATE
        else:
            self.instance.github_status = GITHUB_STATUS_CHOICES.WAITING_CREATE
        return super(LabelEditForm, self).save(commit)


class TypedLabelEditForm(LabelEditForm):
    class Meta(LabelEditForm.Meta):
        fields = ('label_type', 'order', 'typed_name', 'color', 'name')

    def __init__(self, *args, **kwargs):
        super(TypedLabelEditForm, self).__init__(*args, **kwargs)
        self.fields['typed_name'].validators = [self.label_name_validator]

    def clean(self):
        cleaned_data = super(TypedLabelEditForm, self).clean()

        # cannot change label type
        if self.instance and self.instance.label_type:
            cleaned_data['label_type'] = self.instance.label_type

        label_type = cleaned_data['label_type']

        if label_type.edit_mode == LABELTYPE_EDITMODE.REGEX:
            raise forms.ValidationError('You cannot add a label directly to a "regex" group')

        if label_type.edit_mode == LABELTYPE_EDITMODE.FORMAT:
            # try to get the full label name, will raise ValidationError if problem
            cleaned_data['name'] = label_type.create_from_format(
                cleaned_data['typed_name'],
                cleaned_data.get('order')
            )

        else:  # label_type.edit_mode == LABELTYPE_EDITMODE.LIST:
            cleaned_data['name'] = cleaned_data['typed_name']
            # remember the name if changed to remove it from the list
            if self.instance and self.instance.name != cleaned_data['name']:
                self._old_label_name = self.instance.name

        return cleaned_data

    def save(self, commit=True):
        label = super(TypedLabelEditForm, self).save(commit=commit)

        # manage the list of labels if we have this kind of label-type
        label_type = self.cleaned_data['label_type']
        if label_type.edit_mode == LABELTYPE_EDITMODE.LIST:
            labels_list = label_type.edit_details['labels_list'].split(u',')
            type_updated = False

            # if the label changed its name, we remove the old one from the list
            if hasattr(self, '_old_label_name') and self._old_label_name in labels_list:
                labels_list.remove(self._old_label_name)
                type_updated = True

            # if the label is new in the type list, add it
            if label.name not in labels_list:
                labels_list.append(label.name)
                type_updated = True

            if type_updated:
                label_type.edit_details['labels_list'] = u','.join(labels_list)
                label_type.regex = label_type.regex_from_list(labels_list)
                label_type.save()

        return label


class DueOnWidget(EnclosedInput, forms.DateInput):
    def __init__(self, attrs=None):
        if not attrs:
            attrs = {}
        if 'placeholder' not in attrs:
            attrs['placeholder'] = 'yyyy-mm-dd'
        if 'maxlength' not in attrs:
            attrs['maxlength'] = 10
        super(DueOnWidget, self).__init__(
            attrs=attrs,
            input_type='text',
            prepend='icon-th',
            append='icon-remove',
            addons_titles={
                'prepend': 'Click to open a datepicker',
                'append': 'Click to clear the due-on date',
            },
            format='%Y-%m-%d',
            parent_classes=['date', 'due_on'],
        )


class MilestoneEditForm(LinkedToRepositoryFormMixin):

    open = forms.BooleanField(required=False)

    class Meta:
        model = Milestone
        fields = ('title', 'description', 'due_on', 'open')

    def __init__(self, *args, **kwargs):

        # fill the "open" field
        instance = kwargs.get('instance')
        if not instance or not instance.state or instance.state == 'open':
            if 'initial' not in kwargs:
                kwargs['initial'] = {}
            kwargs['initial']['open'] = True

        super(MilestoneEditForm, self).__init__(*args, **kwargs)
        self.fields['title'].widget = forms.TextInput()
        self.fields['due_on'].widget = DueOnWidget()

    def save(self, commit=True):
        """
        Set the github status, and the state
        """
        self.instance.state = 'open' if self.cleaned_data['open'] else 'closed'
        if self.instance.pk:
            self.instance.github_status = GITHUB_STATUS_CHOICES.WAITING_UPDATE
        else:
            self.instance.github_status = GITHUB_STATUS_CHOICES.WAITING_CREATE
        return super(MilestoneEditForm, self).save(commit)


class MilestoneCreateForm(LinkedToUserFormMixin, MilestoneEditForm):
    user_attribute = 'creator'
