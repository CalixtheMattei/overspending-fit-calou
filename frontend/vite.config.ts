import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { defineConfig } from "vite";

const devProxyTarget = process.env.VITE_DEV_PROXY_TARGET ?? "http://localhost:8000";
const usePolling = process.env.CHOKIDAR_USEPOLLING === "true";
const pollingInterval = Number(process.env.CHOKIDAR_INTERVAL ?? "300");

export default defineConfig({
    plugins: [react(), tailwindcss()],
    resolve: {
        alias: {
            "@": path.resolve(__dirname, "./src"),
        },
    },
    server: {
        host: "0.0.0.0",
        port: 5173,
        watch: {
            usePolling,
            interval: Number.isFinite(pollingInterval) ? pollingInterval : 300,
        },
        proxy: {
            "/api": {
                target: devProxyTarget,
                changeOrigin: true,
                rewrite: (requestPath) => requestPath.replace(/^\/api/, ""),
            },
        },
    },
});
