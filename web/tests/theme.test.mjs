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

function environment(saved, dark, blocked = false) {
  const values = new Map(saved === undefined ? [] : [[config.THEME_STORAGE_KEY, saved]]);
  const mediaListeners = new Set(), storageListeners = new Set();
  const media = { matches: dark, addEventListener: (_, fn) => mediaListeners.add(fn), removeEventListener: (_, fn) => mediaListeners.delete(fn) };
  const queries = [];
  const document = { documentElement: { dataset: {} } };
  const localStorage = {
    getItem: key => { if (blocked) throw Error('Storage blocked'); return values.get(key) ?? null; },
    setItem: (key, value) => { if (blocked) throw Error('Storage blocked'); values.set(key, value); },
  };
  const matchMedia = query => { queries.push(query); return media; };
  const window = { matchMedia, addEventListener: (_, fn) => storageListeners.add(fn), removeEventListener: (_, fn) => storageListeners.delete(fn) };
  const globals = { document, localStorage, window, matchMedia };
  vm.runInNewContext(config.THEME_INIT_SCRIPT, globals);
  return { ...globals, values, media, queries, mediaListeners, storageListeners };
}

for (const scenario of [
  { name: 'first visit is light even on a dark system', system: true, expected: 'light', preference: 'default' },
  { name: 'first visit is light on a light system', system: false, expected: 'light', preference: 'default' },
  { name: 'saved dark is used on a light system', saved: 'dark', system: false, expected: 'dark', preference: 'dark' },
  { name: 'saved light is used on a dark system', saved: 'light', system: true, expected: 'light', preference: 'light' },
  { name: 'saved system follows a dark system', saved: 'system', system: true, expected: 'dark', preference: 'system' },
  { name: 'saved system follows a light system', saved: 'system', system: false, expected: 'light', preference: 'system' },
  { name: 'invalid saved values fall back to light', saved: 'invalid', system: true, expected: 'light', preference: 'default' },
  { name: 'blocked storage still opens in light', system: true, blocked: true, expected: 'light', preference: 'default' },
]) test(scenario.name, () => {
  const env = environment(scenario.saved, scenario.system, scenario.blocked);
  assert.equal(env.document.documentElement.dataset.theme, scenario.expected);
  assert.equal(env.document.documentElement.dataset.themePreference, scenario.preference);
  for (const query of env.queries) assert.equal(query, '(prefers-color-scheme: dark)');
});

function component(env) {
  let subscribe, snapshot, serverSnapshot;
  const evaluated = evaluate('_components/theme-toggle.tsx', env, {
    react: { useSyncExternalStore: (listen, read, server) => { subscribe = listen; snapshot ??= read; serverSnapshot ??= server; return read(); } },
    '../theme-config': config,
  });
  evaluated.useTheme();
  return { ...evaluated, subscribe, snapshot, serverSnapshot };
}
/** The radio inputs rendered by the Appearance picker. */
function radios(element, found = []) {
  if (!element || typeof element !== 'object') return found;
  if (Array.isArray(element)) { element.forEach(child => radios(child, found)); return found; }
  if (element.type === 'input' && element.props.type === 'radio') found.push(element.props);
  radios(element.props?.children, found);
  return found;
}

test('the picker shows Light, Dark and System with the saved choice checked', () => {
  const env = environment('dark', false), theme = component(env);
  const inputs = radios(theme.default());
  assert.deepEqual(inputs.map(input => input.value), ['light', 'dark', 'system']);
  assert.deepEqual(inputs.map(input => input.checked), [false, true, false]);
  assert.equal(new Set(inputs.map(input => input.name)).size, 1);
});

test('choosing a radio updates the document and the stored choice', () => {
  const env = environment(undefined, false), theme = component(env);
  assert.equal(theme.snapshot(), 'light');
  assert.deepEqual(radios(theme.default()).map(input => input.checked), [true, false, false]);
  radios(theme.default()).find(input => input.value === 'dark').onChange();
  assert.equal(theme.snapshot(), 'dark');
  assert.equal(env.values.get(config.THEME_STORAGE_KEY), 'dark');
  radios(theme.default()).find(input => input.value === 'light').onChange();
  assert.equal(theme.snapshot(), 'light');
  assert.equal(env.values.get(config.THEME_STORAGE_KEY), 'light');
  assert.equal(theme.serverSnapshot(), 'light');
});

