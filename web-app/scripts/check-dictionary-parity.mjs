import fs from 'node:fs'
import path from 'node:path'

const ROOT = process.cwd()
const EN_DICT_PATH = path.join(ROOT, 'src', 'i18n', 'locales', 'en.ts')
const RU_DICT_PATH = path.join(ROOT, 'src', 'i18n', 'locales', 'ru.ts')

if (!fs.existsSync(EN_DICT_PATH) || !fs.existsSync(RU_DICT_PATH)) {
  console.error('Locale files not found. Expected src/i18n/locales/en.ts and src/i18n/locales/ru.ts')
  process.exit(1)
}

function extractKeys(content) {
  const keyPattern = /'([^']+)':/g
  const keys = []
  let match
  while ((match = keyPattern.exec(content)) !== null) {
    keys.push(match[1])
  }
  return keys
}

function findDuplicates(keys) {
  const counts = new Map()
  for (const key of keys) {
    counts.set(key, (counts.get(key) ?? 0) + 1)
  }
  return [...counts.entries()].filter(([, count]) => count > 1).map(([key]) => key)
}

const enContent = fs.readFileSync(EN_DICT_PATH, 'utf8')
const ruContent = fs.readFileSync(RU_DICT_PATH, 'utf8')

const enKeys = extractKeys(enContent)
const ruKeys = extractKeys(ruContent)

const enDuplicates = findDuplicates(enKeys)
const ruDuplicates = findDuplicates(ruKeys)

if (enDuplicates.length > 0 || ruDuplicates.length > 0) {
  if (enDuplicates.length > 0) {
    console.error('Duplicate keys in en dictionary:')
    for (const key of enDuplicates) {
      console.error(`- ${key}`)
    }
  }
  if (ruDuplicates.length > 0) {
    console.error('Duplicate keys in ru dictionary:')
    for (const key of ruDuplicates) {
      console.error(`- ${key}`)
    }
  }
  process.exit(1)
}

const enSet = new Set(enKeys)
const ruSet = new Set(ruKeys)

const missingInRu = [...enSet].filter((key) => !ruSet.has(key)).sort()
const missingInEn = [...ruSet].filter((key) => !enSet.has(key)).sort()

if (missingInRu.length > 0 || missingInEn.length > 0) {
  if (missingInRu.length > 0) {
    console.error('Missing in ru dictionary:')
    for (const key of missingInRu) {
      console.error(`- ${key}`)
    }
  }
  if (missingInEn.length > 0) {
    console.error('Missing in en dictionary:')
    for (const key of missingInEn) {
      console.error(`- ${key}`)
    }
  }
  process.exit(1)
}

console.log(`Dictionary parity OK. keys=${enSet.size}`)
