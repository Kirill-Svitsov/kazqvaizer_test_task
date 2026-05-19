from rest_framework import serializers

from marketplace.models import MarketplaceItem

from .products import MarketplaceProductSerializer


class SimpleListingItemSerializer(serializers.ModelSerializer):
    gmid = serializers.CharField(source="product_id")
    product = MarketplaceProductSerializer()
    total_stock = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True, default="0.00"
    )
    min_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True, default="0.00"
    )
    max_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True, default="0.00"
    )

    class Meta:
        model = MarketplaceItem
        fields = [
            "id",
            "gmid",
            "status",
            "status_comment",
            "product",
            "total_stock",
            "min_price",
            "max_price",
        ]
