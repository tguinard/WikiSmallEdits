This project is for extracting small edits from Wikipedia's edit history. I originally designed this for Turkish, as part of my [master's thesis](https://digital.lib.washington.edu/researchworks/handle/1773/47616), but it can be used for any language with space separated words (sorry, Chinese). 

A small edit is where no more than n consecutive space-separated tokens are changed (set to 3 by default)

## Dependency

This project depends on [mwparserfromhell](https://github.com/earwig/mwparserfromhell). Please install it first

## Set language specific parameters (for non-Turkish)

In settings.json, change 

    "references": "Kaynakça" 

to 

    "references": "References"
    
(for English). Use whatever the title of [this](https://en.wikipedia.org/wiki/Turkey#References) [section](https://tr.wikipedia.org/wiki/T%C3%BCrkiye#Kaynak%C3%A7a) is in your language

## Running

Download xxwiki-latest-pages-meta-history.xml.bz2 from https://dumps.wikimedia.org/xxwiki/latest/, where "xx" is the language code, e.g. "tr" (Turkish), "en" (English)

Split the .bz2 file into multiple files (so we don't have to reprocess all the data if the python program crashes unexpectedly). If you are feeling brave, you can skip this step

    splitBz2.py path/to/xxwiki-latest-pages-meta-history.xml.bz2 outputFolder

Extract small edits

    bigdiff.py path/to/input.bz2 path/to/output.json

Filter for only final small edits (will remove edits that are likely mistakes, vandalism, frequently updated figures, etc.)

    dedup.py inputFolder outputFolder
