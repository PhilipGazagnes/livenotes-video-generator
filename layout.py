WIDTH, HEIGHT = 1920, 1080
FPS = 60

# Colors (from spec)
BG                  = (17, 17, 17)
TEXT_ACTIVE         = (255, 255, 255)
TEXT_INACTIVE       = (85, 85, 85)
TEXT_HEADER         = (170, 170, 170)
DOT_ACTIVE          = (245, 166, 35)   # amber
DOT_PAST            = (136, 136, 136)
DOT_FUTURE          = (51, 51, 51)
DOT_REPEAT_ACTIVE   = (245, 166, 35)
DOT_REPEAT_INACTIVE = (51, 51, 51)
SEPARATOR_COLOR     = (68, 68, 68)

# Fonts — Ubuntu family (static TTF files, Pillow-safe)
_UBUNTU = '/usr/share/fonts/truetype/ubuntu'
FONT_REGULAR = f'{_UBUNTU}/Ubuntu-R.ttf'
FONT_BOLD    = f'{_UBUNTU}/Ubuntu-B.ttf'
FONT_ITALIC  = f'{_UBUNTU}/Ubuntu-RI.ttf'
FONT_MONO    = f'{_UBUNTU}/UbuntuMono-R.ttf'

# Font sizes (tune after first render)
FONT_LYRICS_SIZE = 42
FONT_CHORD_SIZE  = 30
FONT_HEADER_SIZE = 52

# Block layout (tune after first render)
BLOCK_HEIGHT   = 160   # total height per block slot in the stack
LYRICS_OFFSET  = 10    # top of block → lyrics text top
CHORD_OFFSET   = 68    # top of block → chord row top
DOT_OFFSET     = 115   # top of block → dot row center

# Horizontal layout
MARGIN_H       = 100   # left padding for lyrics / chord rows
BEAT_WIDTH     = 44    # pixels per beat — sets chord/dot row scale
SEP_WIDTH      = 2     # vertical separator bar width
SEP_GAP        = 8     # total extra space (both sides) around each separator
DOT_RADIUS     = 9     # beat dot radius
REPEAT_DOT_R   = 9     # repeat-indicator dot radius
REPEAT_DOT_GAP = 28    # gap between last measure and repeat dots
REPEAT_DOT_PAD = 6     # padding between consecutive repeat dots
CG_GAP         = 16    # gap between chord groups in the same block
