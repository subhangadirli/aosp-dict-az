#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Universal boost system for Azerbaijani dictionary.

Two-layer design:
  Layer 1 - SUFFIX_RULES: pattern-based multipliers applied per word O(1)
  Layer 2 - ANCHOR_WORDS: absolute frequency floor for ~55 critical words
             that are systematically underrepresented in written corpora
             (spoken-register pronouns, modern tech vocab, etc.)

Usage:
    from boost import apply_boost, SINGLE_CHAR_ANCHORS

    boosted_freq = apply_boost(word, corpus_freq)
    # SINGLE_CHAR_ANCHORS must be injected before length-filtering in convert.py
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Layer 1: Suffix-based multipliers
# ---------------------------------------------------------------------------
# Each entry: (suffix_string, min_stem_length, multiplier)
#
# min_stem_length = minimum chars that must remain after removing suffix.
# This prevents pathological matches on very short words (e.g. 'da' particle
# must not match as the locative suffix of a 1-char stem).
#
# All matching rules are checked; the HIGHEST multiplier wins (not additive).
# Rules are pre-sorted by suffix length descending so longest-suffix-first
# matching finds the most specific rule.
#
# Rationale:
#   -mək/-mak  (1.8×) Verb infinitives: Wikipedia strongly prefers conjugated
#              forms (edir, oldu…); keyboard users type base forms for
#              autocomplete. Significantly underrepresented.
#   -lar/-lər  (1.2×) Plural nouns: gentle boost so plural forms don't lose
#              out to singulars purely due to frequency splitting.
#   -üçün      (2.0×) Postposition "for/because-of": frequently appears
#              attached to words in the corpus; standalone form ranks lower.
#   -da/-də    (1.1×) Locative case "-da/-də" (at/in): min_stem=3 prevents
#              matching short particles. 'da' the particle (also/too) is 2
#              chars so won't match min_stem=3 requirement.
#   -dan/-dən  (1.1×) Ablative case "from".
#   -ın/-in/-un/-ün (1.05×) Genitive case.
#   -a/-ə      (1.05×) Dative case. Only long stems (min_stem=3).

_RAW_SUFFIX_RULES: list[tuple[str, int, float]] = [
    # (suffix, min_stem_len, multiplier)
    # --- Verb infinitives (highest multiplier) ---
    ("mək", 2, 1.8),
    ("mak", 2, 1.8),
    # --- Postposition ---
    ("üçün", 1, 2.0),
    # --- Plural ---
    ("lar",  2, 1.2),
    ("lər",  2, 1.2),
    # --- Ablative case ---
    ("dan",  3, 1.1),
    ("dən",  3, 1.1),
    # --- Locative case ---
    ("da",   3, 1.1),
    ("də",   3, 1.1),
    # --- Genitive case ---
    ("ının", 3, 1.05),
    ("inin", 3, 1.05),
    ("unun", 3, 1.05),
    ("ünün", 3, 1.05),
    ("ın",   3, 1.05),
    ("in",   3, 1.05),
    ("un",   3, 1.05),
    ("ün",   3, 1.05),
    # --- Dative case ---
    ("a",    3, 1.05),
    ("ə",    3, 1.05),
]

# Pre-sort by suffix length descending: longest match wins when iterating
SUFFIX_RULES: list[tuple[str, int, float]] = sorted(
    _RAW_SUFFIX_RULES, key=lambda r: len(r[0]), reverse=True
)


def get_suffix_multiplier(word: str) -> float:
    """
    Return the highest suffix-based multiplier for word, or 1.0 if none match.
    O(k) where k = len(SUFFIX_RULES) ~ constant 20.
    """
    best = 1.0
    for suffix, min_stem, mult in SUFFIX_RULES:
        if word.endswith(suffix) and len(word) - len(suffix) >= min_stem:
            if mult > best:
                best = mult
    return best


# ---------------------------------------------------------------------------
# Layer 2: Anchor floors — absolute frequency floor for critical words
# ---------------------------------------------------------------------------
# Format: word -> floor_frequency (raw, pre-normalization scale)
#
# Calibrated for 3-corpus merged scale:
#   Wikipedia 2021 300K max freq ~120k → Wikipedia 2016 + 2021 1M add roughly
#   2x more → merged max ~360k for top word (və).
#
# Anchor target: place anchored words approximately in top-300 of merged set.
# top-300 threshold in merged corpus ≈ 3000-5000.
# Highest-priority anchors (pronouns, core verbs) → 8000 (top ~100).
#
# Key: apply_boost uses max(boosted, anchor), so anchors never push a
# well-represented word DOWN — they only lift underrepresented ones.

