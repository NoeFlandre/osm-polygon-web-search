import sys
from pathlib import Path

_repository_root = Path(__file__).resolve().parent.parent
if not (_repository_root / "scripts").is_dir():
    _repository_root = _repository_root.parent
sys.path.insert(0, str(_repository_root))
