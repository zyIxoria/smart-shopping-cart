// Build frontend bằng esbuild (thay Vite vì môi trường phát triển không cài được Vite).
// Biến môi trường dùng tên VITE_* để sau này chuyển sang Vite không phải đổi code.
//   node build.mjs            -> dist/
//   node build.mjs --watch --serve   -> dev server http://localhost:5173 (proxy /api sang Backend)
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const esbuild = require('esbuild');
const here = path.dirname(fileURLToPath(import.meta.url));
const dist = path.join(here, 'dist');
const args = new Set(process.argv.slice(2));

// nạp .env (đơn giản) nếu có
const envFile = path.join(here, '.env');
if (fs.existsSync(envFile)) {
  for (const line of fs.readFileSync(envFile, 'utf8').split('\n')) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (m && process.env[m[1]] === undefined) process.env[m[1]] = m[2];
  }
}
const envDefine = {};
for (const k of ['VITE_API_BASE_URL', 'VITE_USE_MOCK', 'VITE_WS_URL', 'VITE_SIM_URL']) {
  envDefine[`import.meta.env.${k}`] = JSON.stringify(process.env[k] ?? '');
}

const options = {
  entryPoints: [path.join(here, 'src/main.jsx')],
  bundle: true,
  outdir: path.join(dist, 'assets'),
  entryNames: 'app',
  format: 'esm',
  target: 'es2020',
  minify: !args.has('--watch'),
  sourcemap: args.has('--watch'),
  jsx: 'automatic',
  loader: { '.jsx': 'jsx', '.json': 'json' },
  define: { ...envDefine, 'process.env.NODE_ENV': args.has('--watch') ? '"development"' : '"production"' },
  nodePaths: (process.env.NODE_PATH || '').split(path.delimiter).filter(Boolean),
  logLevel: 'info',
};

fs.rmSync(dist, { recursive: true, force: true });
fs.mkdirSync(dist, { recursive: true });
const rawHtml = fs.readFileSync(path.join(here, 'index.html'), 'utf8');
const versionedHtml = rawHtml
  .replace('/assets/app.js', `/assets/app.js?v=${Date.now()}`)
  .replace('/assets/app.css', `/assets/app.css?v=${Date.now()}`);
fs.writeFileSync(path.join(dist, 'index.html'), versionedHtml, 'utf8');

if (args.has('--watch')) {
  const ctx = await esbuild.context(options);
  await ctx.watch();
  if (args.has('--serve')) {
    const { host, port } = await ctx.serve({ servedir: dist, port: 5173, fallback: path.join(dist, 'index.html') });
    console.log(`Dev server: http://${host === '0.0.0.0' ? 'localhost' : host}:${port}  (đặt VITE_API_BASE_URL=http://localhost:8000)`);
  }
} else {
  await esbuild.build(options);
  console.log('Build xong ->', dist);
}
