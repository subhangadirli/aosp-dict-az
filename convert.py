#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build az_wordlist.combined from all Leipzig corpora in corpora/.

Pipeline:
  1. Discover corpus *-words.txt files via glob (auto-detects all sources)
  2. Merge frequencies across sources (sum for overlapping words)
  3. Inject SINGLE_CHAR_ANCHORS before any length filter
  4. Apply universal boost (suffix multipliers + anchor floors)
  5. Select top MAX_WORDS by boosted frequency
  6. Normalize frequencies to 1-255 scale
  7. Write az_wordlist.combined in AOSP combined format
  8. Print stats and top-10 preview

Output format:
  dictionary=main:az,locale=az,description=Azerbaijani,date=TIMESTAMP,version=19
  word=WORD,f=FREQUENCY
  ...
"""
from __future__ import annotations

import heapq
import time
from pathlib import Path

from boost import ANCHOR_WORDS, SINGLE_CHAR_ANCHORS, apply_boost, get_suffix_multiplier

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
CORPORA_DIR  = PROJECT_ROOT / "corpora"
OUTPUT_FILE  = PROJECT_ROOT / "az_wordlist.combined"

MAX_WORDS    = 50_000
MIN_WORD_LEN = 2

DICT_NAME    = "main"
DICT_LOCALE  = "az"
DICT_DESC    = "Azerbaijani"
DICT_VERSION = 19

# Full Azerbaijani Latin alphabet (a-z plus special chars)
AZ_LETTERS: frozenset[str] = frozenset("abcçdeəfgğhxıijkqlmnoöprsştuüvyz")


# ---------------------------------------------------------------------------
# Word validation
# ---------------------------------------------------------------------------

def _is_valid_word(word: str, min_length: int = MIN_WORD_LEN) -> bool:
    """
    Return True if word is at least min_length chars and contains only
    Azerbaijani Latin alphabet letters (no digits, punctuation, spaces).
    """
    if len(word) < min_length:
        return False
    return all(ch in AZ_LETTERS for ch in word)


# ---------------------------------------------------------------------------
# Corpus discovery and loading
# ---------------------------------------------------------------------------

def discover_corpora(corpora_dir: Path) -> list[Path]:
    """
    Find all *-words.txt files under corpora_dir.
    Sorted by path for deterministic ordering.
    """
    return sorted(corpora_dir.glob("**/*-words.txt"))


def load_corpus(words_file: Path) -> tuple[dict[str, int], int, int]:
    """
    Load a single Leipzig TSV corpus file (rank TAB word TAB frequency).

    Returns:
        (freq_dict, total_lines_read, lines_skipped)
        freq_dict maps canonical (casefolded+stripped) valid AZ words to freq.
        Words appearing multiple times in the same file have their freqs summed.
    """
    result: dict[str, int] = {}
    total = 0
    skipped = 0

    with open(words_file, encoding="utf-8") as fh:
        for line in fh:
            total += 1
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 3:
                skipped += 1
                continue
            _, word, freq_str = parts
            try:
                freq = int(freq_str)
            except ValueError:
                skipped += 1
                continue

            canonical = word.casefold().strip()
            if not _is_valid_word(canonical):
                continue

            result[canonical] = result.get(canonical, 0) + freq

    return result, total, skipped


def merge_corpora(corpus_files: list[Path]) -> tuple[dict[str, int], list[dict]]:
    """
    Load all corpus files and merge frequencies by summing across sources.

    Summation is semantically correct: a word appearing in 3 corpora is
    genuinely more frequent in the language than one appearing in only 1.

    Returns:
        (merged_freq_dict, stats_list)
    """
    merged: dict[str, int] = {}
    stats: list[dict] = []

    for corpus_file in corpus_files:
        corpus, total_lines, skipped = load_corpus(corpus_file)
        source_name = corpus_file.parent.name
        stats.append({
            "name":        source_name,
            "unique_words": len(corpus),
            "total_lines":  total_lines,
            "skipped":      skipped,
        })
        for word, freq in corpus.items():
            merged[word] = merged.get(word, 0) + freq

    return merged, stats


# ---------------------------------------------------------------------------
# Boost application
# ---------------------------------------------------------------------------

def inject_single_char_anchors(freq_dict: dict[str, int]) -> int:
    """
    Inject SINGLE_CHAR_ANCHORS into freq_dict, bypassing the min_length filter.
    Uses max() so an existing corpus entry is only raised, never lowered.
    Returns count of anchors injected.
    """
    for word, floor in SINGLE_CHAR_ANCHORS.items():
        freq_dict[word] = max(freq_dict.get(word, 0), floor)
    return len(SINGLE_CHAR_ANCHORS)


def apply_all_boosts(freq_dict: dict[str, int]) -> dict[str, int]:
    """
    Apply the universal boost system to every word.
    Returns a new dict with boosted frequencies.
    """
    return {word: apply_boost(word, freq) for word, freq in freq_dict.items()}


# ---------------------------------------------------------------------------
# Top-N selection
# ---------------------------------------------------------------------------

def select_top_words(freq_dict: dict[str, int], limit: int) -> list[tuple[str, int]]:
    """
    Return up to `limit` (word, freq) pairs sorted descending by frequency.
    Uses heapq.nlargest — O(n log k) which is much faster than full sort
    when limit << len(freq_dict).
    """
    if limit >= len(freq_dict):
        return sorted(freq_dict.items(), key=lambda kv: kv[1], reverse=True)
    return heapq.nlargest(limit, freq_dict.items(), key=lambda kv: kv[1])


# ---------------------------------------------------------------------------
# Frequency normalization
# ---------------------------------------------------------------------------

def normalize_frequency(freq: int, min_freq: int, max_freq: int) -> int:
    """
    Map raw frequency to 1-255 scale using logarithmic normalization.

    Word frequencies follow Zipf's law (power law distribution). Linear
    normalization would compress 99% of the vocabulary into f=1-5 because
    the top word dominates. Log scale preserves meaningful rank separation
    across the entire vocabulary.

    f(w) = 1 + (log(freq) - log(min_freq)) / (log(max_freq) - log(min_freq)) * 254
    """
    import math
    if max_freq <= min_freq or freq <= 0:
        return 128
    log_min = math.log(max(1, min_freq))
    log_max = math.log(max_freq)
    if log_max <= log_min:
        return 128
    log_freq = math.log(max(1, freq))
    return max(1, min(255, int(1 + (log_freq - log_min) / (log_max - log_min) * 254)))


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_wordlist(output_path: Path, top_words: list[tuple[str, int]]) -> int:
    """
    Write az_wordlist.combined in AOSP combined format.
    Returns number of word entries written.
    """
    if not top_words:
        raise ValueError("top_words is empty — nothing to write")

    timestamp = int(time.time())
    max_freq = top_words[0][1]
    min_freq = top_words[-1][1]

    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(
            f"dictionary={DICT_NAME}:{DICT_LOCALE},"
            f"locale={DICT_LOCALE},"
            f"description={DICT_DESC},"
            f"date={timestamp},"
            f"version={DICT_VERSION}\n"
        )
        for word, freq in top_words:
            norm = normalize_frequency(freq, min_freq, max_freq)
            fh.write(f"word={word},f={norm}\n")

    return len(top_words)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("Azerbaijani Dictionary Builder")
    print("=" * 60)

    # 1. Discover corpora
    corpus_files = discover_corpora(CORPORA_DIR)
    if not corpus_files:
        print(f"\nERROR: No *-words.txt files found in {CORPORA_DIR}")
        raise SystemExit(1)

    print(f"\nFound {len(corpus_files)} corpus source(s):")
    for cf in corpus_files:
        print(f"  {cf.relative_to(PROJECT_ROOT)}")

    # 2. Load and merge corpora
    print("\nLoading and merging corpora...")
    merged, corpus_stats = merge_corpora(corpus_files)
    for s in corpus_stats:
        print(
            f"  {s['name']}: {s['unique_words']:,} valid words "
            f"({s['total_lines']:,} lines, {s['skipped']} skipped)"
        )
    print(f"  -> Unique words after merge: {len(merged):,}")

    # 3. Inject single-char anchors (bypasses length filter)
    n_injected = inject_single_char_anchors(merged)
    print(f"\nSingle-char anchors injected: {n_injected} "
          f"({list(SINGLE_CHAR_ANCHORS.keys())})")

    # 4. Apply universal boost
    print("\nApplying boost system...")
    boosted = apply_all_boosts(merged)

    # Boost stats
    n_suffix_boosted = sum(
        1 for w, f in merged.items()
        if get_suffix_multiplier(w) > 1.0
    )
    n_anchor_activated = sum(
        1 for w in ANCHOR_WORDS
        if w in merged and boosted.get(w, 0) > int(merged[w] * get_suffix_multiplier(w))
    )
    print(f"  Words boosted by suffix multiplier: {n_suffix_boosted:,}")
    print(f"  Anchor floors activated (word raised above suffix result): {n_anchor_activated}")

    # 5. Select top MAX_WORDS
    print(f"\nSelecting top {MAX_WORDS:,} words...")
    top = select_top_words(boosted, MAX_WORDS)
    if not top:
        print("ERROR: No valid words after boost and selection!")
        raise SystemExit(1)
    print(f"  Selected: {len(top):,} words")
    print(f"  Boosted frequency range: {top[-1][1]} — {top[0][1]}")

    # 6 + 7. Normalize and write
    print(f"\nWriting {OUTPUT_FILE.name}...")
    n_written = write_wordlist(OUTPUT_FILE, top)
    print(f"  Written: {n_written:,} entries")
    print(f"  File: {OUTPUT_FILE}")

    # 8. Verification preview
    print("\nFirst 6 lines of output file:")
    with open(OUTPUT_FILE, encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if i >= 6:
                break
            print(f"  {line.rstrip()}")

    print("\nTop 10 words (with boost detail):")
    for word, boosted_freq in top[:10]:
        raw = merged.get(word, 0)
        mult = get_suffix_multiplier(word)
        anchor = ANCHOR_WORDS.get(word)
        if word in SINGLE_CHAR_ANCHORS:
            tag = f" [single-char-anchor={SINGLE_CHAR_ANCHORS[word]}]"
        elif anchor and boosted_freq == anchor:
            tag = f" [anchor={anchor}]"
        elif mult > 1.0:
            tag = f" [suffix-x{mult:.1f}]"
        else:
            tag = ""
        print(f"  {word:15s} raw={raw:>8,}  boosted={boosted_freq:>8,}{tag}")

    print("\nDone!")


if __name__ == "__main__":
    main()
