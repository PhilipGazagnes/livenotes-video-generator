"""
Compute the visual state at a given timestamp t.

Returns a plain dict:
    active_id        — block being centered (used for positioning + text brightness)
    beat_block_id    — block whose beat dots are animating (differs from active_id
                       during scroll anticipation: old block keeps its dots while
                       the new block slides in)
    prev_id          — block scrolling out (None if no scroll)
    scroll_progress  — 0.0 → 1.0
    chord_group_idx, repeat_idx, measure_idx, beat_idx  — beat dot state
"""


def compute(t, blocks, beat_events, anticipation):
    active, active_pos = _find_active(t, blocks)
    if active is None:
        return None

    next_block = _find_next(blocks, active_pos)

    # Check if t falls inside the scroll-anticipation window of the next block.
    # During this window the stack is already moving toward next_block, but beat
    # dots still belong to the current (active) block.
    if next_block and anticipation > 0:
        spb        = 60.0 / next_block['bpm']
        scroll_dur = anticipation * spb
        scroll_start = next_block['start_time'] - scroll_dur
        if scroll_start <= t < next_block['start_time']:
            raw = (t - scroll_start) / scroll_dur
            return {
                'active_id':     next_block['id'],   # block sliding into center
                'beat_block_id': active['id'],        # dots still on current block
                'prev_id':       active['id'],
                'scroll_progress': _smoothstep(raw),
                **_find_beat_state(t, active['id'], beat_events),
            }

    # Normal case: active block is (or has just become) the centered block.
    prev = _find_prev(blocks, active_pos)
    return {
        'active_id':     active['id'],
        'beat_block_id': active['id'],
        'prev_id':       prev['id'] if prev else None,
        'scroll_progress': _scroll_progress(t, active, anticipation),
        **_find_beat_state(t, active['id'], beat_events),
    }


# ---------------------------------------------------------------------------

def _find_active(t, blocks):
    """Last non-header block whose start_time <= t (or first non-header block)."""
    active, active_pos = None, -1
    for i, b in enumerate(blocks):
        if b['kind'] == 'header':
            continue
        if b['start_time'] <= t:
            active, active_pos = b, i
    if active is None:
        for i, b in enumerate(blocks):
            if b['kind'] != 'header':
                return b, i
    return active, active_pos


def _find_prev(blocks, active_pos):
    """Previous non-header block before active_pos, or None."""
    for i in range(active_pos - 1, -1, -1):
        if blocks[i]['kind'] != 'header':
            return blocks[i]
    return None


def _find_next(blocks, active_pos):
    """Next non-header block after active_pos, or None."""
    for i in range(active_pos + 1, len(blocks)):
        if blocks[i]['kind'] != 'header':
            return blocks[i]
    return None


def _scroll_progress(t, active_block, anticipation):
    """Smoothstep progress of the scroll that brought active_block into center."""
    spb        = 60.0 / active_block['bpm']
    scroll_dur = anticipation * spb
    if scroll_dur <= 0:
        return 1.0
    scroll_start = active_block['start_time'] - scroll_dur
    return _smoothstep((t - scroll_start) / scroll_dur)


def _find_beat_state(t, block_id, beat_events):
    """Last beat event for block_id at or before t."""
    state = {'chord_group_idx': 0, 'repeat_idx': 0, 'measure_idx': 0, 'beat_idx': 0}
    for ev in beat_events:
        if ev['t'] > t:
            break
        if ev['block_id'] == block_id:
            state = {k: ev[k] for k in ('chord_group_idx', 'repeat_idx', 'measure_idx', 'beat_idx')}
    return state


def _smoothstep(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)
