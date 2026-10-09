"""
WebP Optima Pro - Slug Generator
Converts title strings and filenames into web-safe SEO slugs.
Handles unicode characters, French accents, ligatures (e.g., Œ -> oe), symbol expansion (& -> and), etc.
"""
import re
import unicodedata


# Dictionary for specific character/symbol expansions prior to normalization
SYMBOL_REPLACEMENTS = {
    "&": " and ",
    "@": " at ",
    "%": " percent ",
    "+": " plus ",
    "€": " euro ",
    "$": " dollar ",
    "£": " pound ",
    "Œ": "oe",
    "œ": "oe",
    "Æ": "ae",
    "æ": "ae",
    "ß": "ss",
    "Ø": "o",
    "ø": "o",
}


def generate_slug(text: str) -> str:
    """
    Transforms text into a clean web-safe slug.
    Example: "CONSTRUCTION & GROS ŒUVRE" -> "construction-and-gros-oeuvre"
    """
    if not text:
        return "image"

    # Strip common image extensions if user pasted a filename (e.g. photo.jpg -> photo)
    text = re.sub(r"\.(webp|png|jpe?g|gif|bmp|tiff|svg)$", "", text.strip(), flags=re.IGNORECASE)

    # Step 1: Replace explicit symbols and ligatures
    for symbol, replacement in SYMBOL_REPLACEMENTS.items():
        text = text.replace(symbol, replacement)

    # Step 2: Normalize unicode (NFKD) to separate base letters from accents
    normalized = unicodedata.normalize("NFKD", text)
    
    # Step 3: Remove diacritics / accent marks
    ascii_text = "".join(c for c in normalized if not unicodedata.combining(c))

    # Step 4: Convert to lowercase
    ascii_text = ascii_text.lower()

    # Step 5: Replace any non-alphanumeric character with a hyphen
    cleaned = re.sub(r"[^a-z0-9]+", "-", ascii_text)

    # Step 6: Collapse consecutive hyphens and trim leading/trailing hyphens
    slug = re.sub(r"-+", "-", cleaned).strip("-")

    return slug if slug else "image"


if __name__ == "__main__":
    # Quick test cases
    test_cases = [
        "CONSTRUCTION & GROS ŒUVRE",
        "Café & Gâteau ! 100%",
        "Résume & Profile — 2026",
        "  über  großes   Haus   ",
    ]
    for test in test_cases:
        print(f"'{test}' -> '{generate_slug(test)}'")
