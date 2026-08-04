import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Tailwind v4 is a Vite plugin now — there is no tailwind.config.js and no
// postcss.config.js. The design tokens live in src/index.css under @theme.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173 },
});
