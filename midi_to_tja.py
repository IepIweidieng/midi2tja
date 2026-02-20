#!/usr/bin/env python3

import argparse
from copy import copy
from dataclasses import dataclass
from fractions import Fraction
from math import gcd
import math
import sys
from typing import IO, Any, Callable, Dict, List, Optional, Sequence, Tuple, TypeVar, Union
from mido import Message, MetaMessage, MidiFile, bpm2tempo, tempo2bpm

T = TypeVar('T')


NOTE_SYMBOL = '7'

KNOWN_NOTES = '012345679ABCDFGHI'
LONG_NOTES = '5679DHI'
BALLOON_NOTES = '79D'

def is_known_note(sym: str):
    return sym in KNOWN_NOTES

def is_long_note(sym: str):
    return sym in LONG_NOTES

def is_balloon_note(sym: str):
    return sym in BALLOON_NOTES


def merge_sorted(arr1: Sequence[T], arr2: Sequence[T], key: Callable[[T], Any]) -> List[T]:
    i1 = 0
    i2 = 0
    res: List[T] = []

    while i1 < len(arr1) and i2 < len(arr2):
        if key(arr1[i1]) < key(arr2[i2]):
            res.append(arr1[i1])
            i1 += 1
        else:
            res.append(arr2[i2])
            i2 += 1

    res.extend(arr1[i1:])
    res.extend(arr2[i2:])

    return res


@dataclass
class ChartEvent():
    msg: Union[Message, MetaMessage]
    tick_abs: int
    tick_end_abs: int = -1
    usec_abs: int = -1
    usec_end_abs: int = -1


