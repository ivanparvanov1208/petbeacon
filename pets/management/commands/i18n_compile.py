"""Compile ``locale/*/LC_MESSAGES/django.po`` into ``django.mo``.

A pure-Python stand-in for ``manage.py compilemessages`` that does not need GNU
gettext. Django only ever reads the compiled ``.mo``, so this must be run for
every catalogue that changed.
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from pets import i18n_tools


class Command(BaseCommand):
    help = "Compile .po catalogues into .mo binaries."

    def handle(self, *args, **options):
        base = Path(settings.BASE_DIR)
        for code, name in settings.LANGUAGES:
            po_path = base / "locale" / code / "LC_MESSAGES" / "django.po"
            if not po_path.exists():
                self.stdout.write(
                    self.style.WARNING(f"  {code}: no catalogue at {po_path.relative_to(base)}")
                )
                continue

            catalogue = i18n_tools.parse_po(po_path)
            if not len(catalogue):
                self.stdout.write(self.style.ERROR(f"  {code}: {po_path.name} is empty"))
                continue

            mo_path = po_path.with_suffix(".mo")
            translated = i18n_tools.write_mo(catalogue, mo_path)
            total = len(catalogue)

            if code == settings.LANGUAGE_CODE:
                # The source language stores its text *as* the msgid, so every
                # msgstr is legitimately empty and gettext falls back to the
                # msgid. Reporting that as "0% translated" would be alarming
                # and wrong.
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  {code} ({name}): source language, {total} strings "
                        f"fall back to their msgid -> {mo_path.relative_to(base)}"
                    )
                )
                continue

            percent = round(100 * translated / total) if total else 100
            style = self.style.SUCCESS if translated == total else self.style.WARNING
            self.stdout.write(
                style(f"  {code} ({name}): {translated}/{total} strings ({percent}%) -> "
                      f"{mo_path.relative_to(base)}")
            )
