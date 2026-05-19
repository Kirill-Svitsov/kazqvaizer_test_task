from django.apps import apps
from django.conf import settings
from django.db.models import DecimalField, Max, Min, Q, Sum
from django.db.models.functions import Coalesce
from django.utils.translation import gettext_lazy as _

from app.models import models
from inventory.logic.binding import ItemsBinder
from inventory.logic.listing_editor import ListingEditor
from inventory.logic.unbinding import ItemsUnBinder

from .base import BaseProduct


class InventoryItemQuerySet(models.QuerySet):
    def for_viewset(self):
        return (
            self.select_related("owner")
            .prefetch_related("warehouse_items")
            .annotate_with_total_stock()
        )

    def group_by_owners(self):
        """You can improve performance by using window function.
        Search such solution in `parsa-backend` for help."""
        owners = apps.get_model("inventory.InventoryOwner").objects.all()
        resulting_ids = []
        for owner in owners:
            owner_items = self.filter(owner=owner).values_list("id", flat=True)
            resulting_ids.extend(owner_items[: settings.ITEMS_PER_OWNER_NUMBER])
        return self.filter(id__in=resulting_ids)

    def annotate_with_total_stock(self):
        return self.annotate(
            warehouse_total_stock=Coalesce(Sum("warehouse_items__stock"), 0)
        )

    def annotate_with_region_aggregates(self, region_id):
        """Аннотирует товары суммой stock и min/max price для конкретного региона."""
        return self.annotate(
            region_total_stock=Coalesce(
                Sum(
                    "warehouse_items__stock",
                    filter=Q(warehouse_items__warehouse__region_id=region_id),
                ),
                0,
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
            region_min_price=Coalesce(
                Min(
                    "warehouse_items__price",
                    filter=Q(warehouse_items__warehouse__region_id=region_id)
                    & Q(warehouse_items__price__isnull=False),
                ),
                0,
                output_field=DecimalField(max_digits=10, decimal_places=2),
            ),
            region_max_price=Coalesce(
                Max(
                    "warehouse_items__price",
                    filter=Q(warehouse_items__warehouse__region_id=region_id)
                    & Q(warehouse_items__price__isnull=False),
                ),
                0,
                output_field=DecimalField(max_digits=10, decimal_places=2),
            ),
        )


class InventoryItem(BaseProduct):
    objects = InventoryItemQuerySet.as_manager()

    owner = models.ForeignKey(
        "inventory.InventoryOwner",
        on_delete=models.PROTECT,
        related_name="inventory_items",
    )
    product = models.ForeignKey(
        "inventory.Product",
        related_name="inventory_items",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
    )
    sku = models.CharField(
        _("Sku"), max_length=255, blank=True, null=True, db_index=True
    )

    class Meta:
        verbose_name = _("Inventory item")
        verbose_name_plural = _("Inventory items")
        unique_together = [["owner", "product"], ["owner", "sku"], ["owner", "ean"]]

    def __str__(self):
        return self.name

    @property
    def binder(self):
        return ItemsBinder(self)

    @property
    def unbinder(self):
        return ItemsUnBinder(self)

    @property
    def listing_editor(self):
        return ListingEditor(self)
