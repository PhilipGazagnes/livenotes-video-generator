"""
Render a single 1920×1080 PIL frame from a visual state.
"""

from PIL import Image, ImageDraw, ImageFont
import layout as L


def load_fonts():
    return {
        'regular': ImageFont.truetype(L.FONT_REGULAR, L.FONT_LYRICS_SIZE),
        'bold':    ImageFont.truetype(L.FONT_BOLD,    L.FONT_LYRICS_SIZE),
        'italic':  ImageFont.truetype(L.FONT_ITALIC,  L.FONT_LYRICS_SIZE),
        'chord':   ImageFont.truetype(L.FONT_MONO,    L.FONT_CHORD_SIZE),
        'header':  ImageFont.truetype(L.FONT_REGULAR, L.FONT_HEADER_SIZE),
    }


def render(state, blocks, fonts):
    img  = Image.new('RGB', (L.WIDTH, L.HEIGHT), L.BG)
    draw = ImageDraw.Draw(img)

    if state is None:
        return img

    active_id  = state['active_id']
    stack_map  = {b['id']: i for i, b in enumerate(blocks)}
    active_pos = stack_map[active_id]

    # Center of screen Y for the active block
    active_y = (L.HEIGHT - L.BLOCK_HEIGHT) // 2

    # Floating "center stack position": shifts during scroll
    if state['prev_id'] is not None:
        center_pos = active_pos - (1.0 - state['scroll_progress'])
    else:
        center_pos = float(active_pos)

    beat_block_id = state['beat_block_id']

    for b in blocks:
        pos = stack_map[b['id']]
        y   = active_y + int((pos - center_pos) * L.BLOCK_HEIGHT)

        # Skip entirely off-screen blocks
        if y + L.BLOCK_HEIGHT < 0 or y > L.HEIGHT:
            continue

        _draw_block(draw, fonts, b, state, y,
                    is_text_active=b['id'] == active_id,
                    is_dots_active=b['id'] == beat_block_id)

    return img


# ---------------------------------------------------------------------------
# Block drawing
# ---------------------------------------------------------------------------

def _draw_block(draw, fonts, block, state, y, is_text_active, is_dots_active):
    kind     = block['kind']
    time_num = block['time_num']

    # --- Lyrics / label row ---
    if kind == 'header':
        draw.text((L.MARGIN_H, y + L.LYRICS_OFFSET),
                  block['lyrics'], font=fonts['header'], fill=L.TEXT_HEADER)
        return  # headers have no chord/dot rows

    if kind == 'countin':
        label_color = L.TEXT_ACTIVE if is_text_active else L.TEXT_INACTIVE
        draw.text((L.MARGIN_H, y + L.LYRICS_OFFSET),
                  'Count', font=fonts['regular'], fill=label_color)
        _draw_countin_dots(draw, block, state, y, is_dots_active)
        return

    # content block
    lyric_color = L.TEXT_ACTIVE if is_text_active else L.TEXT_INACTIVE
    lyric_font  = _lyric_font(fonts, block['style'], is_text_active)
    draw.text((L.MARGIN_H, y + L.LYRICS_OFFSET),
              block['lyrics'], font=lyric_font, fill=lyric_color)

    _draw_chord_dot_rows(draw, fonts, block, state, y, is_text_active, is_dots_active, time_num)


def _lyric_font(fonts, style, is_active):
    if style in ('info', 'musicianInfo'):
        return fonts['italic']
    return fonts['bold'] if is_active else fonts['regular']


def _draw_countin_dots(draw, block, state, y, is_active):
    dot_y        = y + L.DOT_OFFSET
    active_beat  = state['beat_idx'] if is_active else -1

    x = L.MARGIN_H + L.BEAT_WIDTH // 2
    for i in range(block['countin_beats']):
        if is_active:
            if i < active_beat:
                color = L.DOT_PAST
            elif i == active_beat:
                color = L.DOT_ACTIVE
            else:
                color = L.DOT_FUTURE
        else:
            color = L.DOT_FUTURE
        _circle(draw, x, dot_y, L.DOT_RADIUS, color)
        x += L.BEAT_WIDTH


