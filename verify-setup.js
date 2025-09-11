#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

console.log('🧪 OpenAI Proxy Service - Setup Verification\n');

// Check if required files exist
const requiredFiles = [
  'app.js',
  'auth.routes.js', 
  'openai.routes.js',
  'database.js',
  'middleware.js',
  'history.service.js',
  'package.json'
];

console.log('📁 Checking required files:');
let allFilesExist = true;

requiredFiles.forEach(file => {
  const exists = fs.existsSync(path.join(__dirname, file));
  console.log(`   ${exists ? '✅' : '❌'} ${file}`);
  if (!exists) allFilesExist = false;
});

if (!allFilesExist) {
  console.log('\n❌ Some required files are missing!');
  process.exit(1);
}

// Check .env file
console.log('\n🔧 Environment configuration:');
const envExists = fs.existsSync(path.join(__dirname, '.env'));
console.log(`   ${envExists ? '✅' : '⚠️'} .env file ${envExists ? 'found' : 'missing (use .env.template)'}`);

// Check dependencies
console.log('\n📦 Checking dependencies:');
try {
  const packageJson = JSON.parse(fs.readFileSync(path.join(__dirname, 'package.json'), 'utf8'));
  const dependencies = Object.keys(packageJson.dependencies || {});
  
  if (dependencies.length > 0) {
    console.log(`   ✅ Found ${dependencies.length} dependencies in package.json`);
    
    // Check if node_modules exists
    const nodeModulesExists = fs.existsSync(path.join(__dirname, 'node_modules'));
    console.log(`   ${nodeModulesExists ? '✅' : '⚠️'} node_modules ${nodeModulesExists ? 'found' : 'missing (run npm install)'}`);
  }
} catch (error) {
  console.log('   ❌ Error reading package.json');
}

console.log('\n🚀 Setup verification complete!');

if (!envExists) {
  console.log('\n📝 Next steps:');
  console.log('   1. Copy .env.template to .env');
  console.log('   2. Update .env with your OpenAI API key');
  console.log('   3. Run: npm install');
  console.log('   4. Run: npm start');
}
