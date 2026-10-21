
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
