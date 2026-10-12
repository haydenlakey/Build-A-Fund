"""Glossary terms (content/glossary.yaml) and marking them up in Markdown text.

`annotate(text, terms)` wraps the first mention of each term in

    <span class="gl" tabindex="0" data-def="...">term</span>

which the UI styles as a dotted underline whose definition shows on hover and on tap (tapping a
focusable element focuses it, and the definition shows on :focus). LaTeX, code, links, HTML tags and
URLs are left alone.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

GLOSSARY_PATH = Path(__file__).resolve().parent.parent / "content" / "glossary.yaml"

# pieces of Markdown that must never be marked: display/inline maths, code, links, HTML tags, URLs
_PROTECTED = re.compile(r"(\$\$.+?\$\$|\$[^$\n]+\$|`[^`]*`|\[[^\]]*\]\([^)]*\)|<[^>]+>|https?://\S+)", re.S)


@dataclass(frozen=True)
class Term:
    term: str
    definition: str
    aliases: tuple[str, ...] = ()
    article: str = ""
    case: bool = False

    @property
    def key(self) -> str:
        return self.term.lower()


def load_glossary(path: Path | str = GLOSSARY_PATH) -> list[Term]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    out, seen = [], set()
    for d in raw.get("terms", []):
        t = Term(term=d["term"], definition=d["def"].strip(), aliases=tuple(d.get("aliases") or ()),
                 article=d.get("article", ""), case=bool(d.get("case", False)))
        if t.key in seen:
            raise ValueError(f"duplicate glossary term {t.term!r}")
        seen.add(t.key)
        out.append(t)
    return sorted(out, key=lambda t: t.key)


def _matcher(terms: list[Term]) -> tuple[re.Pattern, re.Pattern, dict[str, Term]]:
    """(case-insensitive pattern, case-sensitive pattern, lower-case spelling -> term). Longest first."""
    lookup: dict[str, Term] = {}
    loose, strict = [], []
    for t in terms:
        for s in (t.term, *t.aliases):
            lookup[s.lower()] = t
            (strict if t.case else loose).append(s)

    def pat(words: list[str], flags: int) -> re.Pattern:
        words = sorted(set(words), key=len, reverse=True) or ["(?!x)x"]
        alt = "|".join(re.escape(w) for w in words)
        return re.compile(rf"(?<![\w-])({alt})(s|es)?(?![\w-])", flags)

    return pat(loose, re.I), pat(strict, 0), lookup


def annotate(text: str, terms: list[Term], used: set[str] | None = None) -> str:
    """Mark the first mention of each term (across calls sharing `used`, if given)."""
    if not text or not terms:
        return text
    loose, strict, lookup = _matcher(terms)
    used = set() if used is None else used

    def mark(part: str) -> str:
        hits = sorted([m for p in (strict, loose) for m in p.finditer(part)], key=lambda m: (m.start(), -m.end()))
        out, pos = [], 0
        for m in hits:
            if m.start() < pos:
                continue
            t = lookup[m.group(1).lower()]
            if t.key in used:
                continue
            used.add(t.key)
            out += [part[pos:m.start()],
                    f'<span class="gl" tabindex="0" data-def="{html.escape(t.definition, quote=True)}">{m.group(0)}</span>']
            pos = m.end()
        return "".join(out) + part[pos:]

    pieces = _PROTECTED.split(text)
    return "".join(p if i % 2 else mark(p) for i, p in enumerate(pieces))


def lookup(terms: list[Term], name: str) -> Term | None:
    name = name.lower()
    return next((t for t in terms if t.key == name or name in (a.lower() for a in t.aliases)), None)
