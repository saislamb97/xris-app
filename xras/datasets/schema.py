import graphene
from graphene_django.types import DjangoObjectType
from datasets.models import XmprData
import datetime

class XmprDataType(DjangoObjectType):
    csv = graphene.String()
    png = graphene.String()
    tiff = graphene.String()

    class Meta:
        model = XmprData
        fields = ("id", "time", "created_at", "updated_at")

    def resolve_csv(self, info):
        return self.csv_url  # Use the model's safe URL helper

    def resolve_png(self, info):
        return self.png_url

    def resolve_tiff(self, info):
        return self.tiff_url

class XmprDataPageType(graphene.ObjectType):
    total_count = graphene.Int()
    items = graphene.List(XmprDataType)

class Query(graphene.ObjectType):
    latest_xmpr_data = graphene.Field(
        XmprDataPageType,
        page=graphene.Int(required=False, default_value=1),
        page_size=graphene.Int(required=False, default_value=10),
        date=graphene.String(required=False)  # Format: "YYYY-MM-DD"
    )

    def resolve_latest_xmpr_data(self, info, page, page_size, date=None):
        offset = (page - 1) * page_size
        queryset = XmprData.objects.exclude(png__isnull=True).exclude(png__exact='')

        if date:
            try:
                target_date = datetime.datetime.strptime(date, "%Y-%m-%d").date()
                queryset = queryset.filter(time__date=target_date)
            except ValueError:
                raise ValueError("Invalid date format. Expected 'YYYY-MM-DD'.")

        total = queryset.count()
        items = queryset.order_by('-time')[offset:offset + page_size]
        return XmprDataPageType(total_count=total, items=items)

schema = graphene.Schema(query=Query)
