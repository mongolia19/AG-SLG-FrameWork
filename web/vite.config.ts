import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

function uriMalformedShield() {
  return {
    name: 'uri-malformed-shield',
    configureServer(server: any) {
      // 1. Pre-middleware: sanitize incoming req.url before Vite's transform middleware
      server.middlewares.use((req: any, _res: any, next: any) => {
        if (req.url) {
          try {
            decodeURI(req.url);
          } catch {
            // Fix unencoded or stray '%' in URL
            try {
              req.url = req.url.replace(/%(?![0-9a-fA-F]{2})/g, '%25');
              decodeURI(req.url);
            } catch {
              req.url = req.url.replace(/%/g, '%25');
            }
          }
        }
        next();
      });

      // 2. Post-middleware: catch any uncaught URIError to prevent Vite 500 red error overlay
      return () => {
        server.middlewares.use((err: any, _req: any, res: any, next: any) => {
          if (err instanceof URIError || (err && err.message && err.message.includes('URI malformed'))) {
            res.statusCode = 400;
            res.end('Bad Request: Malformed URI');
            return;
          }
          next(err);
        });
      };
    },
  };
}

export default defineConfig({
  plugins: [uriMalformedShield(), react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
      '/scenarios': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
      '/assets': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
    },
  },
});

