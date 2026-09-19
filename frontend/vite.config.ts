import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
export default defineConfig(({mode}) => {
  const env = loadEnv(mode, ".", "");
  return {
  plugins: [react(), tailwindcss()],
  server: { port: 5173, strictPort: true, proxy: { "/api": { target: env.LOADCHECK_API_TARGET || "http://127.0.0.1:8000", changeOrigin: true } } },
  build: {
    rollupOptions: {
      input: { app: new URL("./index.html", import.meta.url).pathname, preview: new URL("./preview.html", import.meta.url).pathname },
      output: {
        manualChunks: {
          maps: ["leaflet", "react-leaflet"],
          charts: ["recharts"],
        },
      },
    },
  },
};
});
