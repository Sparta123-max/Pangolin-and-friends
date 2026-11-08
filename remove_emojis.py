#!/usr/bin/env python3
import re
import os

files = [
    r'templates\index.html',
    r'templates\about.html',
    r'templates\login.html',
    r'templates\TeTe_game\index.html',
    r'templates\scan.html',
    r'templates\camera.html',
    r'templates\camera_hunter.html',
]

# Regex pattern matching emoji/pictograph ranges
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F700-\U0001F77F"  # alchemical
    "\U0001F780-\U0001F7FF"  # geometric extended
    "\U0001F800-\U0001F8FF"  # supplemental arrows-C
    "\U0001F900-\U0001F9FF"  # supplemental symbols
    "\U0001FA00-\U0001FA6F"  # chess symbols
    "\U0001FA70-\U0001FAFF"  # symbols extended-A
    "\U00002702-\U000027B0"  # dingbats
    "\U000024C2-\U0001F251"  # enclosed chars
    "\U00002600-\U000026FF"  # misc symbols
    "\U0000FE00-\U0000FE0F"  # variation selectors (strip fe0f etc)
    "]+",
    flags=re.UNICODE
)

for filepath in files:
    if not os.path.exists(filepath):
        print(f"Skipping (not found): {filepath}")
        continue
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove emoji but preserve SVG paths and HTML structure
    # We only want to strip emojis from text content and attribute values
    cleaned = EMOJI_PATTERN.sub('', content)
    
    # Fix double-spaces in text nodes but not in CSS/code
    # Only collapse spaces that appear in text contexts (between tags)
    cleaned = re.sub(r'(>)\s{2,}', r'> ', cleaned)
    cleaned = re.sub(r'\s{2,}(<)', r' \1', cleaned)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(cleaned)
    
    print(f"Cleaned: {filepath}")

print("All done!")
