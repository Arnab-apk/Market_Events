# React Bits components

Aurora and SpotlightCard are vendored from the official [React Bits repository](https://github.com/DavidHDev/react-bits) (`src/ts-default`), fetched 2026-10-27. See the accompanying `LICENSE.md` for the upstream MIT + Commons Clause terms.

Local adaptations: lifecycle-managed reduced-motion settings, global effects pause, and scheduler safeguards for hidden/offscreen content. Styling is customized in `app/hero.css` for the research workspace. Aurora uses WebGL2 with a CSS gradient fallback; no third-party network request is needed at runtime.
