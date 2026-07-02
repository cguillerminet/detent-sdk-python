import os

import pytest

from detent import Detent

URL = os.environ.get("DETENT_TEST_URL")
KEY = os.environ.get("DETENT_TEST_KEY")

pytestmark = pytest.mark.skipif(
    not (URL and KEY), reason="set DETENT_TEST_URL and DETENT_TEST_KEY to run live"
)


def test_limit_against_live_api():
    with Detent(api_key=KEY, base_url=URL, timeout=3.0) as rg:  # type: ignore[arg-type]
        r = rg.limit(
            namespace="sdk-it", key="k1", algorithm="fixed_window", limit=5, window_ms=10_000
        )
        assert isinstance(r.allowed, bool)
        assert r.degraded is False
