# midi2tja

## Requirement:

* Python: 3.7+
* mido: 1.3.3+

## Tools

* `MIDI_Timing_dump.py`: Simply dump timing info from MIDI file.
  * usage: `python MIDI_Timing_dump.py filename.mid`
* `MIDI_Timing_to_TJA.py`: Generate timed TJA template from a MIDI file.
  * usage: `python MIDI_Timing_to_TJA.py filename.mid`
* `MIDI_to_TJA_balloon.py`: Convert MIDI notes to tuned TJA balloons, with channels or polyphony split to separate sub-charts. Intended for Peepo Drum Kit v1.2+.
  * usage: `python MIDI_to_TJA_balloon.py filename.mid`

## Features

* [x] Supports any MIDI clock rate (pulses per quarter note; PPQ)
* [x] Supports mid-measure timing commands
  * Mid-measure time signature events are treated as at the start of the next measure.
* [x] Tick-based conversion precision
* [x] Microsecond precision for tracking Balloon timestamps

## TODOs

* [ ] Unify code, with function switches
* [ ] Hit-mode: Convert MIDI note to hit-type TJA notes
* [ ] TJA to MIDI conversion, especially for Bongo game mode

