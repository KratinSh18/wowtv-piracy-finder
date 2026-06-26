"""
Central configuration for ContentGuard fingerprinting.

These defaults are tuned to be a sensible starting point for short vertical
micro-dramas (30s - 5min clips). After you ingest your *real* WOW TV catalog,
re-tune the thresholds (especially MIN_AUDIO_MATCH and VIDEO_MAX_HAMMING) using
the `contentguard tune` workflow described in the README.
"""

# ---------------------------------------------------------------------------
# Audio fingerprinting (Shazam-style landmark / constellation algorithm)
# ---------------------------------------------------------------------------
SAMPLE_RATE   = 11025      # mono resample target. Low rate = robust + compact.
N_FFT         = 1024       # STFT window size (~93 ms @ 11025 Hz)
HOP           = 512        # STFT hop (~46 ms). frame_time = HOP / SAMPLE_RATE
WINDOW        = "hann"

# Peak picking (the "constellation map")
PEAK_NEIGH_F   = 13        # local-max neighbourhood in frequency bins
PEAK_NEIGH_T   = 9         # local-max neighbourhood in time frames
PEAK_PERCENTILE = 65       # keep peaks louder than this percentile of the spectrogram

# Combinatorial hashing (anchor peak -> target zone peaks)
FAN_OUT   = 8              # how many target peaks each anchor pairs with
MIN_DT    = 1             # minimum time gap (frames) between anchor and target
TARGET_T  = 40            # max time gap (frames) ~1.85 s  -> the target zone width
TARGET_F  = 120           # max freq distance (bins) within the target zone

# A query is considered an audio match against a reference work when this many
# of its landmark hashes line up at a *single consistent* time offset.
MIN_AUDIO_MATCH = 12       # votes at the aligned offset for a confident hit
WEAK_AUDIO_MATCH = 5       # below this = noise; between = "needs video confirm"
OFFSET_TOLERANCE = 1       # group offsets within +-this many frames (re-encode jitter)

# Speed-change evasion: pirates often nudge playback speed (e.g. 1.05x) which
# slides the audio offset progressively and defeats exact-offset voting. We undo
# it by re-fingerprinting the suspect at several resample ratios and keeping the
# best. SPEED_GRID is used when speed search is on (default on; --no-speed-search
# to disable for faster scans). 1.0 must be in the grid.
SPEED_GRID = [0.95, 0.97, 1.0, 1.03, 1.05]

# ---------------------------------------------------------------------------
# Video fingerprinting (perceptual hashing of sampled frames)
# ---------------------------------------------------------------------------
VIDEO_FPS         = 1.0    # frames sampled per second for hashing
PHASH_SIZE        = 8      # 8x8 -> 64-bit perceptual hash
PHASH_HIGHFREQ    = 32     # DCT computed on a 32x32 reduced image
VIDEO_MAX_HAMMING = 12     # a frame "matches" if within this Hamming distance
VIDEO_MATCH_FRAC  = 0.35   # fraction of suspect frames that must match a work
MIN_VIDEO_FRAMES  = 5      # containment: this many matched frames alone corroborates
                           # (so a short stolen clip inside a long compilation still flags)
FLIP_INVARIANT    = True   # also store mirrored frame hashes -> catch horizontal flips

# ---------------------------------------------------------------------------
# Verdict thresholds (combined audio + video confidence, 0..100)
# ---------------------------------------------------------------------------
VERDICT_MATCH   = 70       # >= this  -> "MATCH"  (high confidence stolen content)
VERDICT_LIKELY  = 40       # >= this  -> "LIKELY" (review manually)

DB_DEFAULT = "contentguard.db"
