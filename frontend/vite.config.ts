import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The app is served in production by the Python web demo on port 8765
// (it serves the built `dist/`). Vite is used only to build that bundle.
export default defineConfig({
  plugins: [react()],
});
