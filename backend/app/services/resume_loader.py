from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
RESUME_PATH = BACKEND_ROOT / 'data' / 'public_resume.md'

def load_resume(path: Path = RESUME_PATH) -> str | None:
    # Bounded read also protects against a file growing between stat and read.
    try:
        with path.open('rb') as f:
            data = f.read(65537)
        if len(data) > 65536: return None
        text = data.decode('utf-8').strip()
        return text if 100 <= len(text) <= 12000 else None
    except (OSError, UnicodeError):
        return None
