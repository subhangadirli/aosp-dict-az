# Azerbaijani Dictionary for FUTO Keyboard

Build a high-quality AOSP binary dictionary (`.dict`) for Azerbaijani autocorrect and word suggestions in FUTO Keyboard.

## Features

- **Multi-source corpora** — merged from 3 Leipzig Corpus datasets:
  - Wikipedia 2021 300K (291,704 words)
  - Wikipedia 2021 1M (583,667 words)  
  - Wikipedia 2016 300K (293,475 words)
  - **Total: 647,591 unique words → top 50,000 selected**

- **Universal boost system** — two-layer word frequency optimization:
  - **Layer 1**: Suffix-pattern multipliers (O(1) per word)
    - Verb infinitives (-mək/-mak): ×1.8
    - Plurals (-lar/-lər): ×1.2
    - Case markers (locative, ablative, genitive, dative): ×1.05–1.1
  - **Layer 2**: Anchor floors for underrepresented words (~90 critical words)
    - Pronouns (mən, sən, o, biz, siz) — ranked ~top-300
    - Common verbs (etmək, olmaq, getmək, etc.) — calibrated for keyboard UX
    - Numbers, days, months
    - Modern tech vocabulary (telefon, internet, kompyuter)

- **Proper Azerbaijani support** — preserves all special characters:
  - ə (schwa), ğ (soft g), ı (dotless i), ö, ü, ç, ş

- **Log-scale normalization** — frequency scores respect Zipf's law distribution:
  - Linear would compress 99% of words into f=1–5
  - Log scale preserves meaningful rank separation across vocabulary

## Files

```
azdictkey/
├── main_az.dict                  # Final compiled binary (332 KB) → ready to use
├── az_wordlist.combined          # Intermediate AOSP format (1 MB)
├── boost.py                      # Universal boost system
├── convert.py                    # Pipeline orchestration
├── corpora/                      # Word frequency sources (not in git)
└── jdk-21/                       # Java runtime (not in git, if system Java unavailable)
```

## Setup

### Requirements
- Python 3.7+
- Java (system `java` or bundled `jdk-21/bin/java`)
- wget (for downloading corpora)

### Installation

```bash
git clone https://github.com/YOUR_USERNAME/azdictkey.git
cd azdictkey
```

### Download corpora

```bash
mkdir -p corpora
cd corpora

# Wikipedia 2021 1M
wget https://downloads.wortschatz-leipzig.de/corpora/aze_wikipedia_2021_1M.tar.gz
tar xzf aze_wikipedia_2021_1M.tar.gz --wildcards "*-words.txt"
rm aze_wikipedia_2021_1M.tar.gz

# Wikipedia 2016 300K
wget https://downloads.wortschatz-leipzig.de/corpora/aze_wikipedia_2016_300K.tar.gz
tar xzf aze_wikipedia_2016_300K.tar.gz --wildcards "*-words.txt"
rm aze_wikipedia_2016_300K.tar.gz

# Wikipedia 2021 300K
wget https://downloads.wortschatz-leipzig.de/corpora/aze_wikipedia_2021_300K.tar.gz
tar xzf aze_wikipedia_2021_300K.tar.gz --wildcards "*-words.txt"
rm aze_wikipedia_2021_300K.tar.gz

cd ..
```

If any URL fails, the pipeline auto-discovers whatever corpora are present — minimum viable is 1 corpus.

## Build

```bash
# Generate az_wordlist.combined (text format)
python3 convert.py

# Compile to binary .dict
java -jar dicttool_aosp.jar makedict -s az_wordlist.combined -d main_az.dict

# Verify output
ls -lh main_az.dict
# Expected: ~330 KB, non-empty
```

## Import into FUTO Keyboard

### Option A: USB (MTP)
1. Connect Android phone via USB
2. Enable file transfer mode (MTP)
3. Copy `main_az.dict` to phone storage (e.g., `Downloads/`)
4. Open FUTO Keyboard on phone
5. Settings → Languages & Models → Azerbaijani → Dictionary → Import → select file

### Option B: ADB
```bash
adb push main_az.dict /sdcard/Download/main_az.dict
# Then import from FUTO Keyboard settings
```

