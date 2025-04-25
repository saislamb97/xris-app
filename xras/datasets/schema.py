import graphene
from graphene_django.types import DjangoObjectType
from datasets.models import XmprData

def normalize_url(url):
    if url.startswith("/media/media/"):
        return url.replace("/media/media/", "/media/", 1)
    return url

class XmprDataType(DjangoObjectType):
    csv = graphene.String()
    png = graphene.String()
    tiff = graphene.String()

    class Meta:
        model = XmprData
        fields = ("id", "time", "created_at", "updated_at")

    def resolve_csv(self, info):
        return normalize_url(self.csv.url) if self.csv else None

    def resolve_png(self, info):
        return normalize_url(self.png.url) if self.png else None

    def resolve_tiff(self, info):
        return normalize_url(self.tiff.url) if self.tiff else None


class Query(graphene.ObjectType):
    latest_xmpr_data = graphene.List(
        XmprDataType,
        page=graphene.Int(required=False, default_value=1),
        page_size=graphene.Int(required=False, default_value=10)
    )

    def resolve_latest_xmpr_data(self, info, page, page_size):
        offset = (page - 1) * page_size

        # Only include entries where png is present
        queryset = XmprData.objects.exclude(png='').exclude(png__isnull=True).order_by('-time')
        return queryset[offset:offset + page_size]


schema = graphene.Schema(query=Query)
