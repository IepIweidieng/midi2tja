from math import gcd
import sys
from typing import IO, List, NamedTuple, Sequence
from mido import MetaMessage, MidiFile, tempo2bpm

class TmEvent(NamedTuple):
    tick_abs: int
    msg: MetaMessage

class TmState:
    def __init__(self, ticks_per_beat: int) -> None:
        self.ticks_per_beat: int = ticks_per_beat
        self.tsign_upper: int = 4
        self.tsign_lower: int = 4
        self.bpm: float = 120 # TJA: 1/4th notes per min
        self.i_measure_begin: int = 0
        self.tick_measure_begin: int = 0

    def sync_measure_begin_state(self, event: TmEvent) -> None:
        (tick_abs, msg) = event
        if tick_abs != self.tick_measure_begin:
            return
        if msg.type == 'time_signature':
            self.tsign_upper = msg.numerator
            self.tsign_lower = msg.denominator
        elif msg.type == 'set_tempo':
            self.bpm = tempo2bpm(msg.tempo)

    def get_ticks_per_measure(self) -> int:
        return max(1, self.ticks_per_beat * 4 * self.tsign_upper // self.tsign_lower)

    def get_tick_measure_end(self) -> int:
        return self.tick_measure_begin + self.get_ticks_per_measure()

    def advance_measure(self) -> None:
        self.tick_measure_begin = self.get_tick_measure_end()


def emit_measure(tm_state: TmState, events: Sequence[TmEvent], ievents: range, tja: IO) -> None:
    tick_beg = tm_state.tick_measure_begin
    tick_end = tm_state.get_tick_measure_end()

    # notice that the tick per measure is fixed within a measure
    tick_rels: List[int] = [
        events[i].tick_abs - tick_beg
        for i in ievents
        if events[i].tick_abs > tick_beg
    ] + [tick_end - tick_beg]

    # remove duplications
    l = 0
    for r in range(1, len(tick_rels)):
        if tick_rels[r] != tick_rels[l]:
            l += 1
            tick_rels[l] = tick_rels[r]
    del tick_rels[l + 1:]

    tick_gcd = gcd(*tick_rels)

    # output events
    idiv_last = 0
    for i in ievents:
        (tick_abs, msg) = events[i]
        idiv = (tick_abs - tick_beg) // tick_gcd
        if idiv > idiv_last:
            print((idiv - idiv_last) * '0', file=tja)
        idiv_last = idiv
        if msg.type == 'time_signature':
            tm_state.tsign_upper = msg.numerator
            tm_state.tsign_lower = msg.denominator
            print(f'#MEASURE {tm_state.tsign_upper}/{tm_state.tsign_lower}', file=tja)
        elif msg.type == 'set_tempo':
            tm_state.bpm = tempo2bpm(msg.tempo)
            print(f'#BPMCHANGE {repr(tm_state.bpm)}', file=tja)

    # output measure end
    if idiv_last != 0:
        ndivs = (tick_end - tick_beg) // tick_gcd
        if idiv_last < ndivs:
            print((ndivs - idiv_last) * '0', end='', file=tja)
    print(',', file=tja)


def main(*argv: str) -> None:
    fpath_midi = argv[1]
    mid = MidiFile(fpath_midi)

    timing_events: List[TmEvent] = []

    for track in mid.tracks:
        tick = 0
        for msg in track:
            tick += msg.time
            if msg.is_meta and msg.type in {'time_signature', 'set_tempo'}:
                timing_events.append(TmEvent(tick, msg))

    timing_events.sort(key=lambda ev: ev.tick_abs)

    tm_state = TmState(mid.ticks_per_beat)

    for (tick_abs, msg) in timing_events:
        if tick_abs > 0:
            break
        if msg.type == 'set_tempo':
            tm_state.bpm = tempo2bpm(msg.tempo)

    with open(f'{fpath_midi}.tja', 'w', encoding='utf-8-sig') as tja:
        print(f'// {argv[0]}', file=tja)
        print(f'TITLE:{fpath_midi}', file=tja)
        print(f'BPM:{repr(tm_state.bpm)}', file=tja)
        print('OFFSET:0', file=tja)
        print('', file=tja)

        print('#START', file=tja)

        i_measure_begin = 0
        for i, (tick_abs, msg) in enumerate(timing_events):
            # step over measures
            # treat mid-measure time signature changes as next-measure
            while tm_state.get_tick_measure_end() <= tick_abs:
                emit_measure(tm_state, timing_events, range(i_measure_begin, i), tja)
                i_measure_begin = i
                tm_state.advance_measure()

            # sync with measure-initial time signature changes
            if tick_abs == tm_state.tick_measure_begin:
                if msg.type == 'time_signature':
                    tm_state.tsign_upper = msg.numerator
                    tm_state.tsign_lower = msg.denominator

        # emit events in the last measure
        emit_measure(tm_state, timing_events, range(i_measure_begin, len(timing_events)), tja)

        print('#END', file=tja)


if __name__ == '__main__':
    main(*sys.argv)
