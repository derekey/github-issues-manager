from django.views.generic import FormView
from django.shortcuts import redirect
from django.contrib import messages
from django.core.urlresolvers import reverse_lazy


from .forms import AddRepositoryForm

class AddRepositoryView(FormView):
    form_class = AddRepositoryForm
    success_url = reverse_lazy('front:dashboard:repositories:choose')
    http_method_names = [u'post']

    def get_form_kwargs(self):
        """
        Add the current request's user in the kwargs to use in the form
        """
        kwargs = super(AddRepositoryView, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_invalid(self, form):
        """
        If the form is invalid, return to the list of repositories the user
        can add, with an error message
        """
        messages.error(self.request, form.get_main_error_message())
        return redirect(self.get_success_url())

    def form_valid(self, form):
        messages.success(self.request, 'OK, ready to add %s' % form.cleaned_data['name'])
        return super(AddRepositoryView, self).form_valid(form)
