"""Build knowledge-base sections from PAU's Package of Practices for Crops of Punjab.

    python scripts/build_pau_kb.py            # downloads the two PDFs from pau.edu if missing

The PAU text is copyrighted, so it is not committed: this writes data/pau/kb/*.json (git-ignored),
which the app searches next to data/raw/. The app also builds it on startup when it is missing
(PAU_AUTO_BUILD). See app/rag/pau_kb.py.
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.rag.pau_kb import build_pau_kb  # noqa: E402

if __name__ == "__main__":
    build_pau_kb()
