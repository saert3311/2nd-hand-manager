from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from inventory.models import (
    ClarificationCategory,
    MarketplaceSite,
    Product,
    ProductClarification,
    ProductListingLink,
    ProductStatus,
)

User = get_user_model()


class ProductLifecycleStateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password123")
        self.site, _ = MarketplaceSite.objects.get_or_create(
            slug="wallapop",
            defaults={
                "name": "Wallapop",
                "base_url": "https://es.wallapop.com",
                "order": 1,
                "is_active": True,
            },
        )

    def test_item_without_description_is_draft(self):
        """A product without description is in DRAFT state."""
        product = Product.objects.create(
            raw_note="Vintage jacket",
            ai_title="Vintage Jacket",
            ai_description="",
        )
        self.assertEqual(product.status, ProductStatus.DRAFT)
        self.assertFalse(product.is_sold)

    def test_item_with_description_and_title_but_no_price_is_price_pending(self):
        """A product with title and description but missing price is PRICE_PENDING."""
        product = Product.objects.create(
            ai_title="Vintage Schott Leather Jacket",
            ai_description="Great condition, size L, black leather.",
            sale_price=None,
        )
        self.assertEqual(product.status, ProductStatus.PRICE_PENDING)

    def test_item_with_zero_price_is_price_pending(self):
        """A product with sale_price=0.00 is treated as missing price (PRICE_PENDING)."""
        product = Product.objects.create(
            ai_title="Vintage Schott Leather Jacket",
            ai_description="Great condition, size L, black leather.",
            sale_price=Decimal("0.00"),
        )
        self.assertEqual(product.status, ProductStatus.PRICE_PENDING)

    def test_item_with_title_description_and_price_is_ready(self):
        """A product with title, description, and valid price is READY."""
        product = Product.objects.create(
            ai_title="Vintage Schott Leather Jacket",
            ai_description="Great condition, size L, black leather.",
            sale_price=Decimal("150.00"),
        )
        self.assertEqual(product.status, ProductStatus.READY)

    def test_adding_price_to_price_pending_transitions_to_ready(self):
        """Entering a sale price automatically transitions a PRICE_PENDING item to READY."""
        product = Product.objects.create(
            ai_title="Vintage Schott Leather Jacket",
            ai_description="Great condition, size L, black leather.",
            sale_price=None,
        )
        self.assertEqual(product.status, ProductStatus.PRICE_PENDING)

        product.sale_price = Decimal("120.00")
        product.save()
        self.assertEqual(product.status, ProductStatus.READY)

    def test_adding_marketplace_link_transitions_to_published(self):
        """Adding any active marketplace link automatically sets status to PUBLISHED."""
        product = Product.objects.create(
            ai_title="Vintage Schott Leather Jacket",
            ai_description="Great condition, size L, black leather.",
            sale_price=Decimal("120.00"),
        )
        self.assertEqual(product.status, ProductStatus.READY)

        ProductListingLink.objects.create(
            product=product,
            site=self.site,
            url="https://es.wallapop.com/item/123",
            is_active=True,
        )
        product.refresh_from_db()
        self.assertEqual(product.status, ProductStatus.PUBLISHED)

    def test_deleting_all_marketplace_links_reverts_to_ready(self):
        """Removing all marketplace links automatically recalculates status back to READY."""
        product = Product.objects.create(
            ai_title="Vintage Schott Leather Jacket",
            ai_description="Great condition, size L, black leather.",
            sale_price=Decimal("120.00"),
        )
        link = ProductListingLink.objects.create(
            product=product,
            site=self.site,
            url="https://es.wallapop.com/item/123",
            is_active=True,
        )
        product.refresh_from_db()
        self.assertEqual(product.status, ProductStatus.PUBLISHED)

        link.delete()
        product.refresh_from_db()
        self.assertEqual(product.status, ProductStatus.READY)

    def test_deleting_link_when_missing_price_reverts_to_price_pending(self):
        """Removing links when price is missing recalculates status back to PRICE_PENDING."""
        product = Product.objects.create(
            ai_title="Vintage Schott Leather Jacket",
            ai_description="Great condition, size L, black leather.",
            sale_price=None,
        )
        link = ProductListingLink.objects.create(
            product=product,
            site=self.site,
            url="https://es.wallapop.com/item/123",
            is_active=True,
        )
        product.refresh_from_db()
        self.assertEqual(product.status, ProductStatus.PUBLISHED)

        link.delete()
        product.refresh_from_db()
        self.assertEqual(product.status, ProductStatus.PRICE_PENDING)

    def test_clarification_doubts_take_precedence(self):
        """Pending doubts set status to AWAITING_INFO; resolving them restores computed status."""
        product = Product.objects.create(
            ai_title="Vintage Schott Leather Jacket",
            ai_description="Great condition, size L, black leather.",
            sale_price=Decimal("120.00"),
        )
        self.assertEqual(product.status, ProductStatus.READY)

        clarif = ProductClarification.objects.create(
            product=product,
            category=ClarificationCategory.MEASUREMENTS,
            question="Check armpit measurement",
            asked_by=self.user,
        )
        product.refresh_from_db()
        self.assertEqual(product.status, ProductStatus.AWAITING_INFO)

        # Resolving clarification restores to READY
        clarif.resolve(answer="54 cm chest", answered_by=self.user)
        product.refresh_from_db()
        self.assertEqual(product.status, ProductStatus.READY)

    def test_sold_state_takes_precedence(self):
        """Marking a product as sold sets status to SOLD and is_sold to True."""
        product = Product.objects.create(
            ai_title="Vintage Schott Leather Jacket",
            ai_description="Great condition, size L, black leather.",
            sale_price=Decimal("120.00"),
        )
        product.mark_as_sold(price=Decimal("110.00"))
        self.assertEqual(product.status, ProductStatus.SOLD)
        self.assertTrue(product.is_sold)
        self.assertEqual(product.sale_price, Decimal("110.00"))

        # Unsold restores to READY
        product.mark_as_unsold()
        self.assertEqual(product.status, ProductStatus.READY)
        self.assertFalse(product.is_sold)

    def test_blocked_state_takes_precedence(self):
        """A blocked product remains BLOCKED until explicitly changed."""
        product = Product.objects.create(
            ai_title="Vintage Schott Leather Jacket",
            ai_description="Great condition, size L, black leather.",
            sale_price=Decimal("120.00"),
            status=ProductStatus.BLOCKED,
        )
        self.assertEqual(product.status, ProductStatus.BLOCKED)
        product.save()
        self.assertEqual(product.status, ProductStatus.BLOCKED)
