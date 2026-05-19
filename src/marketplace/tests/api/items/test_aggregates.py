from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from inventory.models import InventoryItem, InventoryOwner, Product
from marketplace.constants import (
    TEST_INVENTORY_ITEM_NAME,
    TEST_INVENTORY_ITEM_SKU,
    TEST_LISTING_NAME,
    TEST_MARKETPLACE_NAME,
    TEST_MARKETPLACE_SLUG,
    TEST_MAX_PRICE,
    TEST_MIN_PRICE,
    TEST_OWNER_NAME,
    TEST_OWNER_SLUG,
    TEST_PRICE_WAREHOUSE_1,
    TEST_PRICE_WAREHOUSE_2,
    TEST_PRODUCT_NAME,
    TEST_REGION_NAME,
    TEST_REGION_SLUG,
    TEST_STOCK_WAREHOUSE_1,
    TEST_STOCK_WAREHOUSE_2,
    TEST_TOTAL_STOCK,
    TEST_WAREHOUSE_NAME_FIRST,
    TEST_WAREHOUSE_NAME_SECOND,
)
from marketplace.models import Listing, Marketplace, MarketplaceItem
from regions.models import Region
from warehouse.models import Warehouse, WarehouseItem


class ListingItemAggregatesTest(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_superuser(
            username="testuser", password="testpass", email="test@test.com"
        )
        token = Token.objects.create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        self.region = Region.objects.create(
            name=TEST_REGION_NAME, slug=TEST_REGION_SLUG
        )
        self.owner = InventoryOwner.objects.create(
            name=TEST_OWNER_NAME, slug=TEST_OWNER_SLUG
        )
        self.warehouse1 = Warehouse.objects.create(
            name=TEST_WAREHOUSE_NAME_FIRST, owner=self.owner, region=self.region
        )
        self.warehouse2 = Warehouse.objects.create(
            name=TEST_WAREHOUSE_NAME_SECOND, owner=self.owner, region=self.region
        )
        self.product = Product.objects.create(name=TEST_PRODUCT_NAME, unit="шт")
        self.item = InventoryItem.objects.create(
            name=TEST_INVENTORY_ITEM_NAME,
            owner=self.owner,
            product=self.product,
            sku=TEST_INVENTORY_ITEM_SKU,
        )
        WarehouseItem.objects.create(
            inventory_item=self.item,
            warehouse=self.warehouse1,
            stock=TEST_STOCK_WAREHOUSE_1,
            price=TEST_PRICE_WAREHOUSE_1,
        )
        WarehouseItem.objects.create(
            inventory_item=self.item,
            warehouse=self.warehouse2,
            stock=TEST_STOCK_WAREHOUSE_2,
            price=TEST_PRICE_WAREHOUSE_2,
        )
        self.marketplace = Marketplace.objects.create(
            name=TEST_MARKETPLACE_NAME, slug=TEST_MARKETPLACE_SLUG
        )
        self.listing = Listing.objects.create(
            name=TEST_LISTING_NAME, marketplace=self.marketplace, region=self.region
        )
        self.marketplace_item = MarketplaceItem.objects.create(
            marketplace=self.marketplace, product=self.product, status="confirmed"
        )
        self.marketplace_item.listings.add(self.listing)

    def test_response_has_aggregate_fields(self):
        """Тест: API возвращает поля total_stock, min_price, max_price"""
        response = self.client.get(
            f"/api/v1/marketplace/listings/{self.listing.id}/items/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = response.json()["results"][0]
        self.assertIn("total_stock", result)
        self.assertIn("min_price", result)
        self.assertIn("max_price", result)
        self.assertEqual(result["total_stock"], TEST_TOTAL_STOCK)
        self.assertEqual(result["min_price"], TEST_MIN_PRICE)
        self.assertEqual(result["max_price"], TEST_MAX_PRICE)
