import fs from 'node:fs'
import path from 'node:path'

const ROOT = process.cwd()
const TARGETS = [
  'src',
  'tests',
  'assets/translations',
  'web-app/src',
  'web-app/scripts',
  'web-app/AUTH_SYSTEM.md',
  'web-app/LANDING_PAGE.md',
]
const FILE_EXTENSIONS = new Set([
  '.py',
  '.ftl',
  '.ts',
  '.tsx',
  '.js',
  '.jsx',
  '.css',
  '.md',
  '.mjs',
])
const SKIP_DIR_NAMES = new Set([
  '.git',
  '.venv',
  '.mypy_cache',
  '.pytest_cache',
  '.ruff_cache',
  '__pycache__',
  'node_modules',
  'dist',
])
const ALLOWED_FILES = new Set([
  'tests/core/test_translation_assets.py',
  'tests/core/test_main_menu_render.py',
  'tests/core/test_runtime_localization_guards.py',
  'web-app/scripts/check-mojibake.mjs',
])

const suspiciousFragments = [
  'РЎ',
  'Рџ',
  'Рќ',
  'Р”',
  'СЃ',
  'С‚',
  'СЊ',
  'вЂ',
  'вќ',
  'рџ',
  'пёЏ',
]

function walkFiles(dirPath, result = []) {
  const entries = fs.readdirSync(dirPath, { withFileTypes: true })
  for (const entry of entries) {
    const fullPath = path.join(dirPath, entry.name)
    if (entry.isDirectory()) {
      if (SKIP_DIR_NAMES.has(entry.name)) {
        continue
      }
      walkFiles(fullPath, result)
      continue
    }

    if (!FILE_EXTENSIONS.has(path.extname(entry.name))) {
      continue
    }
    result.push(fullPath)
  }
  return result
}

function collectFiles(targetPath, result = []) {
  if (!fs.existsSync(targetPath)) {
    return result
  }

  const stat = fs.statSync(targetPath)
  if (stat.isDirectory()) {
    return walkFiles(targetPath, result)
  }

  if (FILE_EXTENSIONS.has(path.extname(targetPath))) {
    result.push(targetPath)
  }

  return result
}

function findSuspiciousLines(content) {
  const lines = content.split(/\r?\n/)
  const found = []
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i]
    if (suspiciousFragments.some((fragment) => line.includes(fragment))) {
      found.push({ lineNumber: i + 1, line })
    }
  }
  return found
}

const files = TARGETS.flatMap((target) => collectFiles(path.join(ROOT, target)))
const issues = []

for (const filePath of files) {
  const relativePath = path.relative(ROOT, filePath).replaceAll('\\', '/')
  if (ALLOWED_FILES.has(relativePath)) {
    continue
  }

  const content = fs.readFileSync(filePath, 'utf8')
  const found = findSuspiciousLines(content)
  if (found.length > 0) {
    issues.push({ filePath: relativePath, found })
  }
}

if (issues.length > 0) {
  console.error('Found suspicious mojibake-like fragments:')
  for (const issue of issues) {
    for (const hit of issue.found.slice(0, 10)) {
      console.error(`- ${issue.filePath}:${hit.lineNumber}: ${hit.line.trim()}`)
    }
    if (issue.found.length > 10) {
      console.error(`  ... and ${issue.found.length - 10} more lines`)
    }
  }
  process.exit(1)
}

console.log('No mojibake-like fragments found.')
