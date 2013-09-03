from django.template.response import TemplateResponse
from django.template.loader import render_to_string
from django.contrib.messages.api import get_messages


class AddMessagesToAjaxResponseMiddleware(object):
    def process_response(self, request, response):
        if request.is_ajax() and isinstance(response, TemplateResponse):

            messages_html = render_to_string('front/messages.html',
                                             {'messages': get_messages(request)})
            response.content += messages_html

        return response
