# Balatro Calculator rendering assets

The embedded `m6x11plus.ttf` font is by Daniel Linssen, distributed via the
same pinned calculator repository. Its author's page permits use with
attribution: https://managore.itch.io/m6x11 . The viewer footer includes this
credit. The calculator's MIT notice below does not replace the font credit.

Card atlas coordinates, sprite sheets, scoring logic, value-input labels,
and the layered rendering approach
are adapted from [EFHIII/balatro-calculator](https://github.com/EFHIII/balatro-calculator)
at commit `55322d59197ba08c16874a54b59ac0d443c8ab32`.

Included atlases: `8BitDeck.png`, `Jokers.png`, `Enhancers.png`, `Editions.png`.
They are embedded into `TrajectoryViewer.svelte` because Training Gym uploads
a single-file component. `balatro-sim.js` is embedded with its scoring logic
unchanged, plus a Svelte compiler annotation. No external image or code
requests are made when calculating. Original Balatro artwork remains the property of its
respective rights holders; the upstream project's license is reproduced below.

```
MIT License

Copyright (c) 2024 Saffron Haas

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
