
from __future__ import annotations

# A gettext work-alike in pure Python: GNU gettext is not available on
# Windows, and Django needs both .po catalogues and compiled .mo files.
import ast
import re
import struct
from pathlib import Path

from django.utils.translation.template import templatize


Entry = tuple[str, str, str, list[str]]


def _key(entry: Entry) -> tuple[str, str, str]:
    ctx, msgid, plural, _ = entry
    return ctx, msgid, plural


class Catalogue:

    def __init__(self, entries: list[Entry] | None = None) -> None:
        self.entries: list[Entry] = list(entries or [])

    def __len__(self) -> int:
        return len(self.entries)

    def get(self, ctx: str, msgid: str, plural: str = "") -> Entry | None:
        for entry in self.entries:
            if _key(entry) == (ctx, msgid, plural):
                return entry
        return None


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
    out = text.replace("\\", "\\\\").replace('"', '\\"')
    out = out.replace("\t", "\\t").replace("\r", "").replace("\n", "\\n")
    return out


_PO_KEYWORD_RE = re.compile(
    r"^(?P<keyword>msgctxt|msgid_plural|msgid|msgstr(?:\[(?P<index>\d+)\])?)\s+(?P<rest>.*)$"
)


def _po_literal(raw: str) -> str:
    text = raw.strip()
    if not (text.startswith('"') and text.endswith('"')) or len(text) < 2:
        return ""
    return _unescape(text[1:-1])


def parse_po(path: Path) -> Catalogue:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return Catalogue()

    entries: list[Entry] = []
    ctx = msgid = plural = ""
    msgstrs: list[str] = []
    active: str | None = None
    started = False

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
# {language_name} translation for the PetBeacon project.
# Copyright (C) PetBeacon
# This file is distributed under the same licence as the PetBeacon package.
#
msgid ""
msgstr ""
"Project-Id-Version: PetBeacon 1.0\\n"
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
    escaped = _escape(text)
    if "\n" not in escaped:
        return f'"{escaped}"'
    chunks = escaped.split("\\n")
    parts = ['"%s\\n"' % chunks[0]]
    parts += ['"%s"' % chunk for chunk in chunks[1:]]
    return "\n".join(parts)


MO_MAGIC = 0x950412DE
MO_REVISION = 0

CONTEXT_SEPARATOR = "\x04"


def write_mo(catalogue: Catalogue, path: Path) -> int:
    table: dict[bytes, str] = {}
    for ctx, msgid, plural, msgstrs in catalogue.entries:
        if not msgid:
            continue
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

    header = (
        "Project-Id-Version: PetBeacon 1.0\n"
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
    header_size = 28
    key_table_offset = header_size
    value_table_offset = key_table_offset + count * 8
    data_offset = value_table_offset + count * 8

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
    pass


def _literal(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def extract_from_python(path: Path) -> list[Entry]:
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


_TEMPLATIZED_CALL_RE = re.compile(
    r"\b(?P<callee>_|gettext|ngettext|pgettext|npgettext)\("
    r"(?P<args>(?:u?(?:'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")\s*,?\s*)+)"
    r"(?P<tail>[^)]*)\)"
)

_STRING_LITERAL_RE = re.compile(r"u?(?:'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")")


def extract_from_template(path: Path) -> list[Entry]:
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
        callee = match.group("callee")
        if callee in ("ngettext", "npgettext"):
            if len(args) >= 2:
                ctx = args[0] if callee == "npgettext" else ""
                found.append((ctx, args[-2], args[-1], ["", ""]))
        elif callee == "pgettext" and len(args) >= 2:
            found.append((args[0], args[1], "", [""]))
        elif args:
            found.append(("", args[0], "", [""]))

    return found


def merge(found: list[Entry], existing: Catalogue) -> tuple[list[Entry], list[Entry]]:
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
