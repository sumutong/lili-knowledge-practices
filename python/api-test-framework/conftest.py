# conftest.py — pytest 全局配置与 fixtures
"""
API 测试框架 — 全局配置
依赖: pip install pytest requests jsonschema pyyaml allure-pytest
"""
import json
import os
from pathlib import Path

import pytest
import requests
import yaml


class Config:
    BASE_URL = os.getenv("API_BASE_URL", "https://jsonplaceholder.typicode.com")
    TIMEOUT = int(os.getenv("API_TIMEOUT", "10"))
    HEADERS = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    AUTH_TOKEN = os.getenv("API_TOKEN", "")


@pytest.fixture(scope="session")
def base_url():
    return Config.BASE_URL


@pytest.fixture(scope="session")
def session():
    sess = requests.Session()
    sess.headers.update(Config.HEADERS)
    if Config.AUTH_TOKEN:
        sess.headers["Authorization"] = f"Bearer {Config.AUTH_TOKEN}"
    yield sess
    sess.close()


@pytest.fixture
def api(session, base_url):
    class APIClient:
        @staticmethod
        def get(path: str, **kwargs):
            kwargs.setdefault("timeout", Config.TIMEOUT)
            return session.get(f"{base_url}{path}", **kwargs)

        @staticmethod
        def post(path: str, **kwargs):
            kwargs.setdefault("timeout", Config.TIMEOUT)
            return session.post(f"{base_url}{path}", **kwargs)

        @staticmethod
        def put(path: str, **kwargs):
            kwargs.setdefault("timeout", Config.TIMEOUT)
            return session.put(f"{base_url}{path}", **kwargs)

        @staticmethod
        def delete(path: str, **kwargs):
            kwargs.setdefault("timeout", Config.TIMEOUT)
            return session.delete(f"{base_url}{path}", **kwargs)

    return APIClient


def load_test_data(filename: str) -> list[dict]:
    path = Path(__file__).parent / "test_data" / filename
    if path.suffix in (".yaml", ".yml"):
        with open(path) as f:
            return yaml.safe_load(f)
    elif path.suffix == ".json":
        with open(path) as f:
            return json.load(f)
    raise ValueError(f"Unsupported format: {path.suffix}")


def pytest_generate_tests(metafunc):
    if "test_case" in metafunc.fixturenames:
        func_name = metafunc.function.__name__
        data_file = f"{func_name}.yaml"
        data_path = Path(__file__).parent / "test_data" / data_file
        if data_path.exists():
            cases = load_test_data(data_file)
            ids = [c.get("id", f"case_{i}") for i, c in enumerate(cases)]
            metafunc.parametrize("test_case", cases, ids=ids)


@pytest.fixture
def validate_schema():
    from jsonschema import validate, ValidationError

    def _validate(instance: dict, schema: dict):
        try:
            validate(instance=instance, schema=schema)
        except ValidationError as e:
            pytest.fail(f"Schema validation failed: {e.message}")

    return _validate
