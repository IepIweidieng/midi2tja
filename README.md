# midi2tja

## Requirement:

* Python: 3.7+
* mido: 1.3.3+

## Tools

* `MIDI_Timing_dump.py`: Simply dump timing info from MIDI file.
  * usage: `python MIDI_Timing_dump.py filename.mid`
* `MIDI_to_TJA.py`: Convert MIDI notes to given TJA note. Channels or polyphony notes are split to separate sub-charts, intended for Peepo Drum Kit v1.2+.
  * usage: `python MIDI_to_TJA.py filename.mid X`
    * `X` is a TJA note symbol, defaults to `7`.
    * For getting a template TJA without notes, use `0`.
    * For hit-types note, use one of `1`, `2`, `3`, `4`, `A`, `B`, `C`, `F`, `G`.
    * For non-balloon drumrolls, use one of `5`, `6`, `H`, `I`.
    * For balloon, use one of `7`, `9`, `D`. The balloons are pitch-tuned
* `midi_reclock.py`: Change the clock rate and BPM of the MIDI file, while keeping the play speed unchanged.
  * usage: `python midi_reclock.py filename.mid ppq bpmrate`
    * If `ppq` and `bpmrate` are not given, user will be prompted to input their value.

## Features

* [x] Supports any MIDI clock rate (pulses per quarter note; PPQ)
* [x] Supports mid-measure timing commands
  * Mid-measure time signature events are treated as at the start of the next measure.
* [x] Tick-based conversion precision
* [x] Microsecond precision for tracking Balloon timestamps

## TODOs

* [x] Unify code, with function switches
* [x] Hit-mode: Convert MIDI note to hit-type TJA notes
* [ ] TJA to MIDI conversion, especially for Bongo game mode

