#!/usr/bin/env python3
from phone_number_detector import PhoneNumberDetector
import logging

# Activer debug pour voir les détails
logging.basicConfig(level=logging.DEBUG)

detector = PhoneNumberDetector()

# Test case spécifique qui ne fonctionne pas
text = "mon numéro: 0612345678"
print(f"Test: '{text}'")

# Tester chaque pattern individuellement  
for i, pattern in enumerate(detector.compiled_patterns):
    matches = pattern.finditer(text)
    for match in matches:
        number = match.group()
        start, end = match.span()
        print(f"Pattern {i}: Trouvé '{number}' pos {start}-{end}")
        
        # Tester si c'est une exception
        is_exception = detector._is_exception(number, text, start, end)
        print(f"  Exception: {is_exception}")

# Test final
result = detector.detect_phone_numbers(text)
print(f"Résultat final: {result}")