def _draw_chord_dot_rows(draw, fonts, block, state, y, is_text_active, is_dots_active, time_num):
    chord_y = y + L.CHORD_OFFSET
    dot_y   = y + L.DOT_OFFSET

    x = L.MARGIN_H
    for cg_idx, cg in enumerate(block['chords']):
        is_active_cg = is_dots_active and state['chord_group_idx'] == cg_idx
        pattern      = cg['pattern']
        repeats      = cg['repeats']

        for m_idx, measure in enumerate(pattern):
            n_elem         = len(measure)
            beats_per_slot = time_num / n_elem if n_elem > 0 else float(time_num)
            n_dots         = round(beats_per_slot)   # dots (beats) per chord element
            chord_count    = sum(1 for e in measure if not _is_remover(e))
            measure_px     = chord_count * n_dots * L.BEAT_WIDTH

            chord_rank = 0
            for elem in measure:
                if _is_remover(elem):
                    continue  # no text, no dots, no visual space

                elem_x = x + chord_rank * n_dots * L.BEAT_WIDTH

                # Chord text
                chord_color = L.TEXT_ACTIVE if is_text_active else L.TEXT_INACTIVE
                draw.text((elem_x, chord_y), _fmt_chord(elem),
                          font=fonts['chord'], fill=chord_color)

                # Beat dots
                for b in range(n_dots):
                    dot_x = elem_x + b * L.BEAT_WIDTH + L.BEAT_WIDTH // 2
                    color = _dot_color(is_active_cg, m_idx, chord_rank, b,
                                       n_dots, state)
                    _circle(draw, dot_x, dot_y, L.DOT_RADIUS, color)

                chord_rank += 1

            # Measure separator (not after the last measure in this chord group)
            if m_idx < len(pattern) - 1:
                sep_x = x + measure_px + L.SEP_GAP // 2
                sep_color = L.SEPARATOR_COLOR
                draw.line([(sep_x, chord_y),
                           (sep_x, dot_y + L.DOT_RADIUS)],
                          fill=sep_color, width=L.SEP_WIDTH)
                x += measure_px + L.SEP_GAP + L.SEP_WIDTH
            else:
                x += measure_px

        # Repeat indicator dots (only if repeats > 1)
        if repeats > 1:
            x += L.REPEAT_DOT_GAP
            for r in range(repeats):
                if is_active_cg:
                    c = L.DOT_REPEAT_ACTIVE if r == state['repeat_idx'] else L.DOT_REPEAT_INACTIVE
                else:
                    c = L.DOT_REPEAT_INACTIVE
                cx = x + L.REPEAT_DOT_R
                _circle(draw, cx, dot_y, L.REPEAT_DOT_R, c)
                x += L.REPEAT_DOT_R * 2 + L.REPEAT_DOT_PAD

        if cg_idx < len(block['chords']) - 1:
            x += L.CG_GAP


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_chord(elem):
    """Format a chord element for display: ['Am','7'] → 'Am7', '%' → '%'."""
    if isinstance(elem, list):
        return elem[0] + elem[1]
    return str(elem)


def _is_remover(elem):
    """Return True for beat-remover elements ('=') that have no visual representation."""
    return elem == '='


def _dot_color(is_active_cg, m_idx, chord_rank, b_within_elem, n_dots, state):
    """Return the color for a single beat dot."""
    if not is_active_cg:
        return L.DOT_FUTURE

    if m_idx < state['measure_idx']:
        return L.DOT_PAST
    if m_idx > state['measure_idx']:
        return L.DOT_FUTURE

    # Same measure: compare flat beat position (chord_rank * n_dots + b)
    flat_beat   = chord_rank * n_dots + b_within_elem
    active_beat = state['beat_idx']

    if flat_beat < active_beat:
        return L.DOT_PAST
    elif flat_beat == active_beat:
        return L.DOT_ACTIVE
    else:
        return L.DOT_FUTURE


def _circle(draw, cx, cy, r, color):
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
