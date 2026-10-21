import io
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from inventory.models import (
    ClarificationCategory,
    IntakeBatchSession,
    Product,
    ProductClarification,
    ProductStatus,
)
from inventory.permissions import ROLE_ASSISTANT, ROLE_MANAGER
from inventory.services.intake_batch_service import (
    get_debounce_minutes,
    process_pending_intake_batches,
)

User = get_user_model()


class IntakeBatchNotificationTests(TestCase):
    def setUp(self):
        self.assistant_group, _ = Group.objects.get_or_create(name=ROLE_ASSISTANT)
        self.manager_group, _ = Group.objects.get_or_create(name=ROLE_MANAGER)

        self.assistant_a = User.objects.create_user(
            username="assistant_clara",
            first_name="Clara",
            last_name="Sourcing",
            password="password123",
        )
        self.assistant_a.groups.add(self.assistant_group)

        self.assistant_b = User.objects.create_user(
            username="assistant_marc",
            first_name="Marc",
            last_name="Vintage",
            password="password123",
        )
        self.assistant_b.groups.add(self.assistant_group)

        self.manager = User.objects.create_user(
            username="manager_elena",
            first_name="Elena",
            last_name="Manager",
            password="password123",
            is_staff=True,
        )
        self.manager.groups.add(self.manager_group)

    def test_get_debounce_minutes_defaults_and_override(self):
        with override_settings(INTAKE_SESSION_DEBOUNCE_MINUTES=15):
            self.assertEqual(get_debounce_minutes(), 15)
        with override_settings(INTAKE_SESSION_DEBOUNCE_MINUTES=20):
            self.assertEqual(get_debounce_minutes(), 20)

    @patch("inventory.services.push_service.send_push_to_group")
    @override_settings(PUSH_NOTIFICATIONS_LIVE_SIGNALS=True)
    def test_first_upload_creates_new_session_without_immediate_notification(self, mock_push):
        product = Product.objects.create(
            raw_note="Vintage trench coat Burberry",
            created_by=self.assistant_a,
        )
        self.assertEqual(product.status, ProductStatus.DRAFT)
        mock_push.assert_not_called()

        session = product.batch_session
        self.assertIsNotNone(session)
        self.assertEqual(session.assistant, self.assistant_a)
        self.assertEqual(session.product_count, 1)
        self.assertFalse(session.is_notified)
        self.assertIsNone(session.closed_at)

    @patch("inventory.services.push_service.send_push_to_group")
    @override_settings(PUSH_NOTIFICATIONS_LIVE_SIGNALS=True)
    def test_sequential_uploads_within_window_increment_batch_count(self, mock_push):
        p1 = Product.objects.create(raw_note="Item 1", created_by=self.assistant_a)
        session = p1.batch_session

        # Upload 2 more items shortly after
        p2 = Product.objects.create(raw_note="Item 2", created_by=self.assistant_a)
        p3 = Product.objects.create(raw_note="Item 3", created_by=self.assistant_a)

        session.refresh_from_db()
        self.assertEqual(p2.batch_session, session)
        self.assertEqual(p3.batch_session, session)
        self.assertEqual(session.product_count, 3)
        self.assertFalse(session.is_notified)
        mock_push.assert_not_called()

    @patch("inventory.services.push_service.send_push_to_group")
    @override_settings(PUSH_NOTIFICATIONS_LIVE_SIGNALS=True)
    def test_debounce_window_expiration_dispatches_single_consolidated_notification(self, mock_push):
        # Assistant uploads 4 items
        for i in range(4):
            Product.objects.create(raw_note=f"Batch Item {i}", created_by=self.assistant_a)

        session = IntakeBatchSession.objects.filter(assistant=self.assistant_a).first()
        self.assertEqual(session.product_count, 4)
        mock_push.assert_not_called()

        # Simulate 16 minutes having elapsed since last activity
        sixteen_minutes_ago = timezone.now() - timedelta(minutes=16)
        IntakeBatchSession.objects.filter(pk=session.pk).update(last_activity_at=sixteen_minutes_ago)

        results = process_pending_intake_batches(debounce_minutes=15)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["session_id"], session.id)
        self.assertEqual(results[0]["product_count"], 4)

        mock_push.assert_called_once()
        self.assertEqual(mock_push.call_args.kwargs["group_name"], ROLE_MANAGER)
        self.assertIn("4", mock_push.call_args.kwargs["title"])
        self.assertEqual(mock_push.call_args.kwargs["url"], "/dashboard/?status=draft")
        self.assertEqual(mock_push.call_args.kwargs["tag"], f"intake-batch-{session.id}")

        session.refresh_from_db()
        self.assertTrue(session.is_notified)
        self.assertIsNotNone(session.closed_at)

    @patch("inventory.services.push_service.send_push_to_group")
    @override_settings(PUSH_NOTIFICATIONS_LIVE_SIGNALS=True)
    def test_idempotency_no_duplicate_notifications(self, mock_push):
        Product.objects.create(raw_note="Item 1", created_by=self.assistant_a)
        session = IntakeBatchSession.objects.filter(assistant=self.assistant_a).first()
        IntakeBatchSession.objects.filter(pk=session.pk).update(
            last_activity_at=timezone.now() - timedelta(minutes=20)
        )

        # First pass notifies
        res1 = process_pending_intake_batches(debounce_minutes=15)
        self.assertEqual(len(res1), 1)
        self.assertEqual(mock_push.call_count, 1)

        # Second pass does nothing
        res2 = process_pending_intake_batches(debounce_minutes=15)
        self.assertEqual(len(res2), 0)
        self.assertEqual(mock_push.call_count, 1)

    @patch("inventory.services.push_service.send_push_to_group")
    @override_settings(PUSH_NOTIFICATIONS_LIVE_SIGNALS=True)
    def test_new_upload_after_session_closed_starts_fresh_session(self, mock_push):
        p1 = Product.objects.create(raw_note="Item 1", created_by=self.assistant_a)
        first_session = p1.batch_session

        # Close first session
        IntakeBatchSession.objects.filter(pk=first_session.pk).update(
            last_activity_at=timezone.now() - timedelta(minutes=30)
        )
        process_pending_intake_batches(debounce_minutes=15)

        first_session.refresh_from_db()
        self.assertTrue(first_session.is_notified)

        # Next day / later upload
        p2 = Product.objects.create(raw_note="Item 2 next lot", created_by=self.assistant_a)
        second_session = p2.batch_session

        self.assertNotEqual(first_session.id, second_session.id)
        self.assertEqual(second_session.product_count, 1)
        self.assertFalse(second_session.is_notified)

    @patch("inventory.services.push_service.send_push_to_group")
    @override_settings(PUSH_NOTIFICATIONS_LIVE_SIGNALS=True)
    def test_independent_sessions_per_assistant(self, mock_push):
        p_a = Product.objects.create(raw_note="Item Clara", created_by=self.assistant_a)
        p_b = Product.objects.create(raw_note="Item Marc", created_by=self.assistant_b)

        self.assertNotEqual(p_a.batch_session.id, p_b.batch_session.id)
        self.assertEqual(p_a.batch_session.assistant, self.assistant_a)
        self.assertEqual(p_b.batch_session.assistant, self.assistant_b)
        self.assertEqual(p_a.batch_session.product_count, 1)
        self.assertEqual(p_b.batch_session.product_count, 1)

    @patch("inventory.services.push_service.send_push_to_group")
    @override_settings(PUSH_NOTIFICATIONS_LIVE_SIGNALS=True)
    def test_dry_run_mode_does_not_mutate_or_send_push(self, mock_push):
        Product.objects.create(raw_note="Item 1", created_by=self.assistant_a)
        session = IntakeBatchSession.objects.filter(assistant=self.assistant_a).first()
        IntakeBatchSession.objects.filter(pk=session.pk).update(
            last_activity_at=timezone.now() - timedelta(minutes=20)
        )

        results = process_pending_intake_batches(debounce_minutes=15, dry_run=True)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["is_dry_run"])
        mock_push.assert_not_called()

        session.refresh_from_db()
        self.assertFalse(session.is_notified)
        self.assertIsNone(session.closed_at)

    @patch("inventory.services.push_service.send_push_to_group")
    @override_settings(PUSH_NOTIFICATIONS_LIVE_SIGNALS=True)
    def test_management_command_execution(self, mock_push):
        Product.objects.create(raw_note="Item 1", created_by=self.assistant_a)
        session = IntakeBatchSession.objects.filter(assistant=self.assistant_a).first()
        IntakeBatchSession.objects.filter(pk=session.pk).update(
            last_activity_at=timezone.now() - timedelta(minutes=20)
        )

        # Dry run CLI
        out_dry = io.StringIO()
        call_command("process_intake_batches", "--dry-run", stdout=out_dry)
        self.assertIn("[DRY RUN]", out_dry.getvalue())
        self.assertIn("Processed 1 intake batch session(s)", out_dry.getvalue())
        mock_push.assert_not_called()

        # Real CLI execution
        out_real = io.StringIO()
        call_command("process_intake_batches", stdout=out_real)
        self.assertIn("Processed 1 intake batch session(s)", out_real.getvalue())
        mock_push.assert_called_once()

        session.refresh_from_db()
        self.assertTrue(session.is_notified)

    @patch("inventory.services.push_service.send_push_to_group")
    @override_settings(PUSH_NOTIFICATIONS_LIVE_SIGNALS=True)
    def test_urgent_notifications_remain_instant_and_undebounced(self, mock_push):
        product = Product.objects.create(
            raw_note="Silk dress",
            ai_title="Vintage Silk Dress",
            ai_description="Beautiful 100% silk dress with floral pattern.",
            created_by=self.assistant_a,
        )
        # Note: product transitioned to PRICE_PENDING upon save because it has title and description but no price
        self.assertEqual(product.status, ProductStatus.PRICE_PENDING)
        mock_push.assert_called_once()
        self.assertEqual(mock_push.call_args.kwargs["group_name"], ROLE_MANAGER)
        self.assertEqual(
            mock_push.call_args.kwargs["tag"], f"product-price-pending-{product.pk}"
        )

        # Urgent clarification question asked by manager
        mock_push.reset_mock()
        clarification = ProductClarification.objects.create(
            product=product,
            category=ClarificationCategory.TAG_COMPOSITION,
            question="Is the lining 100% silk or polyester?",
            asked_by=self.manager,
        )
        mock_push.assert_called_once()
        self.assertEqual(mock_push.call_args.kwargs["group_name"], ROLE_ASSISTANT)
        self.assertEqual(
            mock_push.call_args.kwargs["tag"], f"clarification-product-{product.pk}"
        )

        # Urgent clarification response from assistant
        mock_push.reset_mock()
        clarification.resolve(answer="Lining is acetate", answered_by=self.assistant_a)
        # Verify manager alerted immediately
        self.assertTrue(mock_push.called)
        tags = [call.kwargs.get("tag") for call in mock_push.call_args_list]
        self.assertTrue(any(t.startswith(f"clarification-resolved-{product.pk}") for t in tags))

    def test_intake_batch_session_admin_views_and_permissions(self):
        client = Client()

        # Assistant is blocked from admin (403)
        client.force_login(self.assistant_a)
        resp_assistant = client.get("/admin/inventory/intakebatchsession/")
        self.assertEqual(resp_assistant.status_code, 403)

        # Manager can view changelist and batch details
        client.force_login(self.manager)
        p = Product.objects.create(
            raw_note="Admin test coat",
            ai_title="Admin test coat",
            created_by=self.assistant_a,
        )
        session = p.batch_session

        resp_manager_list = client.get("/admin/inventory/intakebatchsession/")
        self.assertEqual(resp_manager_list.status_code, 200)
        self.assertContains(resp_manager_list, "assistant_clara")

        resp_manager_detail = client.get(f"/admin/inventory/intakebatchsession/{session.pk}/change/")
        self.assertEqual(resp_manager_detail.status_code, 200)
        self.assertContains(resp_manager_detail, "Admin test coat")
