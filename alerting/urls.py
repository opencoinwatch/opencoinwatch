from . import views

from django.urls import path


app_name = 'alerting'
urlpatterns = [
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.logout, name='logout'),
    path('', views.index, name='index'),
    path('validating/', views.ValidatingView.as_view(), name='validating'),
    path('published/', views.PublishedView.as_view(), name='published'),
    path('declined/', views.DeclinedView.as_view(), name='declined'),
    path('jobs/', views.JobsView.as_view(), name='jobs'),
]
