"""TU01: read-only preflight before applying accounts/0002."""
import json

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Q
from django.db.models.functions import Length

from accounts.models import Profile


class Command(BaseCommand):
    help = "TU01: read-only check for duplicate emails (including '') and overlong Profile data."

    def handle(self, *args, **options):
        duplicates = list(
            Profile.objects.order_by().exclude(email__isnull=True).values("email")
            .annotate(count=Count("pk")).filter(count__gt=1).order_by("email")
        )
        long_names = list(
            Profile.objects.annotate(first_length=Length("first_name"), last_length=Length("last_name"))
            .filter(Q(first_length__gt=30) | Q(last_length__gt=30)).order_by("pk")
            .values("pk", "first_length", "last_length")
        )
        long_emails = list(
            Profile.objects.annotate(email_length=Length("email")).filter(email_length__gt=150)
            .order_by("pk").values("pk", "email_length")
        )
        result = {"duplicate_emails": duplicates, "overlong_names": long_names,
                  "overlong_emails": long_emails, "safe_to_migrate": not (duplicates or long_names or long_emails)}
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
        if not result["safe_to_migrate"]:
            raise CommandError("TU01: dữ liệu Profile cần được đối soát trước khi migrate; chưa sửa dữ liệu.")
