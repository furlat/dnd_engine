## 💾 Download

Installation:
```bash
npm install pixi.js@8.22.0
```

Development Build:
- https://cdn.jsdelivr.net/npm/pixi.js@8.22.0/dist/pixi.js
- https://cdn.jsdelivr.net/npm/pixi.js@8.22.0/dist/pixi.mjs

Production Build:
- https://cdn.jsdelivr.net/npm/pixi.js@8.22.0/dist/pixi.min.js
- https://cdn.jsdelivr.net/npm/pixi.js@8.22.0/dist/pixi.min.mjs

Documentation:
- https://pixijs.download/v8.22.0/docs/index.html

## Changed
https://github.com/pixijs/pixijs/compare/v8.21.0...v8.22.0

### 🚨 Behavior Change
* fix: tab cannot activate the accessibility layer on a fresh page by @synath in https://github.com/pixijs/pixijs/pull/12220
  * Pressing Tab now activates the accessibility layer on a fresh page when `activateOnTab` is left at its default of `true`. This restores the documented default, which regressed in v8.14.0. To keep Tab from activating it:
  ```ts
  await app.init({ accessibilityOptions: { activateOnTab: false } });
  ```
* fix: apply accessibleText to button and recycled accessible elements by @synath in https://github.com/pixijs/pixijs/pull/12221
  * `accessibleText` now applies to the default `button` type and to accessible elements recycled from the pool.

### 🎁 Added
* feat: add a federated contextmenu event by @Zyie in https://github.com/pixijs/pixijs/pull/12250
  * Containers now receive `contextmenu` and `contextmenucapture` events, also available as the `oncontextmenu` handler property. The event is a `FederatedPointerEvent` that PixiJS hit-tests and propagates like `pointerdown`, and `eventFeatures.click` gates it.
  ```ts
  sprite.eventMode = 'static';
  sprite.on('contextmenu', (event) =>
  {
      event.preventDefault(); // keeps the browser menu closed
      openMenuAt(event.global);
  });
  ```
* feat: sRGB view formats and transient MSAA colour on WebGPU by @GoodBoyDigital in https://github.com/pixijs/pixijs/pull/12225
  * New `transient` renderer option (WebGPU, with `antialias`) discards the canvas's multisample depth/stencil buffer at the end of each pass, and its color buffer too on GPUs that aren't tile-based. 
  ```ts
  await app.init({ preference: 'webgpu', antialias: true, transient: true });
  ```
* feat: 3D textures, storage textures and 3D mipmaps by @GoodBoyDigital in https://github.com/pixijs/pixijs/pull/12248
* feat: partial uploads for BufferImageSource via update(start, end) by @GoodBoyDigital in https://github.com/pixijs/pixijs/pull/12227

### 🐛 Fixed
* fix: integer texture formats on WebGL and WebGPU by @GoodBoyDigital in https://github.com/pixijs/pixijs/pull/12230
* fix: nested filters crash after renderer resize by @Zyie in https://github.com/pixijs/pixijs/pull/12257
* fix: indexed loops instead of for...in on every draw by @GoodBoyDigital in https://github.com/pixijs/pixijs/pull/12229
* fix: declare accessibilityOptions on the public renderer options by @synath in https://github.com/pixijs/pixijs/pull/12222
* fix: array uniform sync over-reads and overlaps matrix elements by @GoodBoyDigital in https://github.com/pixijs/pixijs/pull/12228
* fix: blend filter backdrop when every parent filter is skipped by @Zyie in https://github.com/pixijs/pixijs/pull/12263
* fix: don't warn about unread attributes that already have a format by @Zyie in https://github.com/pixijs/pixijs/pull/12267

### 🧹 Chores
* chore: clarify web font family naming by @Hugohong258 in https://github.com/pixijs/pixijs/pull/12216
* chore: correct TilingSprite texture, width and height defaults by @ZainnQureshii in https://github.com/pixijs/pixijs/pull/12269

## New Contributors
* @synath made their first contribution in https://github.com/pixijs/pixijs/pull/12220
* @ZainnQureshii made their first contribution in https://github.com/pixijs/pixijs/pull/12269