from django.contrib.auth.models import User
from django.core.cache import cache, caches
from django.test import TestCase
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from inventory.models import InventoryItem, InventoryOwner, Product
from marketplace.constants import (
    CACHE_TIMEOUT,
    EMAIL,
    PASSWORD,
    TEST_INITIAL_STOCK_STR,
    TEST_INVENTORY_ITEM_NAME,
    TEST_INVENTORY_ITEM_SKU,
    TEST_LISTING_NAME,
    TEST_MARKETPLACE_NAME,
    TEST_MARKETPLACE_SLUG,
    TEST_OWNER_NAME,
    TEST_OWNER_SLUG,
    TEST_PRICE_WAREHOUSE_1,
    TEST_PRODUCT_NAME,
    TEST_REGION_NAME,
    TEST_REGION_SLUG,
    TEST_STOCK_WAREHOUSE_1,
    TEST_UPDATED_STOCK,
    TEST_WAREHOUSE_NAME_FIRST,
    USERNAME,
)
from marketplace.models import Listing, Marketplace, MarketplaceItem
from regions.models import Region
from warehouse.models import Warehouse, WarehouseItem


class ListingItemCacheTest(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_superuser(
            username=USERNAME, password=PASSWORD, email=EMAIL
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
        self.warehouse = Warehouse.objects.create(
            name=TEST_WAREHOUSE_NAME_FIRST, owner=self.owner, region=self.region
        )
        self.product = Product.objects.create(name=TEST_PRODUCT_NAME, unit="шт")
        self.item = InventoryItem.objects.create(
            name=TEST_INVENTORY_ITEM_NAME,
            owner=self.owner,
            product=self.product,
            sku=TEST_INVENTORY_ITEM_SKU,
        )
        self.warehouse_item = WarehouseItem.objects.create(
            inventory_item=self.item,
            warehouse=self.warehouse,
            stock=TEST_STOCK_WAREHOUSE_1,
            price=TEST_PRICE_WAREHOUSE_1,
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

    def test_cache_returns_cached_value_within_ttl(self):
        """Тест: данные берутся из кэша в течение 10 минут"""
        response1 = self.client.get(
            f"/api/v1/marketplace/listings/{self.listing.id}/items/"
        )
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        result1 = response1.json()["results"][0]
        self.assertEqual(result1["total_stock"], TEST_INITIAL_STOCK_STR)
        self.warehouse_item.stock = TEST_UPDATED_STOCK
        self.warehouse_item.save()
        response2 = self.client.get(
            f"/api/v1/marketplace/listings/{self.listing.id}/items/"
        )
        result2 = response2.json()["results"][0]
        self.assertEqual(result2["total_stock"], TEST_INITIAL_STOCK_STR)
        cache_key = f"listing_items_{self.listing.id}_region_{self.listing.region_id}"
        cache.delete(cache_key)
        response3 = self.client.get(
            f"/api/v1/marketplace/listings/{self.listing.id}/items/"
        )
        result3 = response3.json()["results"][0]
        self.assertEqual(result3["total_stock"], "999.00")

    def test_cache_ttl_is_10_minutes(self):
        """Тест: TTL кэша = 10 минут"""
        response1 = self.client.get(
            f"/api/v1/marketplace/listings/{self.listing.id}/items/"
        )
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        cache_key = f"listing_items_{self.listing.id}_region_{self.listing.region_id}"
        cached_data = cache.get(cache_key)
        self.assertIsNotNone(cached_data)
        redis_cache = caches["default"]
        ttl = redis_cache.ttl(cache_key)
        self.assertGreater(ttl, CACHE_TIMEOUT - 5)
        self.assertLessEqual(ttl, CACHE_TIMEOUT)
