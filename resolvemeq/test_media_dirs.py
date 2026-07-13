"""Tests for media upload directory helpers."""

from django.test import SimpleTestCase, override_settings

from resolvemeq.media_dirs import MEDIA_SUBDIRS, ensure_media_subdirectories


class MediaDirsTest(SimpleTestCase):
    def test_ensure_media_subdirectories_creates_expected_folders(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            ensure_media_subdirectories(tmp)
            root = Path(tmp)
            for name in MEDIA_SUBDIRS:
                self.assertTrue((root / name).is_dir(), name)

    @override_settings(MEDIA_ROOT="/tmp/resolvemeq-media-test")
    def test_ensure_uses_settings_media_root_by_default(self):
        import shutil
        from pathlib import Path

        root = Path("/tmp/resolvemeq-media-test")
        if root.exists():
            shutil.rmtree(root)
        ensure_media_subdirectories()
        try:
            for name in MEDIA_SUBDIRS:
                self.assertTrue((root / name).is_dir(), name)
        finally:
            shutil.rmtree(root, ignore_errors=True)


class AbsoluteMediaUrlTest(SimpleTestCase):
  @override_settings(MEDIA_URL="/media/", API_BASE_URL="https://api.example.com")
  def test_builds_https_url_from_relative_storage_path(self):
    from resolvemeq.media_dirs import absolute_media_url

    url = absolute_media_url("ticket_pending/abc123.jpg")
    self.assertEqual(url, "https://api.example.com/media/ticket_pending/abc123.jpg")

  @override_settings(MEDIA_URL="/media/", API_BASE_URL="https://api.example.com")
  def test_passes_through_existing_absolute_url(self):
    from resolvemeq.media_dirs import absolute_media_url

    existing = "https://cdn.example.com/x.png"
    self.assertEqual(absolute_media_url(existing), existing)