ANCHOR_WORDS: dict[str, int] = {
    # --- First/second person pronouns (most underrepresented in formal text) ---
    "mən":    8000,   # I
    "sən":    8000,   # you (singular)
    "biz":    6000,   # we
    "siz":    6000,   # you (plural/formal)
    "onlar":  5000,   # they
    "bizim":  4000,   # our
    "sizin":  4000,   # your (plural)
    "mənim":  5000,   # my
    "sənin":  4000,   # your (singular)
    # --- High-frequency particles/conjunctions ---
    "və":     9000,   # and (safety anchor; already very high in corpus)
    "da":     7000,   # also/too (particle, 2 chars — not a suffix match)
    "də":     7000,   # also/too (front vowel harmony variant)
    "ki":     6000,   # that/so that (conjunction)
    "amma":   5000,   # but
    "lakin":  5000,   # however
    "yəni":   4000,   # that is / i.e.
    "həm":    4500,   # both/also
    "isə":    5000,   # if/as for
    "çünki":  4000,   # because
    "əgər":   4000,   # if (conditional)
    "ancaq":  3500,   # only/but
    "hər":    5000,   # every/each
    "heç":    4500,   # any/none
    "daha":   5000,   # more/already
    "artıq":  4500,   # already/more
    # --- Common verbs: infinitive forms underrepresented vs. conjugated ---
    "etmək":    5000,
    "olmaq":    5000,
    "getmək":   4000,
    "gəlmək":   4000,
    "demək":    4500,
    "görmək":   4000,
    "bilmək":   4000,
    "istəmək":  4000,
    "vermək":   3500,
    "almaq":    4000,
    "yazmaq":   3500,
    "oxumaq":   3500,
    "başlamaq": 3000,
    "tapmaq":   3000,
    "çatmaq":   3000,
    "açmaq":    3000,
    "baxmaq":   3000,
    "qalmaq":   3500,
    "keçmək":   3000,
    "döndərmək":2500,
    # --- Numbers ---
    "bir":    5000,   # 1
    "iki":    5000,   # 2
    "üç":     4000,   # 3
    "dörd":   3500,   # 4
    "beş":    3500,   # 5
    "altı":   3000,   # 6
    "yeddi":  3000,   # 7
    "səkkiz": 3000,   # 8
    "doqquz": 3000,   # 9
    "on":     4000,   # 10
    "yüz":    3500,   # 100
    "min":    3500,   # 1000
    "milyon": 3000,   # million
    # --- Common adjectives ---
    "yaxşı":  4000,   # good
    "pis":    3000,   # bad
    "yeni":   3500,   # new
    "köhnə":  3000,   # old
    "böyük":  4000,   # big
    "kiçik":  3500,   # small
    "gözəl":  3500,   # beautiful
    "uzun":   3000,   # long
    "qısa":   3000,   # short
    "çox":    5000,   # many/very
    "az":     4000,   # few/little
    "bütün":  4500,   # all/whole
    "hər":    5000,   # every (duplicate key intentional: same value)
    # --- Common nouns ---
    "adam":   3500,   # person/man
    "insan":  3500,   # person/human
    "ev":     3500,   # house/home
    "iş":     4000,   # work/job
    "su":     3500,   # water
    "vaxt":   3500,   # time
    "gün":    4000,   # day/sun
    "il":     4000,   # year
    "yer":    4000,   # place
    "yol":    3500,   # road/way
    "qapı":   3000,   # door
    "həyat":  3500,   # life
    "dünya":  4000,   # world
    "ölkə":   3500,   # country
    "şəhər":  3500,   # city
    # --- Days of week ---
    "bazar":        3000,
    "bərpazar":     2500,
    "çərşənbə":     3000,
    "cümə":         3000,
    "şənbə":        3000,
    # --- Months ---
    "yanvar":   3000,
    "fevral":   3000,
    "mart":     3000,
    "aprel":    3000,
    "may":      3000,
    "iyun":     3000,
    "iyul":     3000,
    "avqust":   3000,
    "sentyabr": 3000,
    "oktyabr":  3000,
    "noyabr":   3000,
    "dekabr":   3000,
    # --- Modern/tech vocabulary (underrepresented in older corpora) ---
    "telefon":    4000,
    "internet":   4000,
    "kompyuter":  4000,
    "mobil":      3500,
    "proqram":    3000,
    "sayt":       3000,
    "məlumat":    3500,
    "şifrə":      3000,
    "hesab":      3500,
    "fayl":       3000,
    "video":      3000,
    "şəkil":      3500,
    "mesaj":      3500,
    "zəng":       3000,
    "nömrə":      3500,
    "ünvan":      3000,
}

# Single-character words that MUST bypass the min_length=2 filter.
# Injected directly into the frequency dict before corpus loading's length check.
# Bug fix from old code: 'o' was in BOOST_WORDS but silently dropped by len<2.
SINGLE_CHAR_ANCHORS: dict[str, int] = {
    "o": 8000,   # he/she/it — most common Azerbaijani 3rd-person pronoun
                 # Systematically absent from corpus due to len<2 filter.
}


def apply_boost(word: str, corpus_freq: int) -> int:
    """
    Apply the two-layer boost and return the effective frequency.

    Layer 1: multiply corpus_freq by the best-matching suffix rule.
    Layer 2: take max(layer1_result, anchor_floor) if word is in ANCHOR_WORDS.

    Properties:
    - Anchors never push a well-represented word DOWN (max not assignment).
    - Multipliers are proportional: high-freq suffixed words stay ranked
      above low-freq ones with the same suffix.
    - O(k) per word where k ~ 20 suffix rules (effectively O(1)).
    """
    multiplier = get_suffix_multiplier(word)
    boosted = int(corpus_freq * multiplier)

    anchor_floor = ANCHOR_WORDS.get(word)
    if anchor_floor is not None:
        boosted = max(boosted, anchor_floor)

    return boosted
