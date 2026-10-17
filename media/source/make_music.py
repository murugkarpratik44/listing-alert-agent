"""Original 60-second background track for the Listing Alert Agent video.

120 BPM, so every scene change (6, 14, 22, 32, 42, 50, 56 s) lands on a bar line.
Everything is synthesised here: no samples, no third-party music.
Usage: python make_music.py out.wav
"""
import sys
import numpy as np
from scipy.signal import butter, sosfilt

SR = 48000
DUR = 60.0
BPM = 120
BEAT = 60 / BPM            # 0.5 s
BAR = 4 * BEAT             # 2 s
SCENES = [6, 14, 22, 32, 42, 50, 56]
N = int(SR * DUR)
rng = np.random.default_rng(7)


def t_of(n):
    return np.arange(n) / SR


def env(n, a=0.005, r=0.2):
    t = t_of(n)
    e = np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / r)
    return e


def lp(x, hz):
    return sosfilt(butter(2, hz, "low", fs=SR, output="sos"), x)


def hp(x, hz):
    return sosfilt(butter(2, hz, "high", fs=SR, output="sos"), x)


def add(buf, start, sig, gain=1.0):
    i = int(start * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(sig))
    buf[i:j] += gain * sig[: j - i]


def note(m):
    return 440.0 * 2 ** ((m - 69) / 12)


# Am – F – C – G, one chord per bar (MIDI notes)
CHORDS = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]
ROOTS = [45, 41, 36, 43]


def section(t):
    """Arrangement level by time: which parts play."""
    if t < 6:   return {"pad": 1, "hat": 0.5, "kick": 0, "clap": 0, "bass": 0}
    if t < 14:  return {"pad": 1, "hat": 0.8, "kick": 1, "clap": 0, "bass": 1}
    if t < 50:  return {"pad": 1, "hat": 1, "kick": 1, "clap": 1, "bass": 1}
    if t < 56:  return {"pad": 1, "hat": 0.6, "kick": 0.7, "clap": 0, "bass": 1}
    return {"pad": 1, "hat": 0, "kick": 0, "clap": 0, "bass": 0.6}


pad = np.zeros(N); bass = np.zeros(N); drums = np.zeros(N); fx = np.zeros(N)

# pad: detuned saws through a low-pass, one chord per bar with soft attack
for b in range(int(DUR / BAR)):
    start = b * BAR
    lvl = section(start)["pad"]
    n = int((BAR + 0.4) * SR)
    t = t_of(n)
    sig = np.zeros(n)
    for m in CHORDS[b % 4]:
        for det in (-0.12, 0.12):
            f = note(m) * 2 ** (det / 12)
            sig += 2 * ((t * f) % 1) - 1
    a = np.minimum(1, t / 0.35) * np.minimum(1, np.maximum(0, (BAR + 0.4 - t) / 0.4))
    add(pad, start, lp(sig, 1400) * a * 0.075 * lvl)

for i in range(int(DUR / BEAT)):
    t0 = i * BEAT
    s = section(t0)
    beat_in_bar = i % 4
    # kick on 1 and 3
    if s["kick"] and beat_in_bar in (0, 2):
        n = int(0.35 * SR); t = t_of(n)
        f = 50 + 70 * np.exp(-t / 0.04)
        add(drums, t0, np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.002, 0.12) * 0.34 * s["kick"])
    # clap on 2 and 4
    if s["clap"] and beat_in_bar in (1, 3):
        n = int(0.2 * SR)
        add(drums, t0, hp(rng.standard_normal(n), 1200) * env(n, 0.001, 0.05) * 0.12)
    # closed hats on eighths
    if s["hat"]:
        for k, g in ((0, 1.0), (0.5, 0.6)):
            n = int(0.05 * SR)
            add(drums, t0 + k * BEAT, hp(rng.standard_normal(n), 7000) * env(n, 0.001, 0.012) * 0.07 * g * s["hat"])
    # bass on 1 and the "and" of 2
    if s["bass"] and beat_in_bar in (0, 2):
        b = int(t0 / BAR) % 4
        n = int(0.45 * SR); t = t_of(n)
        f = note(ROOTS[b] - 12 + 12)
        sig = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t)
        add(bass, t0, lp(sig, 500) * env(n, 0.01, 0.3) * 0.22 * s["bass"])

# scene-change accents: a soft swell into each change and a bell on the downbeat
for sc in SCENES:
    n = int(1.0 * SR); t = t_of(n)
    swell = hp(rng.standard_normal(n), 3000) * (t / t[-1]) ** 2 * 0.05
    add(fx, sc - 1.0, swell)
    n = int(1.6 * SR); t = t_of(n)
    b = int(sc / BAR) % 4
    f = note(CHORDS[b][2] + 12)
    bell = (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * 2.76 * f * t)) * env(n, 0.002, 0.45)
    add(fx, sc, bell * 0.07)

# final chord rings out over the end card
n = int(4.0 * SR); t = t_of(n)
sig = sum(np.sin(2 * np.pi * note(m) * t) for m in CHORDS[0] + [69])
add(pad, 56.0, sig * np.minimum(1, t / 0.3) * np.exp(-t / 2.2) * 0.04)

mix_l = pad * 1.0 + bass + drums * 0.95 + fx * 1.1
mix_r = pad * 0.9 + bass + drums * 1.05 + fx * 0.9
# simple room: a few short delays
for d, g in ((0.031, 0.18), (0.047, 0.14), (0.089, 0.10)):
    k = int(d * SR)
    mix_l[k:] += g * mix_r[:-k]
    mix_r[k:] += g * mix_l[:-k]
stereo = np.stack([mix_l, mix_r], axis=1)
fade = np.ones(N); fi = int(0.8 * SR); fo = int(3.0 * SR)
fade[:fi] = np.linspace(0, 1, fi); fade[-fo:] = np.linspace(1, 0, fo)
stereo *= fade[:, None]
stereo /= np.max(np.abs(stereo)) / 0.89          # peak -1 dBFS before loudness normalisation
pcm = (stereo * 32767).astype(np.int16)

import wave
with wave.open(sys.argv[1], "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print("wrote", sys.argv[1])
