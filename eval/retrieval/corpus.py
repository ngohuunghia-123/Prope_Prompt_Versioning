"""The evaluation corpus: a deterministic slice of ``playgrounds/prompts``.

**Why that directory and not synthetic documents.** The corpus is 375 prompts
written for the same job — instructing an LLM agent — by people who all reached
for the same vocabulary. "You are a senior X specialist. Your expertise spans
A, B, C." repeats across hundreds of files. That near-uniformity is precisely
what breaks a whole-document embedding, and a synthetic corpus of ten unrelated
topics would have hidden it behind scores that look excellent and predict
nothing.

**Selection is deterministic and target-first.** Every prompt named by
``golden.py`` is present, then the remainder fills alphabetically up to the
requested size. Alphabetical fill is not laziness: it pulls in the whole
``agent_*`` block, which is the densest cluster of near-identical documents in
the library and therefore the hardest distractor set available.

Conversion reuses ``seed/converter.py`` — the same offline txt-to-canonical-XML
path the real seed script runs — so the bytes evaluated here are the bytes a
seeded workspace holds.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = PROJECT_ROOT / "playgrounds" / "prompts"
SEED_DIR = PROJECT_ROOT / "seed"

#: Mirrors ``seed_prompts._slug``. Copied rather than imported because importing
#: it drags the seed script's argparse/asyncio entrypoint and its database
#: imports into a module that only needs to name a file.
_NAME_CLEAN = re.compile(r"[^a-z0-9._-]+")
_NAME_TRIM = re.compile(r"^[^a-z0-9]+|[^a-z0-9]+$")


def _load_converter():
    """``seed/converter.py`` as a module, without putting ``seed/`` on the path."""
    spec = importlib.util.spec_from_file_location("_seed_converter", SEED_DIR / "converter.py")
    if spec is None or spec.loader is None:  # pragma: no cover - packaging accident
        raise RuntimeError("seed/converter.py is not importable")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("_seed_converter", module)
    spec.loader.exec_module(module)
    return module


def slug(stem: str) -> str:
    """A filename stem as an A-021 model name, exactly as the seed script writes it."""
    value = _NAME_CLEAN.sub("-", stem.lower())
    value = re.sub(r"-{2,}", "-", value)
    value = _NAME_TRIM.sub("", value)[:63]
    return _NAME_TRIM.sub("", value) or "prompt"


def pretty_title(stem: str) -> str:
    words = re.split(r"[_\-\s]+", stem.strip())
    titled = " ".join(word[:1].upper() + word[1:] for word in words if word)
    return (titled or stem)[:200]


@dataclass(frozen=True, slots=True)
class CorpusItem:
    """One prompt as it will exist in the evaluation workspace."""

    stem: str
    """The filename without its suffix. **The identifier the golden set uses**,
    because it is the one a person can check by opening the file. The database
    never sees it."""

    name: str
    """The ``namespace/name`` leaf the registry stores — ``stem`` lowercased and
    cleaned by :func:`slug`. Search results carry prompt ids; the harness maps
    them back through this."""

    title: str
    purpose: str
    body: str
    """Canonical XML, the same bytes ``create_revision`` would store."""

    raw: str
    """The original file, kept for building duplicate probes."""

    source_file: str


#: The purpose the seed script writes for every imported prompt.
#:
#: A near-constant string across the whole corpus, and reproduced here rather
#: than improved because it is what a seeded workspace actually contains — the
#: state whose search quality is under evaluation. Its effect on ranking is a
#: finding, not something the harness gets to quietly fix.
PURPOSE_TEMPLATE = "Imported prompt library entry ({filename})."


def load_corpus(limit: int, *, required: tuple[str, ...] = ()) -> list[CorpusItem]:
    """The evaluation corpus: `required` stems first, then alphabetical fill.

    ``limit`` counts prompts, not files: anything that fails to convert or
    exceeds the registry's body ceiling is dropped and replaced, so a caller
    asking for 120 gets 120 usable prompts or every usable prompt there is.
    """
    converter = _load_converter()
    from prope.prompt_registry.domain import MAX_BODY_CHARACTERS

    by_stem: dict[str, Path] = {}
    for path in sorted(PROMPTS_DIR.iterdir()):
        if path.suffix.lower() not in {".txt", ".md"} or not path.is_file():
            continue
        by_stem.setdefault(path.stem, path)

    missing = [stem for stem in required if stem not in by_stem]
    if missing:
        raise FileNotFoundError(f"golden set names prompts that do not exist: {missing}")

    ordered = [by_stem[stem] for stem in required]
    ordered += [path for stem, path in sorted(by_stem.items()) if stem not in set(required)]

    items: list[CorpusItem] = []
    seen: set[str] = set()
    for path in ordered:
        if len(items) >= limit:
            break
        raw = path.read_text(encoding="utf-8", errors="ignore")
        try:
            conversion = converter.convert_file(raw, fallback_title=pretty_title(path.stem))
        except Exception:  # a file the deterministic converter cannot shape
            continue
        if len(conversion.xml) > MAX_BODY_CHARACTERS:
            continue
        name = slug(path.stem)
        if name in seen:
            continue
        seen.add(name)
        items.append(
            CorpusItem(
                stem=path.stem,
                name=name,
                title=conversion.title,
                purpose=PURPOSE_TEMPLATE.format(filename=path.name),
                body=conversion.xml,
                raw=raw,
                source_file=path.name,
            )
        )
    return items
