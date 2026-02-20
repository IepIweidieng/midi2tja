#!/usr/bin/env python3

import sys
from mido import MidiFile


def main(*argv: str) -> None:
    fpath_midi = argv[1]
    mid = MidiFile(fpath_midi)

    ticks_per_beat_origin = mid.ticks_per_beat
    print('old ticks_per_beat:', ticks_per_beat_origin)
    if len(argv) > 2:
        ticks_per_beat_target = int(argv[2])
    else:
        ticks_per_beat_target = int(input('enter new ticks_per_beat: '))
    print('new ticks_per_beat:', ticks_per_beat_target)

    mid.ticks_per_beat = ticks_per_beat_target

    if len(argv) > 3:
        tempo_rate = float(argv[3])
    else:
        tempo_rate = float(input('enter bpm rate: '))

    for track in mid.tracks:
        for msg in track:
            msg.time = round(tempo_rate * msg.time * ticks_per_beat_target / ticks_per_beat_origin)
            if msg.type == 'set_tempo':
                msg.tempo = round(msg.tempo / tempo_rate)

    mid.save(fpath_midi + f'.{ticks_per_beat_target}tpb-{tempo_rate}xbpm.mid')

if __name__ == '__main__':
    main(*sys.argv)
