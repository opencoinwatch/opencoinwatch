from  opencoinwatch import config
from alerting.models import Alert, Job
from alerting import logic

from django.http import HttpResponse, HttpResponseBadRequest
from django.template import loader
from django.contrib.auth.decorators import login_required
from django.contrib import auth, messages
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth.models import User
from django.views import View
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin


class LoginView(View):
    def post(self, request):
        # Authentication attempt
        username = request.POST['username']
        password = request.POST['password']
        next = request.POST['next']
        user = auth.authenticate(request, username=username, password=password)

        if user is None:
            # Authentication failure
            if not User.objects.filter(username=username).exists():
                messages.add_message(request, messages.ERROR,
                                     f'User does not exist.')
            else:
                messages.add_message(request, messages.ERROR,
                                     f'Error occurred, please check your password.')
            return redirect(f'{reverse("alerting:login")}?next={next}')

        # Authentication success
        auth.login(request, user)
        if next == "":
            next = 'alerting:index'
        return redirect(next)

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('alerting:index')
        next = request.GET.get('next', '')
        template = loader.get_template('alerting/login.html')
        context = {
            'next': next,
            'production': settings.PRODUCTION,
        }
        return HttpResponse(template.render(context, request))


def logout(request):
    auth.logout(request)
    return redirect('alerting:login')


@login_required
def index(request):
    return redirect('alerting:validating')


class ValidatingView(LoginRequiredMixin, View):
    def get(self, request):
        template = loader.get_template('alerting/validating.html')
        alerts = Alert.objects.filter(published=False, declined=False)
        alerts = sorted(alerts, key=lambda alert: alert.get_importance_with_handicap(), reverse=True)
        context = {
            'user': request.user,
            'production': settings.PRODUCTION,
            'build': config.BUILD,
            'page_id': 'validating',
            'alerts': alerts,
            'validating_alerts_count': len(Alert.objects.filter(published=False, declined=False)),
            'warning_recently_published': logic.warn_recently_published(),
            'recently_published_warning_duration_minutes': config.RECENTLY_PUBLISHED_WARNING_DURATION_MINUTES,
        }
        return HttpResponse(template.render(context, request))

    def post(self, request):
        POST = self.request.POST

        alert = Alert.objects.filter(pk=POST['pk']).first()  # Returns the alert if exists, None otherwise

        if alert is None:
            messages.add_message(request, messages.ERROR, f'Invalid action, the alert was not found.')
            return redirect(reverse('alerting:validating'))
        elif not alert.is_validating():
            messages.add_message(request, messages.ERROR, f'Action not available anymore, the alert has already been processed.')
            return redirect(reverse('alerting:validating'))

        if POST['action'] == 'publish':
            alert.publish()
            messages.add_message(request, messages.SUCCESS, f'Alert was published.')
            return redirect(reverse('alerting:validating'))
        elif POST['action'] == 'decline':
            alert.decline()
            messages.add_message(request, messages.SUCCESS, f'Alert was declined.')
            return redirect(reverse('alerting:validating'))
        return HttpResponseBadRequest("400 Bad Request")


class PublishedView(LoginRequiredMixin, View):
    def get(self, request):
        template = loader.get_template('alerting/published.html')
        alerts = Alert.objects.filter(published=True).order_by('-published_time')
        context = {
            'user': request.user,
            'production': settings.PRODUCTION,
            'build': config.BUILD,
            'page_id': 'published',
            'alerts': alerts,
            'validating_alerts_count': len(Alert.objects.filter(published=False, declined=False)),
        }
        return HttpResponse(template.render(context, request))


class DeclinedView(LoginRequiredMixin, View):
    def get(self, request):
        template = loader.get_template('alerting/declined.html')
        alerts = Alert.objects.filter(declined=True).order_by('-generated_time')
        context = {
            'user': request.user,
            'production': settings.PRODUCTION,
            'build': config.BUILD,
            'page_id': 'declined',
            'alerts': alerts,
            'validating_alerts_count': len(Alert.objects.filter(published=False, declined=False)),
        }
        return HttpResponse(template.render(context, request))


class JobsView(LoginRequiredMixin, View):
    def get(self, request):
        template = loader.get_template('alerting/jobs.html')
        jobs = Job.objects.order_by('-start_time')
        context = {
            'user': request.user,
            'production': settings.PRODUCTION,
            'build': config.BUILD,
            'page_id': 'jobs',
            'jobs': jobs,
            'validating_alerts_count': len(Alert.objects.filter(published=False, declined=False)),
        }
        return HttpResponse(template.render(context, request))
