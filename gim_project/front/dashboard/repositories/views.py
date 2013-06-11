from django.views.generic import FormView, TemplateView
from django.shortcuts import redirect
from django.contrib import messages
from django.core.urlresolvers import reverse_lazy

from subscriptions.models import WaitingSubscription, WAITING_SUBSCRIPTION_STATES
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
        name = form.cleaned_data['name']

        # create the waiting subscription if not exists
        subscription, created = WaitingSubscription.objects.get_or_create(
            user=self.request.user,
            repository_name=name,
            is_admin=form.can_use == 'admin'
        )

        if not created:
            # the subscription already exists, force the state and updated_at
            subscription.state = WAITING_SUBSCRIPTION_STATES.WAITING
            subscription.save()

        return super(AddRepositoryView, self).form_valid(form)


class ChooseRepositoryView(TemplateView):
    template_name = 'front/dashboard/repositories/choose.html'

    def get_waiting_subscriptions(self):
        """
        Return a dict of waiting subscriptions, with the repositories names as keys
        """
        return dict((s.repository_name, s) for s in self.request.user.waiting_subscriptions.all())

    def get_subscriptions(self):
        """
        Return a dict of subscriptions, with the repositories names as keys
        """
        return dict((s.repository.full_name, s) for s in self.request.user.subscriptions.all().select_related('repository__owner'))

    def get_context_data(self, *args, **kwargs):
        context = super(ChooseRepositoryView, self).get_context_data(*args, **kwargs)
        context.update({
            'available_repositories': self.request.user.available_repositories,
            'waiting_subscriptions': self.get_waiting_subscriptions(),
            'subscriptions': self.get_subscriptions()
        })
        return context