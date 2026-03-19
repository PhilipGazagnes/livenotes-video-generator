"""
Build the list of blocks and beat events from a Livenotes JSON song.

A block is a plain dict:
    id, kind ("header"|"countin"|"content"), start_time, duration,
    lyrics, style, chords, countin_beats, bpm, time_num

A beat event is a plain dict:
    t, block_id, chord_group_idx, repeat_idx, measure_idx, beat_idx
"""


def build(song, count_in, anticipation):
    """Return (blocks, beat_events) — both lists are in chronological order."""
    meta     = song['meta']
    prompter = song['prompter']

    bpm      = meta.get('bpm') or 120
    time_num = meta.get('time', {}).get('numerator', 4)

    blocks      = []
    beat_events = []
    block_id    = 0
    current_time = 0.0

    # --- Song header block (no duration, no beat events) ---
    name   = meta.get('name')
    artist = meta.get('artist')
    if name or artist:
        header_text = ' — '.join(x for x in [name, artist] if x)
        blocks.append(_block(block_id, 'header', 0.0, 0.0,
                             header_text, 'default', [], 0, bpm, time_num))
        block_id += 1

    # --- Count-in block ---
    if count_in > 0:
        spb      = 60.0 / bpm
        duration = count_in * spb
        bid      = block_id
        blocks.append(_block(bid, 'countin', 0.0, duration,
                             '', 'default', [], count_in, bpm, time_num))
        for i in range(count_in):
            beat_events.append({
                't': i * spb, 'block_id': bid,
                'chord_group_idx': 0, 'repeat_idx': 0,
                'measure_idx': 0, 'beat_idx': i,
            })
        block_id   += 1
        current_time = duration

    # --- Content blocks from prompter ---
    for item in prompter:
        if item['type'] == 'tempo':
            bpm      = item.get('bpm', bpm)
            time_str = item.get('time', f'{time_num}/4')
            time_num = int(time_str.split('/')[0])
            continue

        if item['type'] != 'content':
            continue

        spb    = 60.0 / bpm
        spm    = spb * time_num
        chords = item['chords']

        total_measures = sum(cg['repeats'] * len(cg['pattern']) for cg in chords)
        duration = total_measures * spm

        bid = block_id
        blocks.append(_block(bid, 'content', current_time, duration,
                             item.get('lyrics', ''), item.get('style', 'default'),
                             chords, 0, bpm, time_num))

        # Beat events: one per beat, per measure, per repetition, per chord group
        t = current_time
        for cg_idx, cg in enumerate(chords):
            for rep_idx in range(cg['repeats']):
                for m_idx in range(len(cg['pattern'])):
                    for b in range(time_num):
                        beat_events.append({
                            't': t + b * spb,
                            'block_id': bid,
                            'chord_group_idx': cg_idx,
                            'repeat_idx': rep_idx,
                            'measure_idx': m_idx,
                            'beat_idx': b,
                        })
                    t += spm

        block_id    += 1
        current_time += duration

    beat_events.sort(key=lambda e: e['t'])
    return blocks, beat_events


def _block(bid, kind, start, duration, lyrics, style, chords, countin_beats, bpm, time_num):
    return {
        'id':            bid,
        'kind':          kind,
        'start_time':    start,
        'duration':      duration,
        'lyrics':        lyrics,
        'style':         style,
        'chords':        chords,
        'countin_beats': countin_beats,
        'bpm':           bpm,
        'time_num':      time_num,
    }
