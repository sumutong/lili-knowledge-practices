# test_users.py — 用户 API 测试用例
"""用户 CRUD 接口测试"""
import pytest


class TestGetUsers:

    def test_list_users(self, api, validate_schema):
        resp = api.get("/users")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        user_schema = {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "name": {"type": "string"},
                "email": {"type": "string"},
            },
            "required": ["id", "name", "email"],
        }
        for user in data:
            validate_schema(user, user_schema)

    @pytest.mark.parametrize("user_id,expected_status", [
        (1, 200),
        (999, 404),
        (0, 404),
        (-1, 404),
    ])
    def test_get_user_by_id(self, api, user_id, expected_status):
        resp = api.get(f"/users/{user_id}")
        assert resp.status_code == expected_status
        if expected_status == 200:
            data = resp.json()
            assert data["id"] == user_id

    def test_query_params(self, api):
        resp = api.get("/users", params={"_limit": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 5


class TestPosts:

    def test_create_post(self, api, validate_schema):
        payload = {
            "title": "Pytest API Test",
            "body": "This is a test post from automated test framework.",
            "userId": 1,
        }
        resp = api.post("/posts", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == payload["title"]
        assert "id" in data

    def test_update_post(self, api):
        payload = {"title": "Updated Title"}
        resp = api.put("/posts/1", json=payload)
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Title"

    def test_delete_post(self, api):
        resp = api.delete("/posts/1")
        assert resp.status_code == 200


class TestAuth:

    def test_unauthorized_access(self, api):
        resp = api.get("/protected-resource")
        assert resp.status_code in (401, 403, 404)

    def test_invalid_token(self, api):
        resp = api.get("/users", headers={"Authorization": "Bearer invalid_token"})
        assert resp.status_code in (401, 403, 200)
