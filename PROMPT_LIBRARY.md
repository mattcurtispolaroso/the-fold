# The Fold — AI Art Prompt Library

## How to Use This File

- All art generation prompts must be stored here before use
- Record the tool used, date generated, and result quality for each prompt
- When a prompt produces a good result mark it **APPROVED**
- When iterating on a prompt keep all versions with notes on what changed
- Reference approved prompts when generating new assets to maintain visual consistency
- Current AI art tool: **Nano Banana 2**

---

## Visual Style Bible — Apply to All Prompts

- **Core aesthetic:** 1940s-1950s Astounding Science Fiction magazine cover illustration
- **Painting style:** gouache and oils, NO line art, NO outlines, forms defined by light and shadow
- **Key artists to reference:** Chesley Bonestell, Dean Ellis, Robert McCall
- **Colour palette:** cold blue-grey base, deep greens, muted ochres, single warm accent per image
- **Lighting:** dramatic single source, chiaroscuro, deep shadow filling majority of frame
- **Mood:** cosmic awe and isolation, serious not cute, scale implied not shown
- **NO:** cartoon style, comic book outlines, pixel art, cell shading, warm cosy lighting, toy-like machines

---

## Player Character

### Base Sprite — Dark Exoskeleton (APPROVED)

- **Tool:** Nano Banana 2
- **Date:** [date]
- **Result:** [your notes on quality]
- **Use for:** all player animation frames

**Prompt:**

> Retrofuturistic Fold Agent, 2D platformer sprite, full body FACING RIGHT, strict side profile, human male early 30s, calm focused expression, dark navy turtleneck and structured charcoal trousers, DARK UNLIT EXOSKELETON — cold carbon and titanium struts with NO glow NO amber light NO illumination on the exoskeleton whatsoever, the exoskeleton is purely dark cold metal, F1 HANS carbon collar yoke rising on both sides of neck, spinal brace running flush against back from skull base to pelvis, pelvic cradle connecting into outer thigh compression struts, hinged knee braces, shin struts, mechanical ankle stirrups over heavy magnetic boots, one forearm wearing control gauntlet, STANDING STILL neutral pose, painted gouache style 1940s Astounding Science Fiction illustration, Chesley Bonestell influence, cold blue-grey palette throughout, NO amber NO glow NO warm colours anywhere, transparent background, strong iconic side profile silhouette, painterly brushwork, NO pixel art NO labels NO helmet

### Glow Reference Image

- **Tool:** Nano Banana 2
- **Date:** [date]
- **Result:** [your notes]
- **Use for:** defining EXOSKELETON_GLOW_PATH coordinates in constants.py

**Prompt:**

> Retrofuturistic Fold Agent exoskeleton only, full body side view facing right, strict side profile, ONLY the exoskeleton structure visible — F1 HANS carbon collar, spinal brace struts, pelvic cradle, thigh struts, knee braces, shin struts, ankle stirrups — glowing vivid amber against pure black background, no suit visible, no body visible, just the glowing exoskeleton structure floating in darkness, the glow path clearly readable as continuous line from ankle to collar, painterly style, pure black background

---

## Environments

### Gameplay Background — Deep Space Industrial (APPROVED)

- **Tool:** Midjourney
- **Date:** [date]
- **Result:** Strong — use as template for all background prompts
- **Use for:** scrolling level background layer

**Prompt:**

> 2D side-scrolling platformer background, retrofuturistic deep space industrial setting, three distinct depth layers, FAR background layer is almost pure dark space with a faint cold green nebula and distant stars, MIDDLE background layer shows only the dark silhouetted suggestion of an enormous submarine hull — mostly in deep shadow with just a rim of cold blue light catching its edge, NEAR background layer has dark silhouetted pipes and structural beams, overall image is dark and atmospheric with 80 percent of the frame in deep shadow, very low detail and contrast throughout, painted style, style of Chesley Bonestell, muted cold palette, NO bright colours, NO busy detail, cinematic widescreen 16x9

### Set Piece — Docking Bay Viewport (APPROVED)

- **Tool:** Midjourney
- **Date:** [date]
- **Result:** Strong after 3 iterations — scale and mood correct
- **Use for:** loading screens, node transition screens, establishing shots
- **Key learnings:** name drop Chesley Bonestell and Dean Ellis explicitly, use cold not warm lighting, specify vessel fills and exceeds viewport for correct scale

**Final prompt:**

