"""
FFmpeg encoder: pipe raw RGB frames in, mux audio, write MP4 out.
Uses a single FFmpeg subprocess with both video pipe and audio file as inputs.
"""

import subprocess


class Encoder:
    def __init__(self, output_path, audio_path, width, height, fps):
        cmd = [
            'ffmpeg', '-y',
            # Video input from stdin pipe
            '-f', 'rawvideo', '-pix_fmt', 'rgb24',
            '-s', f'{width}x{height}', '-r', str(fps),
            '-i', 'pipe:0',
            # Audio input from file
            '-i', audio_path,
            # Video encoding
            '-c:v', 'libx264', '-crf', '18', '-preset', 'fast',
            '-pix_fmt', 'yuv420p',
            # Audio encoding
            '-c:a', 'aac', '-b:a', '192k',
            # End at the shorter of video/audio
            '-shortest',
            output_path,
        ]
        self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        self._last_bytes = None

    def write_frame(self, image):
        """Write a PIL.Image frame to the encoder."""
        b = image.tobytes()
        self._proc.stdin.write(b)
        self._last_bytes = b

    def repeat_last_frame(self):
        """Repeat the last written frame (avoids re-rendering identical frames)."""
        if self._last_bytes is not None:
            self._proc.stdin.write(self._last_bytes)

    def close(self):
        """Flush and wait for FFmpeg to finish."""
        self._proc.stdin.close()
        self._proc.wait()
