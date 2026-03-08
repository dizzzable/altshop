#!/bin/bash

# API Client Generation Script for AltShop
# Generates TypeScript types and API client from FastAPI OpenAPI schema

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   AltShop API Client Generator         ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# Change to web-app directory
cd "$(dirname "$0")/../web-app"

# Step 1: Check if backend is running
echo -e "${YELLOW}📡 Step 1/4: Checking backend...${NC}"
if ! curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/openapi.json | grep -q "200"; then
    echo -e "${RED}❌ Backend is not running or /openapi.json not available${NC}"
    echo ""
    echo "Please start the backend:"
    echo "  cd D:\\altshop-0.9.3"
    echo "  uv run python -m src"
    echo ""
    exit 1
fi
echo -e "${GREEN}✅ Backend is running${NC}"
echo ""

# Step 2: Download OpenAPI schema
echo -e "${YELLOW}📥 Step 2/4: Downloading OpenAPI schema...${NC}"
curl -s http://localhost:5000/openapi.json -o openapi.json

if [ ! -f openapi.json ] || [ ! -s openapi.json ]; then
    echo -e "${RED}❌ Failed to download OpenAPI schema${NC}"
    exit 1
fi

SCHEMA_SIZE=$(wc -c < openapi.json)
echo -e "${GREEN}✅ Schema downloaded (${SCHEMA_SIZE} bytes)${NC}"
echo ""

# Step 3: Preprocess (optional - cleanup operation IDs)
echo -e "${YELLOW}🔧 Step 3/4: Preprocessing schema...${NC}"
if command -v node &> /dev/null; then
    # Create preprocessing script if it doesn't exist
    if [ ! -f scripts/preprocess-openapi.js ]; then
        cat > scripts/preprocess-openapi.js << 'EOF'
import * as fs from 'fs'

async function preprocessOpenAPI(filePath) {
  try {
    const data = await fs.promises.readFile(filePath)
    const openapiContent = JSON.parse(data)
    
    let modified = false
    
    // Clean up operation IDs for better method names
    for (const pathKey of Object.keys(openapiContent.paths)) {
      const pathData = openapiContent.paths[pathKey]
      for (const method of Object.keys(pathData)) {
        const operation = pathData[method]
        if (operation.tags && operation.tags.length > 0 && operation.operationId) {
          const tag = operation.tags[0]
          const operationId = operation.operationId
          const prefix = `${tag}-`
          if (operationId.startsWith(prefix)) {
            operation.operationId = operationId.substring(prefix.length)
            modified = true
          }
        }
      }
    }
    
    if (modified) {
      await fs.promises.writeFile(filePath, JSON.stringify(openapiContent, null, 2))
      console.log('✅ Schema preprocessed successfully')
    } else {
      console.log('ℹ️  No preprocessing needed')
    }
  } catch (error) {
    console.error('❌ Preprocessing failed:', error.message)
    process.exit(1)
  }
}

preprocessOpenAPI('./openapi.json')
EOF
    fi
    
    node scripts/preprocess-openapi.js
else
    echo -e "${YELLOW}⚠️  Node not found, skipping preprocessing${NC}"
fi
echo ""

# Step 4: Generate TypeScript client
echo -e "${YELLOW}🔨 Step 4/4: Generating TypeScript client...${NC}"

# Check if hey-api is installed
if ! npm list @hey-api/openapi-ts &> /dev/null; then
    echo -e "${YELLOW}⚠️  @hey-api/openapi-ts not found, installing...${NC}"
    npm install --save-dev @hey-api/openapi-ts
fi

# Generate
npm run generate:api

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   ✅ Generation Successful!            ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}📦 Generated files:${NC}"
    if [ -d "src/generated" ]; then
        ls -la src/generated/
    else
        echo -e "${YELLOW}⚠️  Generated directory not found${NC}"
    fi
    echo ""
    echo -e "${BLUE}✨ Usage example:${NC}"
    echo "   ${YELLOW}import { UsersService } from './src/generated'${NC}"
    echo "   ${YELLOW}const user = await UsersService.getUserMe()${NC}"
    echo ""
    echo -e "${BLUE}📚 Next steps:${NC}"
    echo "   1. Review generated types in ${YELLOW}src/generated/types.ts${NC}"
    echo "   2. Update imports in your components"
    echo "   3. Use generated services instead of manual API calls"
    echo ""
    echo -e "${YELLOW}💡 Tip: Run this script whenever backend changes!${NC}"
    echo ""
else
    echo ""
    echo -e "${RED}❌ Generation failed${NC}"
    echo "Check the error messages above"
    exit 1
fi
