import { readFileSync, writeFileSync } from 'fs';
import { join } from 'path';
import { fileURLToPath } from 'url';
import { dirname } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const distPath = join(__dirname, '..', 'dist');
const indexPath = join(distPath, 'index.html');

let content = readFileSync(indexPath, 'utf-8');

// Replace absolute paths with relative paths
content = content.replace(/src="\/assets\//g, 'src="./assets/');
content = content.replace(/href="\/assets\//g, 'href="./assets/');
content = content.replace(/href="\/vite\.svg"/g, 'href="./vite.svg"');

writeFileSync(indexPath, content, 'utf-8');
console.log('Fixed asset paths in index.html');
