import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';
import postcss from 'postcss';

const requireModule = createRequire(import.meta.url);
const app = path.join(path.dirname(fileURLToPath(import.meta.url)), '../app');
function evaluate(file, globals = {}, dependencies = {}) {
  const exports = {};
  const code = ts.transpileModule(fs.readFileSync(path.join(app, file), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const context = { exports, require: name => dependencies[name] || requireModule(name), ...globals };
  vm.runInNewContext(code, context);
  return exports;
}
const config = evaluate('theme-config.ts');

function environment(saved, light, blocked = false) {
  const values = new Map(saved === undefined ? [] : [[config.THEME_STORAGE_KEY, saved]]);
  const mediaListeners = new Set(), storageListeners = new Set();
  const media = { matches: light, addEventListener: (_, fn) => mediaListeners.add(fn), removeEventListener: (_, fn) => mediaListeners.delete(fn) };
  const document = { documentElement: { dataset: {} } };
  const localStorage = {
    getItem: key => { if (blocked) throw Error('Storage blocked'); return values.get(key) ?? null; },
    setItem: (key, value) => { if (blocked) throw Error('Storage blocked'); values.set(key, value); },
  };
  const window = { matchMedia: () => media, addEventListener: (_, fn) => storageListeners.add(fn), removeEventListener: (_, fn) => storageListeners.delete(fn) };
  const globals = { document, localStorage, window, matchMedia: window.matchMedia };
  vm.runInNewContext(config.THEME_INIT_SCRIPT, globals);
  return { ...globals, values, media, mediaListeners, storageListeners };
}

for (const scenario of [
  { name: 'saved light overrides a dark system', saved: 'light', system: false, expected: 'light' },
  { name: 'saved dark overrides a light system', saved: 'dark', system: true, expected: 'dark' },
  { name: 'first visit follows a light system', system: true, expected: 'light' },
  { name: 'invalid saved values fall back to system', saved: 'invalid', system: false, expected: 'dark' },
  { name: 'blocked storage still uses system preference', system: true, blocked: true, expected: 'light' },
]) test(scenario.name, () => {
  const env = environment(scenario.saved, scenario.system, scenario.blocked);
  assert.equal(env.document.documentElement.dataset.theme, scenario.expected);
});

function component(env) {
  let subscribe, snapshot, serverSnapshot;
  const evaluated = evaluate('_components/theme-toggle.tsx', env, {
    react: { useSyncExternalStore: (listen, read, server) => { subscribe = listen; snapshot = read; serverSnapshot = server; return read(); } },
    '../theme-config': config,
    'lucide-react': { Sun: () => null, Moon: () => null },
  });
  evaluated.useTheme();
  return { ...evaluated, subscribe, snapshot, serverSnapshot };
}

test('toggle updates the document, accessible action label, and stored choice', () => {
  const env = environment('dark', false), toggle = component(env);
  let button = toggle.default();
  assert.equal(button.props['aria-label'], 'Switch to light mode');
  button.props.onClick();
  assert.equal(toggle.snapshot(), 'light');
  assert.equal(env.values.get(config.THEME_STORAGE_KEY), 'light');
  button = toggle.default();
  assert.equal(button.props['aria-label'], 'Switch to dark mode');
  button.props.onClick();
  assert.equal(toggle.snapshot(), 'dark');
  assert.equal(toggle.serverSnapshot(), 'dark');
});

test('manual toggling works when persistence is blocked', () => {
  const env = environment(undefined, false, true), toggle = component(env);
  toggle.default().props.onClick();
  assert.equal(toggle.snapshot(), 'light');
  assert.equal(env.document.documentElement.dataset.themePreference, 'manual');
});

test('system changes are followed until the user chooses a mode', () => {
  const env = environment(undefined, false), toggle = component(env);
  const unsubscribe = toggle.subscribe(() => {});
  env.media.matches = true;
  env.mediaListeners.forEach(fn => fn());
  assert.equal(toggle.snapshot(), 'light');
  toggle.default().props.onClick();
  env.mediaListeners.forEach(fn => fn());
  assert.equal(toggle.snapshot(), 'dark');
  unsubscribe();
});

test('another tab can update or clear the shared preference', () => {
  const env = environment('dark', true), toggle = component(env);
  const unsubscribe = toggle.subscribe(() => {});
  env.storageListeners.forEach(fn => fn({ key: config.THEME_STORAGE_KEY, newValue: 'light' }));
  assert.equal(toggle.snapshot(), 'light');
  env.storageListeners.forEach(fn => fn({ key: config.THEME_STORAGE_KEY, newValue: 'dark' }));
  assert.equal(toggle.snapshot(), 'dark');
  env.storageListeners.forEach(fn => fn({ key: config.THEME_STORAGE_KEY, newValue: null }));
  assert.equal(toggle.snapshot(), 'light');
  assert.equal(env.document.documentElement.dataset.themePreference, 'system');
  unsubscribe();
});

test('chart and header subscribers share listeners and clean up on unmount', () => {
  const env = environment('dark', false), toggle = component(env);
  let calls = 0;
  const one = toggle.subscribe(() => { calls++; });
  const two = toggle.subscribe(() => { calls++; });
  assert.equal(env.mediaListeners.size, 1);
  assert.equal(env.storageListeners.size, 1);
  toggle.default().props.onClick();
  assert.equal(calls, 2);
  one();
  assert.equal(env.mediaListeners.size, 1);
  two();
  assert.equal(env.mediaListeners.size, 0);
  assert.equal(env.storageListeners.size, 0);
});

function luminance(hex) {
  const rgb = hex.slice(1).match(/../g).map(x => parseInt(x, 16) / 255).map(x => x <= .04045 ? x / 12.92 : ((x + .055) / 1.055) ** 2.4);
  return rgb[0] * .2126 + rgb[1] * .7152 + rgb[2] * .0722;
}
const css = postcss.parse(fs.readFileSync(path.join(app, 'tokens.css'), 'utf8'));
for (const mode of ['dark', 'light']) test(`${mode} theme meets text, chart and focus contrast thresholds`, () => {
  const tokens = {};
  css.nodes.filter(node => node.selector === ':root' || (mode === 'light' && node.selector === ':root[data-theme="light"]')).forEach(node => node.nodes.forEach(decl => { if (decl.prop.startsWith('--')) tokens[decl.prop] = decl.value; }));
  const pairs = [
    ['--mode-text', '--mode-panel', 4.5], ['--mode-muted', '--mode-panel', 4.5],
    ['--mode-soft', '--mode-raised', 4.5], ['--mode-primary-ink', '--mode-primary', 4.5],
    ['--mode-success', '--mode-success-bg', 4.5], ['--mode-warning', '--mode-warning-bg', 4.5],
    ['--mode-danger', '--mode-danger-bg', 4.5], ['--mode-link', '--mode-panel', 3],
    ['--mode-chart-gold', '--mode-panel', 3], ['--mode-chart-green', '--mode-panel', 3],
  ];
  for (const [foreground, background, minimum] of pairs) {
    const x = luminance(tokens[foreground]), y = luminance(tokens[background]);
    const ratio = (Math.max(x, y) + .05) / (Math.min(x, y) + .05);
    assert.ok(ratio >= minimum, `${foreground} / ${background}: ${ratio.toFixed(2)} < ${minimum}`);
  }
});
