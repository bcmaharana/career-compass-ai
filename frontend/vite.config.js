import react from "@vitejs/plugin-react";
import path from "node:path";
import { defineConfig } from "vite";
// https://vitejs.dev/config/
export default defineConfig({
    plugins: [react()],
    resolve: {
        alias: {
            "@": path.resolve(__dirname, "./src"),
        },
    },
    server: {
        port: 5173,
        proxy: {
            // Local dev convenience: frontend calls /api/* and Vite forwards it
            // to the backend, avoiding CORS entirely in development. Production
            // deployments route this at the load balancer/gateway layer instead.
            "/api": {
                target: "http://localhost:8000",
                changeOrigin: true,
            },
        },
    },
});
