# EMBER demo: slides, video and filming script

Everything for the Space Apps "Link to Project Demo" field.

| File | What it is |
|---|---|
| `out/EMBER-demo.mp4` | 29.5 s, 1920×1080 slide video with burned-in English subtitles. No sound yet. |
| `out/EMBER-demo.srt` | The same subtitles as a separate file (for YouTube's captions). |
| `out/EMBER-slides.pdf` | The 7 slides as a PDF. You can submit this instead of a video. |
| `out/slide-1.png` … `slide-7.png` | Each slide as an image. |
| `slides.html` | Slide source. Screenshots are real crops of the running app (`assets/`). |
| `film.html` | Builds the video: timing, crossfades and subtitles. |

Space Apps limits: video **30 seconds or less**, or **7 slides at most** including the title. Ours: 29.5 s, 7 slides.

---

## Filming script (read this over the video)

Play `out/EMBER-demo.mp4` and record your voice while it plays, so your words land on the right slide.
Each line is short enough to say calmly in its time slot. Speak in English.

| Time | Slide on screen | Say this |
|---|---|---|
| 0:00 – 0:03 | 1 · Title: EMBER, team, members, challenge | "Hi, we're team **Mustangs**, and this is EMBER." |
| 0:03 – 0:07.5 | 2 · ISS air (21% O₂) → exploration air (34% O₂, 8.2 psia) | "Moon habitats will breathe richer, thinner air. Does NASA's fire data still apply?" |
| 0:07.5 – 0:12 | 3 · 982 records + evidence map | "EMBER maps 982 records from NASA's PSI and technical reports." |
| 0:12 – 0:17 | 4 · Ask page: ranked experiments | "Describe a habitat. It ranks which experiments apply, and how far you're stretching them." |
| 0:17 – 0:21.5 | 5 · Gaps: microgravity vs lunar | "And it shows the gap: no fire data at lunar or Mars gravity." |
| 0:21.5 – 0:25.5 | 6 · Trust: 5 of 5, 8 of 8, 1,000, 0 of 12 | "Unknowns stay unknown, and nothing is ever called safe." |
| 0:25.5 – 0:29.5 | 7 · Future: aim the next experiments here | "Next: aim the next fire experiments right at those gaps." |

The subtitles match these words exactly. If you change a line, tell us, and the subtitles get
changed to match.

### How to record your voice

1. Use a quiet room and a phone or laptop mic held about a hand's width away.
2. Open the video full screen and start your voice recorder (Voice Memos, QuickTime → New Audio
   Recording, or your phone).
3. Say "three, two, one", press play on the video, and read the lines as the slides change.
4. Do two or three takes and keep the best one.
5. Send us the audio file (m4a, mp3 or wav) plus your **team name** and **member names**. We will put
   them on the title slide, update the first subtitle, add your voice to the video and re-export it.

Rules from the guide: nobody under 18 in the video, everything in English, and no NASA logos (there
are none in these slides). The slides say "Slides made with AI assistance (Claude)" in the corner,
because the guide requires a visible watermark on media made with AI.

---

## Rebuilding (after the team details arrive)

The slides take the team details from the URL, so nothing needs editing by hand:

```bash
cd submission   # needs Node and Playwright (npm i playwright) and Google Chrome
node tools/render.js slides.html out "team=Team%20Blaze&members=A%20·%20B%20·%20C&repo=Code:%20<b>github.com/you/ember</b>"
node tools/film.js film.html out "team=Blaze"
```

`render.js` writes the slide PNGs and PDF; `film.js` plays `film.html` in Chrome and records the
canvas to MP4 (no ffmpeg needed).