### Option C: Cloud
- Upload to Google Drive / Telegram Saved Messages
- Download on phone
- Import from FUTO Keyboard

## Architecture

### boost.py

Universal boost system replacing hardcoded word lists. Two-layer design:

1. **Suffix rules** — pattern-based multipliers applied in O(1) per word
   - Detects Azerbaijani morphology (verb infinitives, plural, case markers)
   - Multipliers: ×1.05–2.0 depending on underrepresentation in corpora

2. **Anchor floors** — absolute frequency floors for critical words
   - ~90 words with manually calibrated floor values
   - Prevents well-represented words from being pushed down
   - Ensures keyboard UX for pronouns, common verbs, tech vocabulary

### convert.py

Pipeline orchestration:
1. Auto-discovers all `*-words.txt` files in `corpora/`
2. Merges frequencies by summing across sources
3. Injects single-char anchors (`"o"` → 8000) before length filter
4. Applies boost system (suffix rules + anchor floors)
5. Selects top 50,000 words by boosted frequency
6. Normalizes to 1–255 scale using log normalization
7. Writes `az_wordlist.combined` in AOSP format
8. Prints stats and top-10 preview

### Key design decisions

- **Frequency summation** — words appearing in multiple corpora have their freqs summed (correct for overlapping sources)
- **Anchors use max()** — never push well-represented words down
- **Log normalization** — respects Zipf's law; linear would compress 99% into f=1–5
- **Bug fix from old code** — `"o"` pronoun was silently dropped by len<2 filter; now injected explicitly

## Example output

Running `convert.py`:
```
Found 3 corpus source(s):
  corpora/aze_wikipedia_2016_300K/aze_wikipedia_2016_300K-words.txt
  corpora/aze_wikipedia_2021_1M/aze_wikipedia_2021_1M-words.txt
  corpora/aze_wikipedia_2021_300K/aze_wikipedia_2021_300K-words.txt

Loading and merging corpora...
  aze_wikipedia_2016_300K: 293,475 valid words
  aze_wikipedia_2021_1M: 583,667 valid words
  aze_wikipedia_2021_300K: 291,704 valid words
  -> Unique words after merge: 647,591

Single-char anchors injected: 1 (['o'])

Applying boost system...
  Words boosted by suffix multiplier: 296,521
  Anchor floors activated: 53

Selecting top 50,000 words...
  Selected: 50,000 words
  Boosted frequency range: 27 — 647925

Top 10 words (with boost detail):
  və              raw= 647,925  boosted= 647,925
  bu              raw= 223,251  boosted= 223,251
  bir             raw= 211,578  boosted= 211,578
  ilə             raw= 187,706  boosted= 187,706
  də              raw= 117,569  boosted= 117,569
  üçün            raw= 107,528  boosted= 107,528
  olan            raw= 103,168  boosted= 103,168
  sonra           raw=  87,515  boosted=  91,890 [suffix-x1.1]
  ildə            raw=  83,849  boosted=  88,041 [suffix-x1.1]
  isə             raw=  86,030  boosted=  86,030
```

## Testing

After importing into FUTO Keyboard, test:
- Type "m" → autocomplete suggests "mən"
- Type "get" → suggests "getmək"
- Type "telefon" → appears in suggestions

## Troubleshooting

**dicttool version error:**
```bash
java -jar dicttool_aosp.jar makedict -t 2 -s az_wordlist.combined -d main_az.dict
```

**Java not found:**
Either install JDK or download and extract jdk-21 from trash, then use:
```bash
./jdk-21/bin/java -jar dicttool_aosp.jar ...
```

**Corpus download fails:**
The pipeline auto-detects available sources. Download at least one working corpus or use a local corpus file in `corpora/` with name pattern `aze_*-words.txt`.

## License

This project is provided as-is for building Azerbaijani keyboard dictionaries. The Leipzig Corpus data is covered by the Leipzig Corpora Collection license.

## References

- [FUTO Keyboard](https://github.com/reuixjw/futo-keyboard)
- [AOSP Dictionary Tools](https://github.com/remi0s/aosp-dictionary-tools)
- [Leipzig Corpora](https://wortschatz-leipzig.de/)
