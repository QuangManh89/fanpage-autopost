import os
from unittest.mock import MagicMock, patch
import pytest

from src.openrouter_service import OpenRouterService


@pytest.fixture
def mock_openrouter_success():
    """Mock successful OpenRouter chat completions response."""
    return {
        "id": "gen-12345",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": (
                        "🔥 5 MẸO TĂNG TỐC MÁY TÍNH CỰC DỄ TẠI NHÀ! 🚀\n\n"
                        "Máy tính của bạn đang chạy chậm như rùa bò? Đừng lo lắng!\n\n"
                        "💡 1. Dọn dẹp rác hệ thống thường xuyên.\n"
                        "💡 2. Tắt các ứng dụng khởi động cùng Windows.\n\n"
                        "👉 Hãy chia sẻ bài viết này nếu thấy hữu ích!\n\n"
                        "#TangTocMayTinh #ThuThuatWindows #MeoHay"
                    ),
                }
            }
        ],
        "citations": ["https://techcommunity.microsoft.com", "https://vnexpress.net/so-hoa"],
    }


def test_init_without_api_key_raises_error(monkeypatch):
    """Test that initializing without an API key raises ValueError."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        OpenRouterService()


def test_init_with_api_key_param():
    """Test initializing with an explicit API key parameter."""
    service = OpenRouterService(api_key="sk-or-v1-testkey123")
    assert service.api_key == "sk-or-v1-testkey123"
    assert "deepseek" in service.model


def test_init_with_env_var(monkeypatch):
    """Test initializing with OPENROUTER_API_KEY from environment variables."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-envkey456")
    service = OpenRouterService()
    assert service.api_key == "sk-or-v1-envkey456"


def test_verify_key_success():
    """Test verify_key when OpenRouter returns valid auth details."""
    service = OpenRouterService(api_key="sk-or-test")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "label": "My Key",
            "usage": 0.05,
            "limit": 10.0,
            "is_free_tier": True,
        }
    }

    with patch("requests.get", return_value=mock_response):
        info = service.verify_key()
        assert info["valid"] is True
        assert info["label"] == "My Key"
        assert info["is_free_tier"] is True


def test_verify_key_invalid():
    """Test verify_key when OpenRouter returns 401 unauthenticated."""
    service = OpenRouterService(api_key="sk-or-invalid")
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.json.return_value = {"error": {"message": "Invalid API key"}}

    with patch("requests.get", return_value=mock_response):
        info = service.verify_key()
        assert info["valid"] is False
        assert "Invalid" in info["error"]


def test_generate_fanpage_post_empty_topic():
    """Test that empty topic raises ValueError."""
    service = OpenRouterService(api_key="sk-or-test")
    with pytest.raises(ValueError, match="chủ đề"):
        service.generate_fanpage_post("")
    with pytest.raises(ValueError, match="chủ đề"):
        service.generate_fanpage_post("   ")


def test_generate_fanpage_post_success(mock_openrouter_success):
    """Test generating Fanpage post via OpenRouter API."""
    service = OpenRouterService(api_key="sk-or-test", model="deepseek/deepseek-chat:free")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_openrouter_success

    with patch("requests.post", return_value=mock_response) as mock_post:
        result = service.generate_fanpage_post(
            topic="Mẹo tăng tốc máy tính",
            tone="hài hước",
            include_hashtags=True,
            use_search=True,
        )

        assert "5 MẸO TĂNG TỐC" in result["content"]
        assert len(result["suggested_hashtags"]) >= 2
        assert "#TangTocMayTinh" in result["suggested_hashtags"]
        assert len(result["sources"]) == 2
        assert "https://vnexpress.net/so-hoa" in result["sources"]

        # Verify headers and payload
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        headers = kwargs.get("headers", {})
        assert "Bearer sk-or-test" in headers.get("Authorization", "")
        payload = kwargs.get("json", {})
        assert payload.get("plugins") == [{"id": "web"}]


def test_generate_fanpage_post_without_search_and_hashtags(mock_openrouter_success):
    """Test generating post without search and without hashtags."""
    service = OpenRouterService(api_key="sk-or-test")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_openrouter_success

    with patch("requests.post", return_value=mock_response) as mock_post:
        result = service.generate_fanpage_post(
            topic="Cài win dạo",
            use_search=False,
            include_hashtags=False,
        )

        assert result["content"] != ""
        assert result["sources"] == []
        assert result["suggested_hashtags"] == []
        payload = mock_post.call_args[1].get("json", {})
        assert "plugins" not in payload


def test_generate_fanpage_post_api_error():
    """Test API error handling when OpenRouter returns error status."""
    service = OpenRouterService(api_key="sk-or-test")
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.json.return_value = {
        "error": {"message": "Rate limit exceeded or provider unavailable"}
    }

    with patch("requests.post", return_value=mock_response):
        with pytest.raises(RuntimeError, match="Rate limit exceeded"):
            service.generate_fanpage_post(topic="Thủ thuật Windows")
