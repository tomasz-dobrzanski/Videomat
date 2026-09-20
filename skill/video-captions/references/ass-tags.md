# ASS override tags — cheatsheet for custom animations

Read this when a requested effect isn't covered by the presets in `make_ass.py`.
Tags go inside `{...}` at the start of (or inline within) a Dialogue text field.
Times inside tags are **milliseconds relative to the event's start**.

## Color format
`&HAABBGGRR` — alpha first (00 = opaque, FF = invisible), then **blue, green, red** (reversed vs HTML).
Examples: white `&H00FFFFFF`, cyan #00E5FF → `&H00FFE500`, magenta #FF00E5 → `&H00E500FF`.

## Positioning & motion
| Tag | Effect |
|---|---|
| `\pos(x,y)` | absolute position (anchor set by `\an`) |
| `\an1..9` | anchor: numpad layout (2 = bottom-center, 5 = middle-center, 8 = top-center) |
| `\move(x1,y1,x2,y2,t1,t2)` | linear motion between t1–t2 ms |
| `\org(x,y)` | rotation origin |
| `\frz15` / `\frx` / `\fry` | rotate (degrees) around z/x/y |

## Appearance
| Tag | Effect |
|---|---|
| `\fs72` | font size |
| `\fscx120\fscy120` | scale % (basis for pop effects) |
| `\c&H..&` `\3c&H..&` `\4c&H..&` | primary / outline / shadow color |
| `\1a&HFF&` `\3a&H80&` | per-component alpha (1=fill, 3=outline) |
| `\bord6` `\shad4` | outline / shadow width |
| `\blur4` | gaussian edge blur — basis for neon glow |
| `\fsp8` | letter spacing (nice for UPPERCASE keywords) |

## Animation
`\t([t1,t2,]tags)` — animate any animatable tags over t1–t2 ms (whole event if omitted).
`\fad(in_ms,out_ms)` — fade in/out.

**Examples:**
```
Neon pulse (single, \t can't loop):
{\an5\pos(540,350)\blur8\3c&HFFE500&\t(0,400,\blur2)}HASŁO

Color shift white→cyan:
{\an5\pos(540,350)\c&HFFFFFF&\t(200,700,\c&HFFE500&)}TEKST

Spin-in:
{\an5\pos(540,350)\frz25\fscx40\fscy40\t(0,250,\frz0\fscx100\fscy100)\fad(80,120)}NOWOŚĆ

Pseudo-loop pulse: emit N consecutive short Dialogue events (e.g. 0.6 s each),
each with its own \t — libass has no looping primitive.
```

## Karaoke / per-word effects
`{\k25}word ` — 25 **centiseconds** per unit; before its time the word shows in SecondaryColour.
- **Typewriter reveal**: set secondary alpha invisible: `{\2a&HFF&}{\k20}słowo {\k20}po {\k20}słowie`
- **Highlight karaoke** (word lights up in accent as spoken): set style SecondaryColour = white, PrimaryColour = accent; primary applies from the word's `\k` onset. Use `\kf` for a smooth sweep.

## Layering
`Dialogue: LAYER,...` — higher layer renders on top. Presets use 0 for captions, 1 for keywords. Use layer 2+ for badges/frames drawn with `\p1` vector mode (rarely needed; drawing code: `m x y l x y ...`).

## Gotchas
- `\t` interpolates linearly; accel parameter `\t(t1,t2,accel,tags)` <1 eases out, >1 eases in.
- `ScaledBorderAndShadow: yes` must stay in [Script Info] or outline widths change with resolution.
- Curly braces in user text must be stripped/replaced — `make_ass.py`'s `esc()` does this.
