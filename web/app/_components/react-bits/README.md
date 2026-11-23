# React Bits components

All components here are vendored from the official [React Bits repository](https://github.com/DavidHDev/react-bits) (`src/ts-default`, the TypeScript + plain-CSS variants). See `LICENSE.md` for the upstream MIT + Commons Clause terms. No React Bits npm package or extra runtime dependency is used.

| Component | Upstream path | Fetched | Used for |
| --- | --- | --- | --- |
| Aurora | `Backgrounds/Aurora` | 2026-10-27 | The only animated background (overview tour card) |
| SpotlightCard | `Components/SpotlightCard` | 2026-10-27 | Metric cards |
| Stepper | `Components/Stepper` | 2026-11-21, commit `701a8acc34f7` | Guided demo tour |
| CountUp | `TextAnimations/CountUp` | 2026-11-21, commit `701a8acc34f7` | Headline numbers (always land on the exact value) |
| AnimatedContent | `Animations/AnimatedContent` | 2026-11-21, commit `701a8acc34f7` | Section (view) transitions |
| ShinyText | `TextAnimations/ShinyText` | 2026-11-21, commit `701a8acc34f7` | Overview title only |

## Local adaptations

Each file starts with a comment listing its own changes. In summary:

- **Reduced motion:** every component reads `../use-reduced-motion`. When the system asks for reduced motion, numbers render at their final value, the title is static, transitions are skipped, and Aurora stays paused. The app's "Effects" toggle also pauses Aurora and CountUp.
- **No new dependencies:**
  - CountUp's `motion/react` helpers became small native functions (`requestAnimationFrame`, IntersectionObserver).
  - AnimatedContent's GSAP/ScrollTrigger became the Web Animations API. GSAP-only options (scrub, wipe, stagger, tilt, disappear) were not ported.
  - Stepper's `@hugeicons` icons became `lucide-react`, which is already a dependency.
- **Motion budget:** Stepper transitions are capped at 360 ms (the app's rule is 400 ms or less).
- **Formatting:** CountUp gained an optional `formatter` prop, so every frame and the final value use the app's Indian number format.
- **Earlier components:** Aurora and SpotlightCard keep their lifecycle-managed reduced-motion settings, the global effects pause, and scheduler safeguards for hidden or offscreen content. Aurora uses WebGL2 with a CSS gradient fallback, and nothing makes a third-party network request at runtime.
