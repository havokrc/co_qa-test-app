"""Base HTTP client shared by all service clients."""
import requests


class HttpBaseClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def get(self, path: str, **params) -> requests.Response:
        return self.session.get(self._url(path), params=params or None)

    def post(self, path: str, payload: dict) -> requests.Response:
        return self.session.post(self._url(path), json=payload)

    def put(self, path: str, payload: dict) -> requests.Response:
        return self.session.put(self._url(path), json=payload)

    def delete(self, path: str) -> requests.Response:
        return self.session.delete(self._url(path))

    def health(self) -> requests.Response:
        return self.get("/health")

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"