class ChartState:
    def __init__(self, ticks_per_beat: int) -> None:
        self.ticks_per_beat: int = ticks_per_beat
        self.tsign_upper: int = 4
        self.tsign_lower: int = 4
        self.usec_per_beat: int = bpm2tempo(120)  # TJA: 1/4th notes per min
        self.i_measure_begin: int = 0
        self.tick_measure_begin: int = 0
        self.tick_checkpoint: int = 0
        self.usec_checkpoint: int = 0
        self.balloons: Optional[List[ChartEvent]] = None

    def sync_measure_begin_state(self, event: ChartEvent) -> None:
        if event.tick_abs != self.tick_measure_begin:
            return
        if event.msg.type == 'time_signature':
            self.tsign_upper = event.msg.numerator
            self.tsign_lower = event.msg.denominator
        elif event.msg.type == 'set_tempo':
            self.usec_per_beat = event.msg.tempo

    def get_ticks_per_measure(self) -> int:
        return max(1, self.ticks_per_beat * 4 * self.tsign_upper // self.tsign_lower)

    def get_tick_measure_end(self) -> int:
        return self.tick_measure_begin + self.get_ticks_per_measure()

    def get_usec_at(self, tick: int) -> int:
        return self.usec_checkpoint + (tick - self.tick_checkpoint) * self.usec_per_beat // self.ticks_per_beat

    def advance_usec(self, tick: int) -> None:
        self.usec_checkpoint = self.get_usec_at(tick)
        self.tick_checkpoint = tick

    def advance_measure(self) -> None:
        self.tick_measure_begin = self.get_tick_measure_end()

    def scan_measure(self, events: Sequence[ChartEvent], ievents: range, tja: Optional[IO] = None) -> None:
        tick_beg = self.tick_measure_begin
        tick_end = self.get_tick_measure_end()

        if tja is None:
            def emit(*args: Any, **kwargs: Any) -> None:
                pass
        else:
            def emit(*args: Any, **kwargs: Any) -> None:
                print(*args, **kwargs, file=tja)

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
        is_line_start = True

        def ensure_line_start() -> None:
            nonlocal is_line_start
            if not is_line_start:
                emit('')
            is_line_start = True

        idiv_last = 0
        note_symbol_last = '0'
        for ievent in ievents:
            e = events[ievent]
            tick_rel = e.tick_abs - tick_beg
            idiv = tick_rel // tick_gcd
            if idiv > idiv_last:
                emit(note_symbol_last + (idiv - idiv_last - 1) * '0', end='')
                is_line_start = False
                note_symbol_last = '0'
                idiv_last = idiv

            if e.msg.type == 'time_signature':
                self.tsign_upper = e.msg.numerator
                self.tsign_lower = e.msg.denominator
                ensure_line_start()
                emit(f'#MEASURE {self.tsign_upper}/{self.tsign_lower}')
            elif e.msg.type == 'set_tempo':
                self.advance_usec(e.tick_abs)
                self.usec_per_beat = e.msg.tempo
                ensure_line_start()
                emit(f'#BPMCHANGE {repr(tempo2bpm(self.usec_per_beat))}')
            elif e.msg.type == 'note_on' and not is_long_note(NOTE_SYMBOL):
                note_symbol_last = NOTE_SYMBOL
                e.usec_abs = self.get_usec_at(e.tick_abs)
                e.usec_end_abs = -1  # mark as not ended
            elif e.msg.type == 'note_on' and not (self.balloons is not None and self.balloons[-1].usec_end_abs < 0):
                note_symbol_last = NOTE_SYMBOL
                e.usec_abs = self.get_usec_at(e.tick_abs)
                e.usec_end_abs = -1  # mark as not ended
                if self.balloons is None:
                    self.balloons = []
                self.balloons.append(e)
            elif e.msg.type == 'note_off' and is_long_note(NOTE_SYMBOL) and self.balloons is not None and self.balloons[-1].usec_end_abs < 0:
                note_symbol_last = '8'
                self.balloons[-1].usec_end_abs = self.get_usec_at(e.tick_abs)

        # output measure end
        idiv = (tick_end - tick_beg) // tick_gcd
        if ievents.stop > ievents.start and idiv > idiv_last:
            emit(note_symbol_last + (idiv - idiv_last - 1) * '0', end='')
        emit(',')

    def scan_chart(self, events: List[ChartEvent], tja: Optional[IO] = None) -> None:
        i_measure_begin = 0
        for i, e in enumerate(events):
            # step over measures
            # treat mid-measure time signature changes as next-measure
            while self.get_tick_measure_end() <= e.tick_abs:
                self.scan_measure(events, range(i_measure_begin, i), tja)
                i_measure_begin = i
                self.advance_measure()

            # sync with measure-initial time signature changes
            if e.tick_abs == self.tick_measure_begin:
                if e.msg.type == 'time_signature':
                    self.tsign_upper = e.msg.numerator
                    self.tsign_lower = e.msg.denominator

        # emit events in the last measure
        self.scan_measure(events, range(i_measure_begin, len(events)), tja)


def note_to_hz(note: float) -> float:
    return 440 * math.pow(2, (note - 69) / 12)


def main(*argv: str) -> None:
    global NOTE_SYMBOL

    parser = argparse.ArgumentParser(
        description='Convert MIDI notes to given TJA note')
    parser.add_argument(
        'input_midi', metavar='input.mid', type=str,
        help='source MIDI file')
    parser.add_argument(
        'note', type=str, choices=KNOWN_NOTES, nargs="?", default=NOTE_SYMBOL,
        help='TJA note symbol to convert the MIDI notes into')
    parser.add_argument(
        '--long-gap', '-g', metavar='u/d', type=Fraction, default=Fraction(1, 192),
        help="Fraction of 4 pulses for minimum length and gap of long notes (default: 1/192nd)")
    args = parser.parse_args()

    fpath_midi = args.input_midi
    mid = MidiFile(fpath_midi)

    if len(args.note) == 1 and is_known_note(args.note):
        NOTE_SYMBOL = args.note

    timing_events: List[ChartEvent] = []
    raw_note_events: List[ChartEvent] = []
    ticks_gap = int(4 * mid.ticks_per_beat * args.long_gap) if is_long_note(NOTE_SYMBOL) else 0 # ensure gap for long notes

    for track in mid.tracks:
        tick_abs = 0
        for msg in track:
            tick_abs += msg.time
            if msg.is_meta and msg.type in {'time_signature', 'set_tempo'}:
                timing_events.append(ChartEvent(msg, tick_abs))
            elif msg.type in {'note_on', 'note_off'} and NOTE_SYMBOL != '0':
                raw_note_events.append(ChartEvent(msg, tick_abs))

    timing_events.sort(key=lambda ev: ev.tick_abs)
    raw_note_events.sort(key=lambda ev: ev.tick_abs)

    # simulate polyphonic notes
    note_events: Dict[Tuple[int, int], List[ChartEvent]] = {}
    on_notes: Dict[int, List[ChartEvent]] = {}

    def note_on(msg: Message, tick: int):
        # for hit-type notes, keep 1 chart per track
        channel_on_notes = on_notes.setdefault(msg.channel, [])
        polypos = len(channel_on_notes)
        event = ChartEvent(msg, tick)  # set start
        event.tick_end_abs = tick + ticks_gap # minimum length
        event.usec_end_abs = -1 # mark as unended
        for i, e in enumerate(channel_on_notes):
            e_ = e
            # cut same note
            if e_.msg.note == msg.note:
                e_ = copy(e)
                if e_.usec_end_abs == -1:
                    e_.tick_end_abs = tick
                    e_.usec_end_abs = -2 # mark as ended
                e_.tick_end_abs = max(e_.tick_abs + ticks_gap, min(e_.tick_end_abs, tick - ticks_gap))
            # check if free
            if e_.usec_end_abs != -1 and tick > e_.tick_end_abs:  # free slot found
                polypos = i
                channel_on_notes[i] = event
                # apply note cut
                e.tick_end_abs = e_.tick_end_abs
                e.usec_end_abs = e_.usec_end_abs
                break
        else:
            if is_long_note(NOTE_SYMBOL):
                channel_on_notes.append(event)
        if is_long_note(NOTE_SYMBOL) or polypos == 0:
            note_events.setdefault((msg.channel, polypos), []).append(event)

    def note_off(msg: Message, tick: int):
        channel_on_notes = on_notes.get(msg.channel, None)
        if channel_on_notes is None:
            return
        for i in range(len(channel_on_notes) - 1, -1, -1):
            e = channel_on_notes[i]
            if e.usec_end_abs == -1 and e.msg.note == msg.note:
                e.tick_end_abs = max(e.tick_abs + ticks_gap, tick)  # set end
                e.usec_end_abs = -2 # mark as ended
                return

    for e in raw_note_events:
        if e.msg.type == 'note_on' and e.msg.velocity > 0:
            note_on(e.msg, e.tick_abs)
            if not is_long_note(NOTE_SYMBOL):
                note_off(e.msg, e.tick_abs)
        elif (is_long_note(NOTE_SYMBOL)
            and (e.msg.type == 'note_off'
                or (e.msg.type == 'note_on' and e.msg.velocity <= 0))
            ):
            note_off(e.msg, e.tick_abs)

    # regenerate note-on & off events
    if is_long_note(NOTE_SYMBOL):
        for (ch, poly), events in note_events.items():
            new_events = note_events[(ch, poly)] = []
            for i, e in enumerate(events):
                if e.tick_end_abs > e.tick_abs:
                    new_events.append(e)
                    new_events.append(
                        ChartEvent(
                            Message('note_off', channel=e.msg.channel, note=e.msg.note),
                            e.tick_end_abs))

    # ensure at least one (empty) chart for timing
    if len(note_events) == 0:
        note_events[(0, 0)] = []

    chart_state = ChartState(mid.ticks_per_beat)

    for e in timing_events:
        if e.tick_abs > 0:
            break
        if e.msg.type == 'set_tempo':
            chart_state.usec_per_beat = e.msg.tempo

    with open(f'{fpath_midi}.tja', 'w', encoding='utf-8-sig') as tja:
        print(f'// {argv[0]}', file=tja)
        print(f'TITLE:{fpath_midi}', file=tja)
        print(f'BPM:{repr(tempo2bpm(chart_state.usec_per_beat))}', file=tja)
        print('OFFSET:0', file=tja)

        for (ch, poly), events in note_events.items():
            print('', file=tja)
            print('', file=tja)
            print(f'// Channel {ch}, polyphonic position {poly}', file=tja)

            merged_events = merge_sorted(timing_events, events, key=lambda ev: (
                ev.tick_abs,
                1 if ev.msg.type.startswith('note_') else 0,
            ))

            # scan for balloon count
            if is_balloon_note(NOTE_SYMBOL):
                chart_scan_state = copy(chart_state)
                chart_scan_state.scan_chart(merged_events)

                if chart_scan_state.balloons is not None:
                    balloons = [
                        max(1, round(note_to_hz(e.msg.note) * ((e.usec_end_abs - e.usec_abs) / 1_000_000)))
                        for e in chart_scan_state.balloons]
                    print(f'BALLOON:{",".join((repr(v) for v in balloons))}', file=tja)
                    print('', file=tja)

            print('#START', file=tja)

            # actually print chart
            chart_output_state = copy(chart_state)
            chart_output_state.scan_chart(merged_events, tja)

            print('#END', file=tja)


if __name__ == '__main__':
    main(*sys.argv)
