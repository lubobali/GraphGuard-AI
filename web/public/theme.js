// S8b.4b: runs before the page paints, so a visitor who chose light sees no dark flash.
// A file of its own: the site's CSP allows no inline script. Key: lib/theme.js KEY.
try {
  if (localStorage.getItem("gg-theme") === "light") document.documentElement.dataset.theme = "light";
} catch (e) { /* blocked storage: dark */ }
