"""Labelled-set keys (`evals/retrieval.jsonl`, evaluation.md §1): `<source_key>::<path>[#<ordinal>]`.

A key matches a chunk of that source when the chunk covers a node **at or under** the labelled path. The path's
segments must appear in order in the node's path, so a tree level the label leaves out still matches
(`CHAPTER III > 23` matches `CHAPTER III > PART I > 23 > (2)`). `#n` selects piece n of a split leaf. An empty path
means any chunk of the source. Paths never include the source title.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LabelKey:
    source_key: str
    path: tuple[str, ...]
    ordinal: int | None

    @classmethod
    def parse(cls, key: str) -> LabelKey:
        source, sep, rest = key.partition("::")
        if not sep or not source:
            raise ValueError(f"label key must look like '<source_key>::<path>': {key!r}")
        path, _, piece = rest.partition("#")
        return cls(source, split_path(path), int(piece) if piece else None)


def split_path(path: str) -> tuple[str, ...]:
    return tuple(s.strip() for s in path.split(" > ") if s.strip())


def _at_or_under(label: tuple[str, ...], node: tuple[str, ...]) -> int | None:
    """Index in `node` where the label's last segment matched (ancestors in order before it), else None."""
    if not label:
        return 0
    for end in range(len(node)):
        if node[end] != label[-1]:
            continue
        it = iter(node[:end])
        if all(seg in it for seg in label[:-1]):
            return end
    return None


def matches(
    key: LabelKey, source_key: str, section_path: str, ordinal: int, node_paths: list[str]
) -> bool:
    if key.source_key != source_key:
        return False
    if key.ordinal is not None:
        node = split_path(section_path)
        end = _at_or_under(key.path, node)
        return end is not None and end == len(node) - 1 and ordinal == key.ordinal
    return any(_at_or_under(key.path, split_path(p)) is not None for p in node_paths)
