"""
Translation catalogue tooling — a gettext work-alike implemented in pure Python.

GNU gettext (`xgettext`, `msgmerge`, `msgfmt`) is not installed on Windows and
installing it is a non-starter for most Python teams, yet Django needs two
things to translate a site:

1. a ``.po`` catalogue per language listing every translatable string, and
2. a compiled ``.mo`` binary for each of those catalogues.

This module provides both, plus an extractor, so the whole workflow runs from
``python manage.py`` alone:

    python manage.py i18n_extract     # scan sources -> locale/*/LC_MESSAGES/django.po
    python manage.py i18n_compile     # .po -> .mo

The extractor understands the subset of gettext syntax this project uses:

Python
    gettext("...")            gettext_lazy("...")
    _("...")                  the ``gettext_lazy as _`` alias
    ngettext("one", "many", n)
    pgettext("ctx", "...")    pgettext_lazy("ctx", "...")

Templates
    {% translate "..." %}     {% trans "..." %}
    {% blocktranslate %}...{% endblocktranslate %}
    {% blocktranslate with a=b c=d %}...{% endblocktranslate %}

Anything outside that subset is silently ignored rather than reported as an
error, so the extractor never blocks a commit — run ``i18n_extract --check`` to
assert that no catalogue is stale instead.
"""

from __future__ import annotations

import ast
import re
import struct
from pathlib import Path

from django.utils.translation.template import templatize

# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------

# A single translatable string.
#
#   msgctxt     optional disambiguating context, "" when absent
#   msgid       the source text (Bulgarian in this project)
#   msgid_plural  the plural form, "" when the entry is not plural
#   msgstr      a list; [0] is the singular translation, [1] the plural
Entry = tuple[str, str, str, list[str]]


def _key(entry: Entry) -> tuple[str, str, str]:
    ctx, msgid, plural, _ = entry
    return ctx, msgid, plural


class Catalogue:
    """A parsed ``.po`` file."""

    def __init__(self, entries: list[Entry] | None = None) -> None:
        self.entries: list[Entry] = list(entries or [])

    def __len__(self) -> int:
        return len(self.entries)

    def get(self, ctx: str, msgid: str, plural: str = "") -> Entry | None:
        for entry in self.entries:
            if _key(entry) == (ctx, msgid, plural):
                return entry
        return None


# --------------------------------------------------------------------------
# .po parsing / writing
# --------------------------------------------------------------------------

_PO_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}


