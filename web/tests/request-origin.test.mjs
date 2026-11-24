import assert from "node:assert/strict";
import test from "node:test";
import { acceptsLocalOrigin } from "../app/_lib/request-origin.ts";

for (const host of ["127.0.0.1:3000", "localhost:3000", "[::1]:3000"]) {
  test(`explicit same-origin browser request through ${host}`, () => {
    assert.equal(acceptsLocalOrigin(`http://${host}`, host, "http:", "3000"), true);
  });
}

for (const [origin, host] of [
  ["https://other.invalid", "127.0.0.1:3000"],
  ["null", "127.0.0.1:3000"],
  ["http://127.0.0.1:3001", "127.0.0.1:3000"],
  ["https://127.0.0.1:3000", "127.0.0.1:3000"],
  ["http://localhost:3000", "127.0.0.1:3000"],
  ["http://other.invalid:3000", "other.invalid:3000"],
  ["http://127.0.0.1:3001", "127.0.0.1:3001"],
  ["http://127.0.0.1:3000", "other.invalid@127.0.0.1:3000"],
  ["http://127.0.0.1:3000", null],
]) {
  test(`reject ${origin} with Host ${host}`, () => {
    assert.equal(acceptsLocalOrigin(origin, host, "http:", "3000"), false);
  });
}

test("keep explicit CLI requests without browser Origin working", () => {
  assert.equal(acceptsLocalOrigin(null, "127.0.0.1:3000", "http:", "3000"), true);
});

test("hosted deployment accepts its own public origin", () => {
  assert.equal(acceptsLocalOrigin("https://demo.vercel.app", "demo.vercel.app", "https:", "", true), true);
});

for (const [origin, host] of [
  ["https://other.invalid", "demo.vercel.app"],
  ["http://demo.vercel.app", "demo.vercel.app"],
  ["null", "demo.vercel.app"],
]) {
  test(`hosted deployment rejects ${origin} with Host ${host}`, () => {
    assert.equal(acceptsLocalOrigin(origin, host, "https:", "", true), false);
  });
}

test("public hosts stay refused unless the deployment opts in", () => {
  assert.equal(acceptsLocalOrigin("https://demo.vercel.app", "demo.vercel.app", "https:", ""), false);
});
