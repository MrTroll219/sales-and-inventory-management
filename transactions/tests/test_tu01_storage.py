"""TU01: exercise configured static manifest and default media storage."""
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.core.management import call_command
from django.test import SimpleTestCase, override_settings


class StorageUpgradeTests(SimpleTestCase):
    def test_collectstatic_writes_manifest_and_rewrites_css_asset(self):
        with TemporaryDirectory() as folder:
            source = Path(folder) / "source"
            target = Path(folder) / "collected"
            (source / "css").mkdir(parents=True)
            (source / "img").mkdir()
            (source / "img/dot.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
            (source / "css/site.css").write_text('body {background:url("../img/dot.svg")}', encoding="utf-8")
            # TU02 ordinary tests use plain storage; this test explicitly checks
            # production manifest behavior, with all existing assertions intact.
            production_storages = {name: dict(config) for name, config in settings.STORAGES.items()}
            production_storages["staticfiles"] = {
                "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"}
            with override_settings(STATICFILES_DIRS=[source], STATIC_ROOT=target,
                                   STATICFILES_FINDERS=["django.contrib.staticfiles.finders.FileSystemFinder"],
                                   STORAGES=production_storages):
                call_command("collectstatic", interactive=False, verbosity=0, stdout=StringIO())
                manifest = json.loads((target / "staticfiles.json").read_text(encoding="utf-8"))
                hashed_css = manifest["paths"]["css/site.css"]
                hashed_svg = manifest["paths"]["img/dot.svg"]
                self.assertTrue((target / hashed_css).is_file())
                self.assertTrue((target / hashed_svg).is_file())
                self.assertIn(Path(hashed_svg).name, (target / hashed_css).read_text(encoding="utf-8"))

    def test_default_storage_still_saves_and_reads_media(self):
        with TemporaryDirectory() as folder:
            with override_settings(MEDIA_ROOT=folder, MEDIA_URL="/test-media/", STORAGES=settings.STORAGES):
                storage = storages["default"]
                name = storage.save("tu01/sample.txt", ContentFile(b"TU01 media round trip"))
                self.assertTrue((Path(folder) / name).is_file())
                with storage.open(name, "rb") as stream:
                    self.assertEqual(stream.read(), b"TU01 media round trip")
                self.assertEqual(storage.url(name), "/test-media/tu01/sample.txt")
