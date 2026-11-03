# FocusBoard VR

A hands-first, seated productivity experience for Meta VR devices, built with Meta's Immersive Web SDK (IWSDK) for the Meta VR Start Developer Competition 2026.

You sit at a calm floating desk: pinch sticky notes off the tray, park a thought where it belongs, and keep the focus ring in your hand while you think. No locomotion, no controllers needed. Everything is hands-first and works seated.

## Interactions

1. **Grab** pinch a sticky note to pick it up
2. **Hold** grab the focus ring and turn it in your hand
3. **Park** set a note down to park the thought

## Stack

- Immersive Web SDK (`@iwsdk/core`), VR mode with hand tracking
- Vite + TypeScript
- GitHub Pages deployment (no paid hosting)

## Local development

```bash
npm install
npm run dev
```

## Production build

```bash
npm run build   # outputs to dist/
```

## Deploy

`dist/` is published to the `gh-pages` branch and served at:
https://shlokgit-04.github.io/focusboard-vr/

MIT licensed. Built by Shlok Vane (@shlokgit-04).