> Retrofuturistic industrial observation deck, enormous riveted circular viewport, through it the massive curved hull and single engine nacelle of a space-submarine fills and exceeds the entire viewport, beyond the hull deep space visible — dark nebula with cold distant stars, lone human figure on metal gantry far below completely dwarfed, painted in oils and gouache, style of Chesley Bonestell and Dean Ellis, 1940s Astounding Science Fiction magazine cover painting, NO line art NO outlines NO cartoon NO organic details, clean riveted steel panels, cool blue-grey metal hull, deep shadow filling most of frame, single warm amber practical light from below illuminating human figure only, cold hard light catching hull edge from deep space, muted palette of deep grey-green and cold blue with one small warm accent, atmosphere of cosmic awe and isolation, cinematic widescreen

---

## Platforms and Tiles

### Industrial Platform Tiles (APPROVED)

- **Tool:** Midjourney
- **Date:** [date]
- **Result:** Strong — horizontal orientation correct, rich detail
- **Use for:** walkable platform surfaces throughout all levels

**Prompt:**

> Sheet of 2D side-scrolling platformer building block elements for a retrofuturistic industrial game, horizontal surfaces that stack and connect to form walkable platforms, each element is LANDSCAPE ORIENTATION wide and flat like a shelf or ledge viewed from the side, the player character will stand ON TOP of these, include: wide riveted metal floor panel, wide industrial grating section, bundle of horizontal pipes running left to right, wide I-beam viewed from the side, reinforced blast door hatch lying flat, each element approximately 300 pixels wide and 60-80 pixels tall maximum, painted gouache style 1940s Astounding Science Fiction, cold blue-grey steel with warm amber rust accents, scratches rivets warning stripes pressure seals analogue gauges on sides, transparent background, all elements horizontal, NO vertical orientation NO walls NO doors standing upright

---

## Enemies

### The Witness — Cult Member (PENDING)

- **Tool:** Nano Banana 2
- **Date:** [not yet generated]
- **Result:** not yet generated
- **Use for:** first enemy type, early game nodes

**Prompt:**

> Retrofuturistic cult member enemy sprite for 2D side-scrolling platformer, full body FACING LEFT, strict side profile, human figure, ordinary 1960s civilian clothes — dark trousers plain shirt simple jacket, one detail only: small pin or patch on chest showing concentric circles collapsing toward an off-centre point, figure has unsettling stillness not aggressive in posture but deeply certain, hands at sides, calm committed expression, painted gouache style 1940s Astounding Science Fiction illustration, Chesley Bonestell influence, cold blue-grey palette, NO exoskeleton NO weapons NO helmet, transparent background, strong readable silhouette that contrasts with player character, NO glow NO technology just quiet human certainty, painterly brushwork, NO pixel art NO labels

---

## Animation States Needed

The following player animation states need sprites generated in priority order. All must use the Base Sprite prompt as foundation with pose modifications only. All must have DARK UNLIT EXOSKELETON — no glow in any sprite.

| State | Status | Notes |
|---|---|---|
| IDLE | PENDING | standing still, weight settled, slight breathing suggestion |
| WALK | PENDING | mid stride, weight forward, 2-3 frame cycle |
| JUMP RISING | PENDING | body compact, legs tucking, arms back |
| JUMP PEAK | PENDING | body extended, weightless moment, slight float |
| JUMP FALLING | PENDING | body loose, slight forward lean, bracing |
| LAND | PENDING | compression on contact, knees bent, one frame |
| GRAVITY ROTATING | PENDING | body bracing, exoskeleton collar beginning to rise |
| ABILITY ACTIVE | PENDING | one arm extended, gauntlet activated |
| HIT | PENDING | recoil, head back, one frame |
| DEAD | PENDING | collapse in current gravity direction |

---

## Iteration Log

Record failed prompt attempts here with notes on what went wrong so we do not repeat mistakes:

- **FAILED** — early platform attempts used isometric perspective — platforms appeared as 3D boxes not flat surfaces. **Fix:** specify strictly 2D side view, landscape orientation, player stands ON TOP.
- **FAILED** — early character attempts included compass/clock breastplate — too generic sci-fi. **Fix:** removed entirely, let spinal brace be the hero element.
- **FAILED** — early background attempts too warm and golden — lost serious tone. **Fix:** specify cold lighting, name drop Dean Ellis, specify NO warm cosy lighting.
- **FAILED** — Nano Banana created comparison cards when given version labels — interpreted A/B as instructions to make a labeled comparison sheet. **Fix:** never use version labels in prompts, use separate prompt submissions.
