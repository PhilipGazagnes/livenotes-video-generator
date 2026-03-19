# Implementation Plan — livenotes-video-generator

**POC v1.0** — Goal: produce a watchable karaoke-style MP4 from a Livenotes JSON + audio file.

---

## What We're Building

```
python main.py song.json audio.mp3 [--count-in 4] [--anticipation 0] [--output out.mp4]
```

Takes a Livenotes JSON + audio → outputs a 1920×1080 60fps MP4 with chords/lyrics scrolling in sync.

---

## Module Structure (per spec)

```
main.py       CLI entry point, frame loop, orchestration
timeline.py   Build timed blocks and beat events from JSON
state.py      Compute visual state at timestamp t
renderer.py   Draw a single PIL frame from visual state
encoder.py    FFmpeg pipe: write frames, mux audio
layout.py     Visual constants (colors, sizes, spacing)
```

---

## Step 0 — Setup

`requirements.txt`:
```
Pillow
ffmpeg-python
```

Also needs: system FFmpeg binary, a monospace TTF font and a regular TTF font bundled in `fonts/`.

Font choice is a real decision: Pillow's built-in bitmap fonts are too low quality for video. Pick a clean open-source pair (e.g., Inter for lyrics, JetBrains Mono for chords/dots) before any rendering work.

---

## Step 1 — `layout.py`

All visual constants in one place. Values below are **starting guesses** — expect to tune them after seeing the first rendered frame.

```python
WIDTH, HEIGHT = 1920, 1080
FPS = 60

# Colors (from spec)
BG              = (17, 17, 17)
TEXT_ACTIVE     = (255, 255, 255)
TEXT_INACTIVE   = (85, 85, 85)
TEXT_HEADER     = (170, 170, 170)
DOT_ACTIVE      = (245, 166, 35)   # amber
DOT_PAST        = (136, 136, 136)
DOT_FUTURE      = (51, 51, 51)
SEPARATOR_COLOR = (68, 68, 68)

# Sizes — tune after first render
FONT_LYRICS_SIZE = 42
FONT_CHORD_SIZE  = 32   # monospace
BLOCK_HEIGHT     = 160  # pixels per block (all 3 rows)
MARGIN_H         = 120  # left/right padding
BEAT_WIDTH       = 40   # px per beat (dot cell width, chord cell aligns to this)
```

---

## Step 2 — `timeline.py`

**Input:** parsed song JSON, `count_in` int, `anticipation` int
**Output:** `blocks` list, `beat_events` list (both sorted by time)

### What a Block is

A plain dict with computed fields added:

```python
{
  "id":         int,
  "kind":       "header" | "countin" | "content",
  "start_time": float,   # seconds
  "duration":   float,   # 0 for header
  "lyrics":     str,
  "style":      "default" | "info" | "musicianInfo",
  "chords":     [...],   # chord groups from prompter (content only)
  "countin_beats": int,  # countin only
}
```

No dataclass needed — plain dicts are fine for a POC.

### What a BeatFire is

```python
{
  "t":          float,   # absolute timestamp
  "block_id":   int,
  "measure_idx": int,    # 0-based, within current pass (resets each repetition)
  "beat_idx":   int,     # 0-based within the measure
  "repeat_idx": int,     # which pass through the chord group pattern
}
```

Only BeatFire events are needed. Block activation and scroll timing are **derived from block start times** at query time in `state.py` — no need to materialise them as events.

### Build Algorithm

```
1. bpm = meta.bpm, num = meta.time.numerator
   current_time = 0

2. If meta.name or meta.artist:
     append header block (id=0, kind="header", start=0, duration=0)

3. If count_in > 0:
     spb = 60 / bpm
     duration = count_in * spb
     append countin block (start=0, duration=duration, countin_beats=count_in)
     append BeatFire events: t = i * spb for i in 0..count_in-1
     current_time += duration

4. For each prompter item:
     if type == "tempo": update bpm and/or num, continue
     if type == "content":
       spm = (60 / bpm) * num
       total_measures = sum(cg.repeats * len(cg.pattern) for cg in item.chords)
       duration = total_measures * spm
       append content block (start=current_time, duration=duration, ...)

       # Emit BeatFire events
       t = current_time
       for cg in item.chords:
           for rep in range(cg.repeats):
               for m_idx, measure in enumerate(cg.pattern):
                   for b in range(num):
                       append BeatFire(t + b*spb, block_id, m_idx, b, rep)
                   t += spm

       current_time += duration
```

**Notes on edge cases:**
- `%` and `_` symbols in measures are display-only — the beat still fires, timing is unaffected
- `=` (beat removal) — treat as a full measure for timing in v1 (spec timing formula is uniform)
- `newLine` / `loopStart` / `loopEnd:n` do **not** appear in prompter patterns — they are already expanded by the converter

---

## Step 3 — `state.py`

**`compute(t, blocks, beat_events) → state dict`**

Called once per frame. Returns everything the renderer needs.

### Active block

Find the content block where `block.start_time <= t < block.start_time + block.duration`. If `t` is before all content blocks (count-in period), active block is the count-in block.

### Current beat position

Binary-search `beat_events` for the last event where `event.t <= t` and `event.block_id == active_block_id`. That gives `(measure_idx, beat_idx, repeat_idx)` for the dot animation.

### Scroll progress

```python
scroll_trigger = active_block.start_time - anticipation * spb
scroll_duration = anticipation * spb

if scroll_duration == 0:
    scroll_progress = 1.0   # instant snap
else:
    scroll_progress = smoothstep((t - scroll_trigger) / scroll_duration)

def smoothstep(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)
```

### Output

```python
{
  "active_id":      int,
  "prev_id":        int | None,   # the block scrolling out
  "scroll_progress": float,       # 0.0–1.0
  "measure_idx":    int,
  "beat_idx":       int,
  "repeat_idx":     int,
}
```

