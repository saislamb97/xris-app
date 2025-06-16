import graphene
from datasets.schema import Query as DatasetsQuery

class Query(DatasetsQuery, graphene.ObjectType):
    hello = graphene.String(default_value="Hello from XRIS GraphQL!")

schema = graphene.Schema(query=Query)
