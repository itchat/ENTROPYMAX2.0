"""Sanity test to verify pytest discovery and conftest fixtures work."""


def test_pytest_discovery_works():
    assert True


def test_tmp_cache_root_isolates(tmp_cache_root):
    import os
    assert os.environ["ENTROPYMAX_CACHE_DIR"] == str(tmp_cache_root)
    assert tmp_cache_root.exists()


def test_frontend_on_sys_path():
    import sys
    assert any("frontend" in p for p in sys.path)


def test_can_import_cache_paths(tmp_cache_root):
    from utils.cache_paths import resolve_cache_root
    assert resolve_cache_root() == tmp_cache_root
