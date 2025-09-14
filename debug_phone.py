#!/usr/bin/env python3
import re

text = "mon numéro: 0612345678"
patterns = [
    r'0[1-9]\d{8}',
    r'\b0[1-9]\d{8}\b', 
    r'(?<!\d)0[1-9]\d{8}(?!\d)',
]

for i, pattern in enumerate(patterns):
    matches = re.findall(pattern, text)
    print(f"Pattern {i+1}: {pattern}")
    print(f"  Matches: {matches}")
    print(f"  Text: '{text}'")
    print()