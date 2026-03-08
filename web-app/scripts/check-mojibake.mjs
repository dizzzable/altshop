import fs from 'node:fs'
import path from 'node:path'

const ROOT = process.cwd()
const SRC_ROOT = path.join(ROOT, 'src')
const FILE_EXTENSIONS = new Set(['.ts', '.tsx', '.js', '.jsx', '.css', '.md'])

const suspiciousFragments = [
  'РќР',
  'РџР',
  'РЎР',
  'РўР',
  'РёР',
  'СЃ',
  'С‚',
  'СЊ',
]

function walkFiles(dirPath, result = []) {
  const entries = fs.readdirSync(dirPath, { withFileTypes: true })
  for (const entry of entries) {
    const fullPath = path.join(dirPath, entry.name)
    if (entry.isDirectory()) {
      if (entry.name === 'node_modules' || entry.name === 'dist') {
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

const files = walkFiles(SRC_ROOT)
const issues = []

for (const filePath of files) {
  const content = fs.readFileSync(filePath, 'utf8')
  const found = findSuspiciousLines(content)
  if (found.length > 0) {
    issues.push({ filePath, found })
  }
}

if (issues.length > 0) {
  console.error('Found suspicious mojibake-like fragments:')
  for (const issue of issues) {
    const relativePath = path.relative(ROOT, issue.filePath).replaceAll('\\', '/')
    for (const hit of issue.found.slice(0, 10)) {
      console.error(`- ${relativePath}:${hit.lineNumber}: ${hit.line.trim()}`)
    }
    if (issue.found.length > 10) {
      console.error(`  ... and ${issue.found.length - 10} more lines`)
    }
  }
  process.exit(1)
}

console.log('No mojibake-like fragments found.')
