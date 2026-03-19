#!/usr/bin/env python3
"""
livenotes-video-generator
Generate a karaoke-style MP4 video from a Livenotes JSON file + audio.

Usage:
    python main.py song.json audio.mp3 [--count-in 4] [--anticipation 0] [--output out.mp4]
"""

import argparse
import json
import subprocess
import sys

import layout as L
from timeline import build
from state import compute
from renderer import load_fonts, render
from encoder import Encoder


def get_audio_duration(path):
    result = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f'Error: ffprobe failed on {path}', file=sys.stderr)
        sys.exit(1)
    return float(json.loads(result.stdout)['format']['duration'])


def main():
    parser = argparse.ArgumentParser(
        description='Generate a karaoke-style video from Livenotes JSON + audio.'
    )
    parser.add_argument('json_file',   help='Livenotes JSON file')
    parser.add_argument('audio_file',  help='Audio file (.mp3 or .wav)')
    parser.add_argument('--count-in',     type=int, default=4,
                        help='Count-in beats at the start of the audio (default: 4)')
    parser.add_argument('--anticipation', type=int, default=0,
                        help='Beats before a new block to start scroll animation (default: 0)')
    parser.add_argument('--output', default='output.mp4',
                        help='Output video path (default: output.mp4)')
    args = parser.parse_args()

    with open(args.json_file) as f:
        song = json.load(f)

    print('Building timeline...')
    blocks, beat_events = build(song, args.count_in, args.anticipation)
    print(f'  {len(blocks)} blocks, {len(beat_events)} beat events')

    audio_duration = get_audio_duration(args.audio_file)
    total_frames   = int(audio_duration * L.FPS)
    print(f'  Audio: {audio_duration:.1f}s → {total_frames} frames at {L.FPS}fps')

    fonts = load_fonts()
    enc   = Encoder(args.output, args.audio_file, L.WIDTH, L.HEIGHT, L.FPS)

    last_state   = None
    renders      = 0
    repeats      = 0

    print('Rendering...')
    for frame_n in range(total_frames):
        t = frame_n / L.FPS
        s = compute(t, blocks, beat_events, args.anticipation)

        if s == last_state:
            enc.repeat_last_frame()
            repeats += 1
        else:
            img = render(s, blocks, fonts)
            enc.write_frame(img)
            last_state = s
            renders += 1

        if frame_n % (L.FPS * 5) == 0:
            pct = 100 * frame_n / total_frames
            print(f'  {t:6.1f}s / {audio_duration:.1f}s  ({pct:.0f}%)  '
                  f'rendered={renders} repeated={repeats}',
                  flush=True)

    enc.close()
    print(f'\nDone → {args.output}')
    print(f'Frames: {renders} rendered, {repeats} repeated '
          f'({100*repeats//total_frames}% deduplication)')


if __name__ == '__main__':
    main()