def _unescape(raw: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(raw):
        ch = raw[i]
        if ch == "\\" and i + 1 < len(raw):
            nxt = raw[i + 1]
            if nxt in _PO_ESCAPES:
                out.append(_PO_ESCAPES[nxt])
                i += 2
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def _escape(text: str) -> str:
    """Render `text` as the *contents* of a quoted .po string.

    Non-ASCII characters are emitted literally: .po files are UTF-8 and GNU
    gettext does the same, so the catalogues stay readable in the repo.
    """
    out = text.replace("\\", "\\\\").replace('"', '\\"')
    out = out.replace("\t", "\\t").replace("\r", "").replace("\n", "\\n")
    return out


_PO_KEYWORD_RE = re.compile(
    r"^(?P<keyword>msgctxt|msgid_plural|msgid|msgstr(?:\[(?P<index>\d+)\])?)\s+(?P<rest>.*)$"
)


def _po_literal(raw: str) -> str:
    """Unescape the `"..."` payload of a PO string line, or ``""`` if absent."""
    text = raw.strip()
    if not (text.startswith('"') and text.endswith('"')) or len(text) < 2:
        return ""
    return _unescape(text[1:-1])


def parse_po(path: Path) -> Catalogue:
    """Read a ``.po`` file into a :class:`Catalogue`.

    Tolerant by design: anything that is not a keyword or a string continuation
    is ignored, so a hand-edited catalogue with a stray comment still loads
    instead of crashing the whole build.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return Catalogue()

    entries: list[Entry] = []
    ctx = msgid = plural = ""
    msgstrs: list[str] = []
    # Which field a bare `"..."` continuation line appends to, or None when the
    # line is orphaned.
    active: str | None = None
    started = False   # a msgid/msgctxt has been seen for the current entry

    def ensure(index: int) -> None:
        while len(msgstrs) <= index:
            msgstrs.append("")

    def assign(field: str, chunk: str) -> None:
        nonlocal ctx, msgid, plural
        if field == "ctx":
            ctx += chunk
        elif field == "msgid":
            msgid += chunk
        elif field == "plural":
            plural += chunk
        else:
            ensure(int(field.removeprefix("msgstr")))
            msgstrs[int(field.removeprefix("msgstr"))] += chunk

    def flush() -> None:
        nonlocal ctx, msgid, plural, msgstrs, active, started
        if msgid or plural:
            # Plural entries always need at least two msgstr slots so the .mo
            # writer emits a well-formed nplurals=2 table.
            if plural:
                ensure(1)
            entries.append((ctx, msgid, plural, msgstrs))
        ctx = msgid = plural = ""
        msgstrs = []
        active = None
        started = False

    for raw in text.splitlines():
        line = raw.strip()

        if not line:
            flush()
            continue
        if line.startswith("#"):
            # `#~` marks an obsolete entry: drop it and end the current one.
            if line.startswith("#~"):
                flush()
            continue

        if line.startswith('"'):
            if active is not None:
                assign(active, _po_literal(line))
            continue

        match = _PO_KEYWORD_RE.match(line)
        if match is None:
            continue

        keyword = match.group("keyword")
        chunk = _po_literal(match.group("rest"))

        if keyword in ("msgctxt", "msgid"):
            # Either keyword can open an entry; both need the previous one closed
            # first. `msgctxt` always precedes `msgid`, so `started` is what
            # distinguishes opening from continuing.
            if not started:
                flush()
                started = True
            active = "ctx" if keyword == "msgctxt" else "msgid"
        elif keyword == "msgid_plural":
            active = "plural"
        else:
            index = int(match.group("index") or 0)
            ensure(index)
            active = f"msgstr{index}"

        if chunk:
            assign(active, chunk)

    flush()
    return Catalogue(entries)



_PO_HEADER = '''\
# {language_name} translation for the VetLink project.
# Copyright (C) VetLink
# This file is distributed under the same licence as the VetLink package.
#
msgid ""
msgstr ""
"Project-Id-Version: VetLink 1.0\\n"
"Report-Msgid-Bugs-To: \\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Content-Transfer-Encoding: 8bit\\n"
"Language: {code}\\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\\n"
'''


def write_po(
    path: Path,
    catalogue: Catalogue,
    *,
    code: str,
    language_name: str,
    is_source_language: bool = False,
) -> None:
    """Write `catalogue` to `path`, untranslated entries included but commented out.

    Commenting out empty msgstrs (rather than dropping them) is what GNU
    gettext does, and it keeps `i18n_compile`'s coverage report meaningful.

    `is_source_language` suppresses that comment for the language the msgids are
    written in: there, an empty msgstr is the completed state, and labelling it
    "untranslated" would send someone looking for work that does not exist.
    """
    lines = [_PO_HEADER.format(code=code, language_name=language_name)]
    lines.append("")

    for ctx, msgid, plural, msgstrs in sorted(catalogue.entries, key=_key):
        if not msgid:
            continue
        translated = bool(msgstrs and msgstrs[0])
        if not translated and not is_source_language:
            lines.append("# Untranslated — translate and drop the leading '#'.")
        if ctx:
            lines.append(f"msgctxt {_po_str(ctx)}")
        lines.append(f"msgid {_po_str(msgid)}")
        if plural:
            lines.append(f"msgid_plural {_po_str(plural)}")
            for index, value in enumerate(msgstrs or ["", ""]):
                prefix = f"msgstr[{index}]"
                lines.append(f"{prefix} {_po_str(value)}" if translated
                             else f"# {prefix} {_po_str(value)}")
        else:
            lines.append(f"msgstr {_po_str(msgstrs[0] if msgstrs else '')}"
                         if translated else f"# msgstr {_po_str(msgstrs[0] if msgstrs else '')}")
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _po_str(text: str) -> str:
    """Render `text` as a .po string literal, wrapped when it contains newlines."""
    escaped = _escape(text)
    if "\n" not in escaped:
        return f'"{escaped}"'
    chunks = escaped.split("\\n")
    # Re-join with the escape intact so the trailing chunk does not gain one.
    parts = ['"%s\\n"' % chunks[0]]
    parts += ['"%s"' % chunk for chunk in chunks[1:]]
    return "\n".join(parts)


# --------------------------------------------------------------------------
# .mo writing
# --------------------------------------------------------------------------

MO_MAGIC = 0x950412DE
MO_REVISION = 0

#: Django's ``pgettext`` looks a string up as ``context + CONTEXT_SEPARATOR +
#: msgid`` (see ``django.utils.translation.trans_real``), so a message with a
#: context is stored under that exact composite key — *not* separated by NUL.
CONTEXT_SEPARATOR = "\x04"


def write_mo(catalogue: Catalogue, path: Path) -> int:
    """Compile `catalogue` to a binary ``.mo``.

    Returns the number of translated strings written. Untranslated entries are
    skipped rather than written as empty, so gettext falls back to the msgid —
    which is the desired behaviour, because in this project the msgid *is* the
    Bulgarian text.

    Key layout, as required by the format Python's :mod:`gettext` parses:

    * no context, singular  -> ``msgid``
    * context, singular     -> ``msgctxt + "\\x04" + msgid``
    * plural                -> the above with ``"\\x00" + msgid_plural`` appended,
      because ``GNUTranslations._parse`` splits a NUL-bearing key in half to
      recover the two forms.
    """
    table: dict[bytes, str] = {}
    for ctx, msgid, plural, msgstrs in catalogue.entries:
        if not msgid:
            continue
        # An empty context must not leave a leading separator behind, or the key
        # would stop matching a plain `gettext`/`ngettext` lookup.
        prefix = f"{ctx}{CONTEXT_SEPARATOR}" if ctx else ""
        if plural:
            if len(msgstrs) < 2 or not msgstrs[0]:
                continue
            key = f"{prefix}{msgid}\0{plural}"
            value = "\0".join(msgstrs)
        else:
            if not msgstrs or not msgstrs[0]:
                continue
            key = f"{prefix}{msgid}"
            value = msgstrs[0]
        table[key.encode("utf-8")] = value

    # The header entry is mandatory: gettext reads it to learn the charset and
    # the plural rule, and Django refuses to use a catalogue without it.
    header = (
        "Project-Id-Version: VetLink 1.0\n"
        "MIME-Version: 1.0\n"
        "Content-Type: text/plain; charset=UTF-8\n"
        "Content-Transfer-Encoding: 8bit\n"
        "Language: \n"
        "Plural-Forms: nplurals=2; plural=(n != 1);\n"
    )
    table["".encode("utf-8")] = header

    keys = sorted(table)
    values = [table[k] for k in keys]

    count = len(keys)
    # 7 uint32 of file header, then two 8-byte-per-entry tables, then the string
    # data itself. A hashing table is optional; gettext accepts size 0.
    header_size = 28
    key_table_offset = header_size
    value_table_offset = key_table_offset + count * 8
    data_offset = value_table_offset + count * 8

    # Lay the payload out first so each entry's offset is known, then emit the
    # header, the two offset tables and the payload in that order.
    blob = bytearray()
    encoded_keys = [key.decode("utf-8") for key in keys]
    offsets: list[int] = []
    for text in encoded_keys + values:
        encoded = text.encode("utf-8")
        offsets.append(data_offset + len(blob))
        blob += encoded + b"\0"

    output = bytearray()
    output += struct.pack(
        "<IIIIIII", MO_MAGIC, MO_REVISION, count,
        key_table_offset, value_table_offset, 0, data_offset,
    )
    for i, text in enumerate(encoded_keys):
        output += struct.pack("<II", len(text.encode("utf-8")), offsets[i])
    for i, text in enumerate(values):
        output += struct.pack("<II", len(text.encode("utf-8")), offsets[count + i])
    output += blob

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(output))
    return sum(1 for entry in catalogue.entries if entry[3] and entry[3][0])


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------

# Callables imported under a different name, mapped to the canonical function.
_PY_ALIASES = {
    "_": "gettext",
    "gettext": "gettext",
    "gettext_lazy": "gettext",
    "gettext_noop": "gettext_noop",
    "ugettext": "gettext",
    "ngettext": "ngettext",
    "ngettext_lazy": "ngettext",
    "pgettext": "pgettext",
    "pgettext_lazy": "pgettext",
}

_PY_SOURCE_DIRS = ("pets", "accounts", "petcare")
_PY_SOURCE_FILES = ("models.py", "forms.py", "views.py", "admin.py", "urls.py",
                    "apps.py", "context_processors.py", "i18n_tools.py",
                    "templatetags/petcare_tags.py")

_TEMPLATE_SOURCE_DIRS = ("templates",)


class ExtractionError(Exception):
    """A source file could not be scanned for translatable strings."""


def _literal(node: ast.AST) -> str | None:
    """Return the value of a constant string node, else None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def extract_from_python(path: Path) -> list[Entry]:
    """Pull translatable strings out of a Python module via its AST.

    Parsing rather than regexing means a gettext call whose argument is a
    variable is simply not extracted, instead of being captured as garbage.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return []

    found: list[Entry] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        name = _PY_ALIASES.get(_callee_name(node.func))
        if name is None:
            continue

        if name == "gettext":
            msgid = _literal(node.args[0])
            if msgid:
                found.append(("", msgid, "", [""]))
        elif name == "ngettext" and len(node.args) >= 2:
            singular = _literal(node.args[0])
            plural = _literal(node.args[1])
            if singular and plural:
                found.append(("", singular, plural, ["", ""]))
        elif name == "pgettext" and len(node.args) >= 2:
            ctx = _literal(node.args[0])
            msgid = _literal(node.args[1])
            if ctx and msgid:
                found.append((ctx, msgid, "", [""]))

    return found


def _callee_name(func: ast.AST) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _unquote(token: str) -> str:
    body = token[1:-1]
    return body.replace('\\"', '"').replace("\\'", "'").replace("\\\\", "\\")


# `templatize` rewrites a template into gettext calls rendered as Python repr()s,
# e.g. ` gettext(u'...') ` or ` ngettext(u'...', u'...', count) `. The string
# arguments are therefore always well-formed Python literals and can be read back
# exactly; only the trailing `count` of a plural call is a bare identifier, which
# `tail` absorbs.
_TEMPLATIZED_CALL_RE = re.compile(
    r"\b(?P<callee>_|gettext|ngettext|pgettext|npgettext)\("
    r"(?P<args>(?:u?(?:'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")\s*,?\s*)+)"
    r"(?P<tail>[^)]*)\)"
)

_STRING_LITERAL_RE = re.compile(r"u?(?:'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")")


def extract_from_template(path: Path) -> list[Entry]:
    """Pull translatable strings out of a Django template.

    This delegates to Django's own ``templatize`` — the very function
    ``manage.py makemessages`` feeds to xgettext — and then reads the resulting
    gettext calls back out.

    Reimplementing the template grammar here would be a subtle liability:
    ``blocktranslate`` does *not* normalise whitespace, so a body written across
    several lines keeps its newlines and indentation in the msgid, and any
    "helpful" collapsing would produce catalogue keys that never match what the
    template looks up at render time. Sharing the implementation makes the two
    agree by construction, and it also means the extractor raises on a
    ``blocktranslate`` containing another block tag — a mistake the runtime
    rejects too.
    """
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return []

    try:
        templatized = templatize(source, origin=str(path))
    except SyntaxError as exc:
        raise ExtractionError(f"{path}: {exc}") from exc

    found: list[Entry] = []
    for match in _TEMPLATIZED_CALL_RE.finditer(templatized):
        args = [
            ast.literal_eval(token)
            for token in _STRING_LITERAL_RE.findall(match.group("args"))
        ]
        # Dispatch on the callee, not on the argument count: a context-less
        # ngettext also takes two string arguments, so counting them would
        # silently file every plural as a pgettext.
        callee = match.group("callee")
        if callee in ("ngettext", "npgettext"):
            # The two forms are the last two string arguments; the trailing
            # `count` is not one, and `npgettext` prefixes a context.
            if len(args) >= 2:
                ctx = args[0] if callee == "npgettext" else ""
                found.append((ctx, args[-2], args[-1], ["", ""]))
        elif callee == "pgettext" and len(args) >= 2:
            found.append((args[0], args[1], "", [""]))
        elif args:
            found.append(("", args[0], "", [""]))

    return found


# --------------------------------------------------------------------------
# Merge
# --------------------------------------------------------------------------


def merge(found: list[Entry], existing: Catalogue) -> tuple[list[Entry], list[Entry]]:
    """Combine freshly extracted entries with an existing catalogue.

    Returns ``(merged, removed)``. Translations for strings that are still in
    the source are preserved; strings that disappeared are reported so they can
    be deleted by hand. Context changes invalidate a translation, matching
    gettext behaviour.
    """
    translations = {_key(e): e[3] for e in existing.entries}
    merged: list[Entry] = []
    seen: set[tuple[str, str, str]] = set()

    for entry in found:
        key = _key(entry)
        if key in seen:
            continue
        seen.add(key)
        merged.append((*key, translations.get(key, entry[3])))

    removed = [e for e in existing.entries if _key(e) not in seen and e[1]]
    return merged, removed
