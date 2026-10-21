
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from pets import i18n_tools


class Command(BaseCommand):
    help = "Extract translatable strings into locale/<lang>/LC_MESSAGES/django.po."

    def add_arguments(self, parser):
        parser.add_argument(
            "--check",
            action="store_true",
            help="Exit non-zero if any catalogue is missing strings, instead of writing.",
        )

    def handle(self, *args, **options):
        check_only = options["check"]
        base = Path(settings.BASE_DIR)
        found = self._collect(base)
        if not found:
            raise CommandError("No translatable strings were found. Check the source paths.")

        self.stdout.write(f"Extracted {len(found)} unique strings.")

        stale = False
        for code, name in settings.LANGUAGES:
            po_path = base / "locale" / code / "LC_MESSAGES" / "django.po"
            existing = i18n_tools.parse_po(po_path)
            merged, removed = i18n_tools.merge(found, existing)

            if check_only:
                if code == settings.LANGUAGE_CODE:
                    pending = removed
                    label = f"{len(removed)} obsolete"
                else:
                    missing = [e for e in merged if not e[3] or not e[3][0]]
                    pending = missing + removed
                    label = (
                        f"{len(missing)} untranslated, {len(removed)} obsolete"
                    )
                if pending:
                    stale = True
                    self.stdout.write(
                        self.style.WARNING(f"  {code}: {label}")
                    )
                else:
                    self.stdout.write(self.style.SUCCESS(f"  {code}: up to date"))
                continue

            i18n_tools.write_po(
                po_path,
                i18n_tools.Catalogue(merged),
                code=code,
                language_name=name,
                is_source_language=(code == settings.LANGUAGE_CODE),
            )
            translated = sum(1 for e in merged if e[3] and e[3][0])
            self.stdout.write(
                f"  {code} ({name}): {len(merged)} strings, {translated} translated -> "
                f"{po_path.relative_to(base)}"
            )
            for entry in removed:
                self.stdout.write(self.style.WARNING(f"    obsolete: {entry[1]!r}"))

        if check_only and stale:
            raise CommandError(
                "Translation catalogues are out of date. Run: python manage.py i18n_extract"
            )

    def _collect(self, base: Path) -> list[i18n_tools.Entry]:
        found: list[i18n_tools.Entry] = []
        seen: set[tuple[str, str, str]] = set()

        for directory, patterns in (
            (i18n_tools._PY_SOURCE_DIRS, i18n_tools._PY_SOURCE_FILES),
            (i18n_tools._TEMPLATE_SOURCE_DIRS, ("**/*.html",)),
        ):
            for name in directory:
                root = base / name
                if not root.is_dir():
                    continue
                if patterns == i18n_tools._PY_SOURCE_FILES:
                    candidates = [root / f for f in patterns]
                else:
                    candidates = sorted(root.glob(patterns[0]))

                for path in candidates:
                    if not path.is_file():
                        continue
                    if path.suffix == ".py":
                        entries = i18n_tools.extract_from_python(path)
                    else:
                        entries = i18n_tools.extract_from_template(path)
                    for entry in entries:
                        key = (entry[0], entry[1], entry[2])
                        if key not in seen:
                            seen.add(key)
                            found.append(entry)

        return found
