"""TU01: migrate legacy Profile data and verify the read-only preflight."""
from io import StringIO
import json

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext


FROM = ("accounts", "0001_initial")
TO = ("accounts", "0002_alter_profile_email_alter_profile_first_name_and_more")


class ProfileUpgradeTests(TransactionTestCase):
    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate([FROM])
        old_apps = executor.loader.project_state([FROM]).apps
        self.User = old_apps.get_model("auth", "User")
        self.Profile = old_apps.get_model("accounts", "Profile")

    def tearDown(self):
        # Only the isolated test DB: remove intentionally invalid fixtures so the
        # schema is restored for the remaining suite, even after a failed test.
        self.Profile.objects.all().delete()
        MigrationExecutor(connection).migrate([TO])
        super().tearDown()

    def profile(self, username, email, first="Demo", last="User"):
        user = self.User.objects.create(username=username)
        return self.Profile.objects.create(user_id=user.pk, slug=f"tu01-{username}",
                                           email=email, first_name=first, last_name=last)

    def audit(self):
        out = StringIO()
        call_command("check_profile_data", stdout=out)
        return json.loads(out.getvalue())

    def assert_email_unique(self):
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(cursor, "accounts_profile")
        self.assertTrue(any(c["unique"] and c["columns"] == ["email"] for c in constraints.values()))

    def test_empty_accounts_schema_migrates_to_0002(self):
        self.assertTrue(self.audit()["safe_to_migrate"])
        MigrationExecutor(connection).migrate([TO])
        self.assertEqual(self.Profile.objects.count(), 0)
        self.assert_email_unique()

    def test_demo_data_migrates_without_changing_values(self):
        self.profile("one", "one@example.invalid", "A" * 30, "B" * 30)
        self.profile("blank", "")
        self.profile("null-one", None)
        self.profile("null-two", None)
        before = list(self.Profile.objects.order_by("pk").values("id", "email", "first_name", "last_name"))
        self.assertTrue(self.audit()["safe_to_migrate"])
        MigrationExecutor(connection).migrate([TO])
        self.assertEqual(list(self.Profile.objects.order_by("pk").values("id", "email", "first_name", "last_name")), before)
        self.assert_email_unique()

    def test_preflight_detects_duplicates_including_empty_and_overlong_data(self):
        self.profile("dup-one", "same@example.invalid")
        self.profile("dup-two", "same@example.invalid")
        self.profile("blank-one", "")
        self.profile("blank-two", "")
        self.profile("long", "x" * 151, "A" * 31, "B" * 31)
        before = list(self.Profile.objects.order_by("pk").values())
        out = StringIO()
        with CaptureQueriesContext(connection) as queries:
            with self.assertRaises(CommandError):
                call_command("check_profile_data", stdout=out)
        result = json.loads(out.getvalue())
        self.assertFalse(result["safe_to_migrate"])
        self.assertEqual({row["email"] for row in result["duplicate_emails"]}, {"", "same@example.invalid"})
        self.assertEqual(result["overlong_names"][0]["first_length"], 31)
        self.assertEqual(result["overlong_names"][0]["last_length"], 31)
        self.assertEqual(result["overlong_emails"][0]["email_length"], 151)
        self.assertTrue(queries.captured_queries)
        self.assertTrue(all(q["sql"].lstrip().upper().startswith("SELECT") for q in queries.captured_queries))
        self.assertEqual(list(self.Profile.objects.order_by("pk").values()), before)

    def test_preflight_allows_multiple_null_emails_and_boundary_lengths(self):
        self.profile("null1", None, "A" * 30, "B" * 30)
        self.profile("null2", None)
        self.profile("empty", "")
        self.profile("max-email", "x" * 150)
        result = self.audit()
        self.assertTrue(result["safe_to_migrate"])
        self.assertEqual(result["duplicate_emails"], [])
