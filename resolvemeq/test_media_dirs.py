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
