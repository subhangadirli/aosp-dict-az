# Corpora Directory

Download Azerbaijani word frequency lists from the Leipzig Corpora Collection.

## Available Sources

The pipeline auto-discovers all `*-words.txt` files in this directory. Download any or all of:

### Wikipedia 2021 1M (Recommended)
```bash
wget https://downloads.wortschatz-leipzig.de/corpora/aze_wikipedia_2021_1M.tar.gz
tar xzf aze_wikipedia_2021_1M.tar.gz --wildcards "*-words.txt"
rm aze_wikipedia_2021_1M.tar.gz
```
**Size**: ~175 MB (extracts to 18 MB words.txt)  
**Words**: 583,667 unique

### Wikipedia 2016 300K
```bash
wget https://downloads.wortschatz-leipzig.de/corpora/aze_wikipedia_2016_300K.tar.gz
tar xzf aze_wikipedia_2016_300K.tar.gz --wildcards "*-words.txt"
rm aze_wikipedia_2016_300K.tar.gz
```
**Size**: ~57 MB (extracts to 7.9 MB words.txt)  
**Words**: 293,475 unique

### Wikipedia 2021 300K
```bash
wget https://downloads.wortschatz-leipzig.de/corpora/aze_wikipedia_2021_300K.tar.gz
tar xzf aze_wikipedia_2021_300K.tar.gz --wildcards "*-words.txt"
rm aze_wikipedia_2021_300K.tar.gz
```
**Size**: ~52 MB (extracts to 8.1 MB words.txt)  
**Words**: 291,704 unique

## Format

Each `*-words.txt` file is a tab-separated file with 3 columns:

```
rank<TAB>word<TAB>frequency
1	və	647925
2	bu	223251
3	bir	211578
...
```

The pipeline loads all available sources and merges frequencies by summing across files.

## Minimum viable

The pipeline works with just 1 corpus. If you only want Wikipedia 2021 1M, download that alone.

## Do NOT commit

These files are large (~26 MB total) and are `.gitignore`d. They're regenerable from the Leipzig Corpora servers, so there's no need to version them.