---

## Step 4 — `encoder.py`

Single FFmpeg call: pipe raw video frames in, take audio file as a second input.

```python
class Encoder:
    def open(self, output_path, audio_path, width, height, fps):
        self.proc = ffmpeg
            .input('pipe:', format='rawvideo', pix_fmt='rgb24',
                   s=f'{width}x{height}', r=fps)
            .input(audio_path)
            .output(output_path, vcodec='libx264', crf=18, preset='fast',
                    acodec='aac', audio_bitrate='192k', shortest=None)
            .overwrite_output()
            .run_async(pipe_stdin=True)
        self._last_bytes = None

    def write_frame(self, image):
        b = image.tobytes()
        self.proc.stdin.write(b)
        self._last_bytes = b

    def repeat_last_frame(self):
        self.proc.stdin.write(self._last_bytes)

    def close(self):
        self.proc.stdin.close()
        self.proc.wait()
```

---

## Step 5 — `renderer.py`

**`render(state, blocks, layout) → PIL.Image`**

### Visible blocks

Active block is vertically centered. Fill above (past) and below (upcoming) with as many blocks as fit. During scroll: offset all blocks by `scroll_progress * BLOCK_HEIGHT` upward so the next block slides in from below.

```python
active_y = (HEIGHT - BLOCK_HEIGHT) // 2
offset = int(scroll_progress * BLOCK_HEIGHT)
```

### Per-block rendering

For each visible block, compute `y = active_y + (block_index - active_index) * BLOCK_HEIGHT - offset`.

**Brightness:** Active = full, others dimmed. Simple approach: multiply color channels by a factor based on distance (e.g. `0.35` for all inactive blocks).

**Three rows per block:**

**Row 1 — Lyrics** (`y + 0`):
- Font: bold if active, regular if inactive; italic if style is `"info"` or `"musicianInfo"`
- Color: `TEXT_ACTIVE` if active, `TEXT_INACTIVE` if not

**Row 2 — Chord row** (`y + 50`):
- For each chord group, render one pass through its pattern:
  - For each measure: draw chord text left-aligned in a cell of width `num_chords_in_measure × beats_per_chord × BEAT_WIDTH`
  - Draw `|` separator between measures (color `SEPARATOR_COLOR`)
  - If `repeats > 1`: draw repeat dots to the right after a small gap
- Chord display: join `base + extension` → `"Am7"`, `"G"`, display `%` and `_` as-is

**Row 3 — Dot row** (`y + 90`):
- Mirror the chord row's cell structure
- Each beat = one filled circle
- Color per dot (active block only):
  - Global beat position = `measure_idx * num + beat_idx`
  - `beat < current_global_beat`: `DOT_PAST`
  - `beat == current_global_beat`: `DOT_ACTIVE`
  - `beat > current_global_beat`: `DOT_FUTURE`
- Inactive blocks: all dots `DOT_FUTURE` color

**Repeat dots** (right of chord row, only if `repeats > 1`):
- `repeats` small circles; `repeat_idx` is highlighted amber, rest dim

**Special blocks:**
- Header: just draw `"Song Title — Artist"` text, centered, no chord/dot rows
- Count-in: draw `"Count"` label + `countin_beats` dots (same dot color logic)

### Multi-chord measures

When a measure has N chords, each chord gets `num / N` beats (assumed equal split). Each chord sub-cell width = `(num / N) * BEAT_WIDTH`. Dots are grouped accordingly under each chord.

---

## Step 6 — `main.py`

```python
def main():
    # 1. Parse args: json_path, audio_path, --count-in, --anticipation, --output
    # 2. song = json.load(json_path)
    # 3. blocks, beat_events = timeline.build(song, count_in, anticipation)
    # 4. total_duration = get_audio_duration(audio_path)  # via ffprobe
    # 5. total_frames = int(total_duration * FPS)
    # 6. encoder.open(output, audio_path, ...)
    # 7. last_state = None
    #    for frame_n in range(total_frames):
    #        t = frame_n / FPS
    #        state = compute(t, blocks, beat_events)
    #        if state == last_state:
    #            encoder.repeat_last_frame()
    #        else:
    #            image = render(state, blocks)
    #            encoder.write_frame(image)
    #            last_state = state
    # 8. encoder.close()
```

**Frame deduplication** is a simple equality check — no skip-ahead, no event lookahead. The loop runs every frame; only the PIL rendering is skipped. At 120 BPM this avoids ~97% of render calls with no added complexity.

**Audio duration** via `ffprobe`:
```python
import subprocess, json
def get_audio_duration(path):
    out = subprocess.check_output(
        ['ffprobe', '-v', 'quiet', '-print_format', 'json',
         '-show_format', path])
    return float(json.loads(out)['format']['duration'])
```

---

## Implementation Order

1. `layout.py` — constants (10 min)
2. `timeline.py` — parse JSON → blocks + beat events (core logic, test with `print`)
3. `state.py` — compute state at t (unit-testable: given events, does state look right?)
4. `encoder.py` — FFmpeg pipe (test: write 60 blank frames, confirm a valid mp4)
5. `renderer.py` — draw frames (start with just background + active lyrics text, add layers)
6. `main.py` — wire everything together

**First milestone:** render a single frame at `t = 5.0` for `highway-to-hell.json` and inspect it visually. Don't attempt full video encoding until one frame looks correct.

---

## What Is Out of Scope for POC

- Fonts being perfect — pick anything readable and move on
- Pixel-perfect layout alignment — tune constants after first render
- Songs without timing info (lyrics with `measures: null`) — skip gracefully
- Error handling beyond "crash with a clear message"
- Performance beyond the simple frame dedup check
