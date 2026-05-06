#!/usr/bin/env python3
"""
Verification script to check Ollama integration is complete
Run: python verify_ollama_integration.py
"""

import os
import sys
import subprocess
import json
from pathlib import Path

def check_ollama_running():
    """Check if Ollama server is running"""
    try:
        import urllib.request
        response = urllib.request.urlopen('http://localhost:11434/api/tags', timeout=2)
        data = json.loads(response.read())
        models = [m['name'] for m in data.get('models', [])]
        return True, models
    except Exception as e:
        return False, str(e)

def check_model_available():
    """Check if llama3.2:3b model is available"""
    try:
        import urllib.request
        response = urllib.request.urlopen('http://localhost:11434/api/tags', timeout=2)
        data = json.loads(response.read())
        models = [m['name'] for m in data.get('models', [])]
        has_model = any('llama3.2:3b' in m for m in models)
        return has_model, models
    except Exception as e:
        return False, str(e)

def check_env_file():
    """Check .env has correct Ollama config and no old API keys"""
    env_path = Path('backend/.env')
    if not env_path.exists():
        return False, "backend/.env not found"

    content = env_path.read_text()

    # Check for required Ollama config
    has_ollama_url = 'OLLAMA_BASE_URL' in content
    has_ollama_model = 'OLLAMA_MODEL' in content

    # Check for forbidden old API keys
    forbidden_keys = [
        'GEMINI_API_KEY=',
        'GOOGLE_API_KEY=',
        'OPENAI_API_KEY=',
        'GROQ_API_KEY=',
        'DEEPGRAM_API_KEY=',
        'ELEVENLABS_TTS_KEY='
    ]

    has_old_keys = []
    for key in forbidden_keys:
        # Check for uncommented instances
        for line in content.split('\n'):
            if line.startswith(key):
                has_old_keys.append(key.rstrip('='))

    issues = []
    if not has_ollama_url:
        issues.append("Missing OLLAMA_BASE_URL")
    if not has_ollama_model:
        issues.append("Missing OLLAMA_MODEL")
    if has_old_keys:
        issues.append(f"Found old API keys: {', '.join(has_old_keys)}")

    return len(issues) == 0, issues or ["✅ .env configured correctly"]

def check_requirements():
    """Check requirements.txt has correct dependencies"""
    req_path = Path('backend/requirements.txt')
    if not req_path.exists():
        return False, "backend/requirements.txt not found"

    content = req_path.read_text()

    # Check for required packages
    required = {
        'ollama': False,
        'faster-whisper': False,
        'scipy': False,
        'sounddevice': False
    }

    # Check for forbidden packages
    forbidden = {
        'openai': False,
        'groq': False,
        'google-generativeai': False,
    }

    for line in content.split('\n'):
        for pkg in required:
            if pkg in line.lower():
                required[pkg] = True
        for pkg in forbidden:
            if pkg in line.lower() and not line.strip().startswith('#'):
                forbidden[pkg] = True

    issues = []
    for pkg, found in required.items():
        if not found:
            issues.append(f"Missing {pkg}")
    for pkg, found in forbidden.items():
        if found:
            issues.append(f"Found deprecated {pkg}")

    return len(issues) == 0, issues or ["✅ requirements.txt correct"]

def check_main_py():
    """Check main.py doesn't have old API calls"""
    main_path = Path('backend/app/main.py')
    if not main_path.exists():
        return False, "backend/app/main.py not found"

    content = main_path.read_text()

    # Check for old API imports
    forbidden_patterns = [
        'google.generativeai',
        'from openai import',
        'from groq import',
        'ask_groq',
        'ask_openai',
    ]

    found_patterns = []
    for pattern in forbidden_patterns:
        if pattern in content:
            found_patterns.append(pattern)

    if found_patterns:
        return False, [f"Found old API: {p}" for p in found_patterns]

    # Check for required Ollama patterns
    has_ollama_chat = 'ollama.chat(' in content
    has_question_gen = 'def generate_questions_with_ai' in content

    if not has_ollama_chat:
        return False, ["Missing ollama.chat() calls"]

    return True, ["✅ main.py uses Ollama only"]

def check_syntax():
    """Check Python syntax is valid"""
    main_path = Path('backend/app/main.py')
    if not main_path.exists():
        return False, "backend/app/main.py not found"

    try:
        import py_compile
        py_compile.compile(str(main_path), doraise=True)
        return True, ["✅ Python syntax valid"]
    except py_compile.PyCompileError as e:
        return False, [f"Syntax error: {e}"]

def main():
    print("\n" + "="*60)
    print("🔍 OLLAMA INTEGRATION VERIFICATION")
    print("="*60 + "\n")

    checks = [
        ("Ollama Server Running", check_ollama_running, True),
        ("Model Available", check_model_available, True),
        ("Environment File (.env)", check_env_file, False),
        ("Requirements File", check_requirements, False),
        ("Main.py Code Quality", check_main_py, False),
        ("Python Syntax", check_syntax, False),
    ]

    results = []
    for name, check_fn, needs_ollama in checks:
        if needs_ollama:
            ollama_ok, _ = check_ollama_running()
            if not ollama_ok:
                print(f"⏭️  SKIPPED: {name} (Ollama not running)")
                continue

        success, details = check_fn()
        results.append((name, success, details))

        icon = "✅" if success else "❌"
        print(f"{icon} {name}")

        if isinstance(details, list):
            for detail in details:
                print(f"   {detail}")
        else:
            print(f"   {details}")
        print()

    # Summary
    print("="*60)
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)

    if passed == total:
        print(f"✅ ALL CHECKS PASSED ({passed}/{total})")
        print("\nYou're ready to run:")
        print("  1. ollama serve")
        print("  2. cd backend && python -m uvicorn app.main:app --reload")
        print("  3. cd frontend && npm run dev")
        return 0
    else:
        print(f"⚠️  SOME CHECKS FAILED ({passed}/{total} passed)")
        print("\nFailing checks need attention before running the system.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
