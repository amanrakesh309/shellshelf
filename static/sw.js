/* ShellShelf service worker: caches the app shell ONLY (HTML/CSS/JS, manifest,
 * icons) so the installed app opens fast and its chrome survives brief network
 * hiccups. NEVER caches API responses, shortcut data, shell file contents,
 * command output, or errors: every request under /api/, the worker script
 * itself, non-GET requests, and cross-origin requests always go to the network
 * and are never stored. The Python backend on localhost remains required for
 * all shortcut data and launching. */

"use strict";

const SHELL_CACHE = "shellshelf-shell-v1";

// Exact same-origin paths that make up the app shell. Nothing else is cached.
const SHELL_ASSETS = [
  "/",
  "/index.html",
  "/static/styles.css",
  "/static/app.js",
  "/static/manifest.webmanifest",
  "/static/icons/icon.svg",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  "/static/icons/apple-touch-icon.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      .then((cache) => cache.addAll(SHELL_ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== SHELL_CACHE).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  // Network-only: anything that is not a same-origin GET of a shell asset.
  // In particular, shortcut data, import previews, launches, and outputs
  // (all under /api/) are never served from — or written to — the cache.
  if (event.request.method !== "GET" || url.origin !== self.location.origin) {
    return;
  }
  if (url.pathname.startsWith("/api/") || url.pathname === "/sw.js") {
    return;
  }
  if (!SHELL_ASSETS.includes(url.pathname)) {
    return;
  }
  event.respondWith(
    caches.match(event.request).then((hit) => hit || fetch(event.request))
  );
});
