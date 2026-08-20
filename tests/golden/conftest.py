"""Put ``.env`` in the environment before any test module imports `prope`.

**Why a conftest and not a line in the test.** `prope.app_agent.client` reads its
provider settings into module-level constants at import time:

    APP_OPENAI_API_KEY = os.environ.get("APP_OPENAI_API_KEY", "")

so anything that imports it before the environment is populated binds the empty
default permanently, and every adjudication answers `LMServerError`. The live
lane would then report a model that disagrees with the labels when what actually
happened is an unset variable — the most expensive kind of wrong measurement,
because it looks like a finding.

pytest imports a directory's `conftest.py` before the test modules beside it, so
this is the last point where the ordering can still be fixed. `run_eval.py`
solves the same problem the same way and its loader is reused here rather than
copied.

Harmless for the free lane, which calls nothing.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from eval.retrieval.run_eval import load_dotenv  # noqa: E402

load_dotenv()
