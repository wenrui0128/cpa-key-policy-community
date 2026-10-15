import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
// Inline the management UI without a separate single-file dependency.
function inlineManagementUI(): Plugin {
  return {
    name: "inline-management-ui",
    enforce: "post",
    apply: "build",
    generateBundle(_options, bundle) {
      const entry = bundle["index.html"];
      if (!entry || entry.type !== "asset" || typeof entry.source !== "string") {
        throw new Error("Missing management UI HTML");
      }
      let html = entry.source;
      for (const [name, file] of Object.entries(bundle)) {
        if (name === "index.html") continue;
        let inlined = false;
        if (file.type === "chunk") {
          if (file.imports.length || file.dynamicImports.length) {
            throw new Error("Management UI must be a single JavaScript chunk");
          }
          html = html.replace(/<script\b[^>]*\bsrc="([^"]+)"[^>]*><\/script>/g, (tag, src: string) => {
            if (!src.endsWith(name)) return tag;
            inlined = true;
            return `<script type="module">${file.code.replace(/<\/script/gi, "<\\/script")}</script>`;
          });
        } else if (name.endsWith(".css")) {
          const css = typeof file.source === "string" ? file.source : new TextDecoder().decode(file.source);
          html = html.replace(/<link\b[^>]*\bhref="([^"]+)"[^>]*>/g, (tag, href: string) => {
            if (!href.endsWith(name)) return tag;
            inlined = true;
            return `<style>${css.replace(/<\/style/gi, "<\\/style")}</style>`;
          });
        }
        if (!inlined) throw new Error("Unembedded management UI asset: " + name);
        delete bundle[name];
      }
      entry.source = html;
    },
  };
}

// CPA base URL used by the dev-server proxy. Override with VITE_CPA_BASE.
const cpaBase = process.env.VITE_CPA_BASE ?? "http://127.0.0.1:8317";

// When hosted inside CPA, the app is served at
// /v0/resource/plugins/cpa-key-policy/index.html. Production builds must use
// that base so inlined asset URLs resolve. In dev we keep "/" for convenience.
const base = process.env.VITE_HOSTED === "1"
  ? "/v0/resource/plugins/cpa-key-policy/"
  : "/";

export default defineConfig({
  base,
  plugins: [react(), inlineManagementUI()],
  // Single-file build: inline everything into index.html.
  build: {
    assetsInlineLimit: 100000000,
    cssCodeSplit: false,
    rolldownOptions: {
      output: { codeSplitting: false },
    },
  },
  server: {
    port: 5174,
    proxy: {
      // Proxy management API calls to CPA during development to avoid CORS.
      "/v0/management": { target: cpaBase, changeOrigin: true },
      "/v1/models": { target: cpaBase, changeOrigin: true },
    },
  },
});
