from django.core.cache import cache
from django.shortcuts import get_object_or_404
from django.utils.functional import cached_property
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from app.permissions import MarketplaceOnly, StuffAndSuperUserOnly
from inventory.models import InventoryItem
from marketplace.api.serializers import SimpleListingItemSerializer
from marketplace.constants import CACHE_TIMEOUT
from marketplace.models import Listing, MarketplaceItem


class ListingItemViewSet(ReadOnlyModelViewSet):
    queryset = MarketplaceItem.objects.none()
    serializer_class = SimpleListingItemSerializer
    permission_classes = [StuffAndSuperUserOnly | MarketplaceOnly]

    @cached_property
    def listing(self) -> Listing:
        filters = {"id": self.kwargs.get("listing_pk")}
        if self.request.marketplace:
            filters["marketplace"] = self.request.marketplace
        return get_object_or_404(Listing, **filters)

    def get_queryset(self):
        return (
            MarketplaceItem.objects.filter(listings__id=self.listing.pk)
            .select_related("product")
            .distinct()
        )

    def list(self, request, *args, **kwargs):
        cache_key = f"listing_items_{self.listing.id}_region_{self.listing.region_id}"
        cached_response = cache.get(cache_key)
        if cached_response is not None:
            return Response(cached_response)
        queryset = self.filter_queryset(self.get_queryset())
        product_ids = list(queryset.values_list("product_id", flat=True))
        if product_ids:
            inventory_items = InventoryItem.objects.filter(
                product_id__in=product_ids
            ).annotate_with_region_aggregates(self.listing.region_id)
            self._aggregates_map = {
                item.product_id: {
                    "total_stock": str(item.region_total_stock),
                    "min_price": str(item.region_min_price),
                    "max_price": str(item.region_max_price),
                }
                for item in inventory_items
            }
        else:
            self._aggregates_map = {}
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            data = self._inject_aggregates(serializer.data)
            response = self.get_paginated_response(data)
            cache.set(cache_key, response.data, CACHE_TIMEOUT)
            return response
        serializer = self.get_serializer(queryset, many=True)
        data = self._inject_aggregates(serializer.data)
        response_data = {
            "count": len(data),
            "next": None,
            "previous": None,
            "results": data,
        }
        cache.set(cache_key, response_data, CACHE_TIMEOUT)
        return Response(response_data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        product_id = instance.product_id
        cache_key = f"listing_items_agg_{self.listing.id}_region_{self.listing.region_id}_{product_id}"
        cached_agg = cache.get(cache_key)
        if cached_agg:
            data.update(cached_agg)
        else:
            inventory_item = (
                InventoryItem.objects.filter(product_id=product_id)
                .annotate_with_region_aggregates(self.listing.region_id)
                .first()
            )
            if inventory_item:
                agg_data = {
                    "total_stock": str(inventory_item.region_total_stock),
                    "min_price": str(inventory_item.region_min_price),
                    "max_price": str(inventory_item.region_max_price),
                }
                data.update(agg_data)
                cache.set(cache_key, agg_data, CACHE_TIMEOUT)
            else:
                data.update(
                    {
                        "total_stock": "0.00",
                        "min_price": "0.00",
                        "max_price": "0.00",
                    }
                )
        return Response(data)

    def _inject_aggregates(self, data):
        for item_data in data:
            agg = self._aggregates_map.get(int(item_data["gmid"]), {})
            item_data["total_stock"] = agg.get("total_stock", "0.00")
            item_data["min_price"] = agg.get("min_price", "0.00")
            item_data["max_price"] = agg.get("max_price", "0.00")
        return data
