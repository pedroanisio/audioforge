# Bach interchange fixtures

Johann Sebastian Bach's BWV 66.6 and BWV 4.8 are public-domain compositions.
These files were exported from the bundled [music21 corpus](https://www.music21.org/music21docs/moduleReference/moduleCorpus.html)
using music21 10.5.0 on 2026-09-06:

```python
from music21 import corpus
for name in ("bwv66.6", "bwv4.8"):
    corpus.parse("bach/" + name).write("musicxml", fp=name + ".musicxml")
```

The generated MusicXML 4.0 files are committed unchanged. They are importer fixtures;
AudioForge's own exports target the separately vendored MusicXML 3.1 schema.
The original encoding and attribution metadata remain in each file.
No network or corpus lookup is needed when running the tests.

Tests compare note starts and tied-note counts per part with music21, then validate
and render the imported spec. Written duration and performed duration are checked
separately: BWV 4.8 contains a repeat, which both render timelines expand. A fermata
has no specified duration in seconds, so import records that missing information
without adding an arbitrary pause. music21 may pad a final measure with a rest;
the comparison uses the last sounding event, preserving the original phrase length.

| File | SHA-256 |
|---|---|
| `bwv4.8.musicxml` | `a8d049dabb570388a75905d96f445905f9df19a84dc97c0e648576584c4f0dd1` |
| `bwv66.6.musicxml` | `2c11892d62242fa77ea6767df95a104c00fd98923d89d70228a839cb0ac03cca` |