test('choosing works when persistence is blocked', () => {
  const env = environment(undefined, false, true), theme = component(env);
  theme.setThemeChoice('dark');
  assert.equal(theme.snapshot(), 'dark');
  assert.equal(env.document.documentElement.dataset.themePreference, 'dark');
});

test('system changes are followed only while System is chosen', () => {
  const env = environment('system', false), theme = component(env);
  const unsubscribe = theme.subscribe(() => {});
  env.media.matches = true;
  env.mediaListeners.forEach(fn => fn());
  assert.equal(theme.snapshot(), 'dark');
  theme.setThemeChoice('light');
  env.mediaListeners.forEach(fn => fn());
  assert.equal(theme.snapshot(), 'light');
  unsubscribe();
});

test('a dark system does not change the default light theme', () => {
  const env = environment(undefined, false), theme = component(env);
  const unsubscribe = theme.subscribe(() => {});
  env.media.matches = true;
  env.mediaListeners.forEach(fn => fn());
  assert.equal(theme.snapshot(), 'light');
  unsubscribe();
});

test('another tab can update or clear the shared preference', () => {
  const env = environment('dark', false), theme = component(env);
  const unsubscribe = theme.subscribe(() => {});
  env.storageListeners.forEach(fn => fn({ key: config.THEME_STORAGE_KEY, newValue: 'light' }));
  assert.equal(theme.snapshot(), 'light');
  env.storageListeners.forEach(fn => fn({ key: config.THEME_STORAGE_KEY, newValue: 'dark' }));
  assert.equal(theme.snapshot(), 'dark');
  env.storageListeners.forEach(fn => fn({ key: config.THEME_STORAGE_KEY, newValue: null }));
  assert.equal(theme.snapshot(), 'light');
  assert.equal(env.document.documentElement.dataset.themePreference, 'default');
  unsubscribe();
});

test('chart and header subscribers share listeners and clean up on unmount', () => {
  const env = environment('dark', false), theme = component(env);
  let calls = 0;
  const one = theme.subscribe(() => { calls++; });
  const two = theme.subscribe(() => { calls++; });
  assert.equal(env.mediaListeners.size, 1);
  assert.equal(env.storageListeners.size, 1);
  theme.setThemeChoice('light');
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
for (const mode of ['light', 'dark']) test(`${mode} theme meets text, chart and focus contrast thresholds`, () => {
  const tokens = {};
  css.nodes.filter(node => node.selector === ':root' || (mode === 'dark' && node.selector === ':root[data-theme="dark"]')).forEach(node => node.nodes.forEach(decl => { if (decl.prop.startsWith('--')) tokens[decl.prop] = decl.value; }));
  const pairs = [
    ['--mode-text', '--mode-panel', 4.5], ['--mode-muted', '--mode-panel', 4.5],
    ['--mode-soft', '--mode-raised', 4.5], ['--mode-primary-ink', '--mode-primary', 4.5],
    ['--mode-success', '--mode-success-bg', 4.5], ['--mode-warning', '--mode-warning-bg', 4.5],
    ['--mode-danger', '--mode-danger-bg', 4.5], ['--mode-link', '--mode-panel', 3],
    ['--mode-chart-gold', '--mode-panel', 3], ['--mode-chart-green', '--mode-panel', 3],
    ['--mode-accent-text', '--mode-accent-bg', 4.5], ['--mode-neutral', '--mode-neutral-bg', 4.5],
    ['--mode-muted', '--mode-raised', 4.5], ['--mode-text', '--mode-bg', 4.5],
    ['--mode-success', '--mode-panel', 4.5], ['--mode-danger', '--mode-panel', 4.5], ['--mode-warning', '--mode-panel', 4.5],
    ['--mode-link', '--mode-raised', 4.5], ['--mode-chart-red', '--mode-panel', 3],
  ];
  for (const [foreground, background, minimum] of pairs) {
    const x = luminance(tokens[foreground]), y = luminance(tokens[background]);
    const ratio = (Math.max(x, y) + .05) / (Math.min(x, y) + .05);
    assert.ok(ratio >= minimum, `${foreground} / ${background}: ${ratio.toFixed(2)} < ${minimum}`);
  }
});
