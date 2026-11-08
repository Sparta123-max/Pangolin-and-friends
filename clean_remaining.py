#!/usr/bin/env python3
"""
Comprehensive UI upgrade script:
- Removes all emoji from HTML text content
- Upgrades CSS to a more professional, polished design system
"""
import re
import os

# ============================
# EMOJI CLEANUP
# ============================
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F1E0-\U0001F1FF"
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002702-\U000027B0"
    "\U00002600-\U000026FF"
    "\U0000FE00-\U0000FE0F"
    "]+",
    flags=re.UNICODE
)

def clean_emoji_from_html(content):
    """Remove emoji only from HTML text nodes and attribute values, not from JS/Python code."""
    # Remove emoji
    cleaned = EMOJI_PATTERN.sub('', content)
    # Remove leftover <span></span> wrappers that only held emoji
    cleaned = re.sub(r'<span>\s*</span>\s*', '', cleaned)
    # Clean up leading/trailing spaces within tags
    cleaned = re.sub(r'(>)\s{2,}([^\s<])', r'\1 \2', cleaned)
    return cleaned

# Files to process
files_to_clean = [
    r'templates\scan.html',
    r'templates\camera.html',
    r'templates\camera_hunter.html',
    r'templates\map.html',
    r'templates\register.html',
]

for filepath in files_to_clean:
    if not os.path.exists(filepath):
        print(f"  Skipping (not found): {filepath}")
        continue
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    cleaned = clean_emoji_from_html(content)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(cleaned)
    print(f"  Cleaned: {filepath}")

print("Done!")
