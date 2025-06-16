from django.urls import path
from processor.views import rainmap_data, download_rainmap_data

app_name = 'processor'

urlpatterns = [
    path('rainmap/', rainmap_data, name='rainmap_data'),
    path('rainmap/download/', download_rainmap_data, name='download_rainmap_data'),

]
