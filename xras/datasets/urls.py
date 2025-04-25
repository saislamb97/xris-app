from django.urls import path
from datasets.views import download_xmpr_data, xmpr_data

app_name = 'datasets'

urlpatterns = [
    path('xmpr/', xmpr_data, name='xmpr_data'),
    path('xmpr/download/', download_xmpr_data, name='download_xmpr_data'),
]
