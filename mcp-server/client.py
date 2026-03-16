"""Shared HTTP client for proxying requests to the FastAPI backend."""
import os
import httpx

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


async def get(path: str, **params) -> dict:
    """GET request, dropping None params."""
    clean = {k: v for k, v in params.items() if v is not None}
    async with httpx.AsyncClient(timeout=30) as http:
        r = await http.get(f"{API_BASE_URL}{path}", params=clean)
        r.raise_for_status()
        return r.json()


async def post(path: str, body: dict) -> dict:
    """POST request with JSON body."""
    async with httpx.AsyncClient(timeout=30) as http:
        r = await http.post(f"{API_BASE_URL}{path}", json=body)
        r.raise_for_status()
        return r.json()


async def patch(path: str, body: dict) -> dict:
    """PATCH request with JSON body."""
    async with httpx.AsyncClient(timeout=30) as http:
        r = await http.patch(f"{API_BASE_URL}{path}", json=body)
        r.raise_for_status()
        return r.json()


async def delete(path: str, **params) -> dict:
    """DELETE request."""
    clean = {k: v for k, v in params.items() if v is not None}
    async with httpx.AsyncClient(timeout=30) as http:
        r = await http.delete(f"{API_BASE_URL}{path}", params=clean)
        r.raise_for_status()
        return r.json()
