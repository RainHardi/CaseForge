import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["CASEFORGE_LLM_MODE"] = "offline"  # tests never call a paid/rate-limited API

from caseforge.cli import load_input  # noqa: E402
from caseforge.models import ImageRef  # noqa: E402
from caseforge.store import Store  # noqa: E402

SAMPLES = ROOT / "samples"
SAMPLE_FILES = [
    SAMPLES / "01_clean_form" / "input.json",
    SAMPLES / "02_rough_notes" / "notes.txt",
    SAMPLES / "03_pasted_chat" / "chat.txt",
]


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "projects")


@pytest.fixture
def make_record(store):
    def _make(path: Path):
        inp = load_input(path)
        images = inp.images
        inp.images = []
        rec = store.create(inp)
        for img in images:
            src = path.parent / img.filename
            if src.exists():
                name = store.add_image(rec.id, src=src)
                rec.input.images.append(ImageRef(filename=name, caption=img.caption, section=img.section))
        return rec

    return _make
