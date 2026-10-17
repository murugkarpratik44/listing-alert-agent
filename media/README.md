# Media

All listings, people and places shown are sample data from the plugin's test fixtures. Nothing comes from a real search.

| File | What it is |
|---|---|
| `demo.gif` | 25-second dry run: seven sample alert emails become one ranked alert (800×500) |
| `listing-alert-agent-60s.mp4` | 60-second overview with captions and background music, no voiceover (1920×1080) |
| `listing-alert-agent-60s-square.mp4` | The same video for social feeds (1080×1080) |
| `how-it-works.png` | One-page infographic (1200×2180) |

## Rebuild

The GIF and videos are animated HTML pages recorded frame by frame with Playwright, then encoded with ffmpeg.

1. Run a dry run on the test fixtures and render the alert email to `alert-full.png` (640 px wide) and `alert-phone.png` (390 px wide). Put both next to the pages in `source/`.
2. Record the frames:

   ```bash
   python source/record.py source/demo-gif.html frames-gif 12 800 500 1
   python source/record.py source/video.html frames-wide 30 1920 1080 1
   python source/record.py "source/video.html?sq" frames-square 30 1080 1080 1
   ```

3. Encode with ffmpeg: a 128-colour palette for the GIF, and H.264 (`-crf 20 -pix_fmt yuv420p`) for the MP4s.
4. Music: `python source/make_music.py music.wav` writes an original 120 BPM track, synthesised in the script with no samples. Each scene change lands on a bar line. Normalise it with `loudnorm=I=-16:TP=-1.5`, then add it to each MP4 as 160 kbps AAC.
