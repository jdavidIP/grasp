import uuid

from httpx import ASGITransport, AsyncClient

from app.main import app

BASE_URL = "http://test"


async def test_video_lifecycle():
    url = f"https://www.youtube.com/watch?v=test-{uuid.uuid4().hex[:8]}"
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        create_response = await client.post("/api/videos", json={"url": url})
        assert create_response.status_code == 201
        video = create_response.json()
        assert video["status"] == "pending"

        duplicate_response = await client.post("/api/videos", json={"url": url})
        assert duplicate_response.status_code == 409

        list_response = await client.get("/api/videos")
        assert any(v["id"] == video["id"] for v in list_response.json())

        get_response = await client.get(f"/api/videos/{video['id']}")
        assert get_response.status_code == 200
        assert get_response.json()["status"] == "ready"

        delete_response = await client.delete(f"/api/videos/{video['id']}")
        assert delete_response.status_code == 204

        list_after_delete = await client.get("/api/videos")
        assert all(v["id"] != video["id"] for v in list_after_delete.json())


async def test_create_video_invalid_url():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.post("/api/videos", json={"url": "https://example.com/not-youtube"})
    assert response.status_code == 400
