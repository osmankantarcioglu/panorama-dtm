import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { join, extname, normalize } from 'node:path';

const ROOT = process.cwd();
// 3000 is often taken by another local project; PORT overrides.
const PORT = Number(process.env.PORT) || 4300;

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.avif': 'image/avif',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
};

async function resolve(urlPath) {
  // strip query/hash, decode, and block path traversal
  const clean = decodeURIComponent(urlPath.split('?')[0].split('#')[0]);
  const safe = normalize(clean).replace(/^([/\\])+/, '');
  if (safe.startsWith('..')) return null;

  let target = join(ROOT, safe);
  try {
    const s = await stat(target);
    if (s.isDirectory()) target = join(target, 'index.html');
  } catch {
    // fall through: maybe an extensionless path
    if (!extname(target)) target += '.html';
  }
  return target;
}

createServer(async (req, res) => {
  const target = await resolve(req.url || '/');
  if (!target) {
    res.writeHead(400).end('Bad request');
    return;
  }
  try {
    const body = await readFile(target);
    res.writeHead(200, {
      'Content-Type': MIME[extname(target).toLowerCase()] || 'application/octet-stream',
      'Cache-Control': 'no-store',
    });
    res.end(body);
  } catch {
    res.writeHead(404, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end('<h1>404</h1><p>Not found: ' + target + '</p>');
  }
}).listen(PORT, () => {
  console.log(`Serving ${ROOT} at http://localhost:${PORT}`);
});
