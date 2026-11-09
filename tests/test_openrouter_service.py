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


def test_get_available_models():
    """Test retrieving available models list from OpenRouter."""
    service = OpenRouterService(api_key="sk-or-test")
    mock_data = {
        "data": [
            {
                "id": "deepseek/deepseek-chat:free",
                "name": "DeepSeek: DeepSeek V3 (free)",
                "context_length": 64000,
                "pricing": {"prompt": "0", "completion": "0"},
            },
            {
                "id": "anthropic/claude-3.5-sonnet",
                "name": "Anthropic: Claude 3.5 Sonnet",
                "context_length": 200000,
                "pricing": {"prompt": "0.000003", "completion": "0.000015"},
            },
            {
                "id": "meta-llama/llama-3.3-70b-instruct:free",
                "name": "Meta: Llama 3.3 70B (free)",
                "context_length": 131072,
                "pricing": {"prompt": "0", "completion": "0"},
            },
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_data

    with patch("requests.get", return_value=mock_resp):
        all_models = service.get_available_models(only_free=False)
        assert len(all_models) == 3

        free_models = service.get_available_models(only_free=True)
        assert len(free_models) == 2
        assert all(m["is_free"] for m in free_models)
        assert any("deepseek" in m["id"] for m in free_models)


def test_test_model_connection_success():
    """Test pinging an OpenRouter model successfully."""
    service = OpenRouterService(api_key="sk-or-test")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "pong"}}]
    }

    with patch("requests.post", return_value=mock_resp):
        res = service.test_model_connection("deepseek/deepseek-chat:free")
        assert res["success"] is True
        assert res["model"] == "deepseek/deepseek-chat:free"
        assert res["latency_ms"] >= 0
        assert "pong" in res["message"]


def test_test_model_connection_failure():
    """Test pinging an OpenRouter model when model fails or is rate limited."""
    service = OpenRouterService(api_key="sk-or-test")
    mock_resp = MagicMock()
    mock_resp.status_code = 503
    mock_resp.json.return_value = {
        "error": {"message": "Model is temporarily overloaded"}
    }

    with patch("requests.post", return_value=mock_resp):
        res = service.test_model_connection("deepseek/deepseek-r1:free")
        assert res["success"] is False
        assert "overloaded" in res["message"]


def test_test_model_connection_null_content_does_not_crash():
    """Test that null content (e.g. reasoning models) falls back cleanly without AttributeError."""
    service = OpenRouterService(api_key="sk-or-test")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": None, "reasoning": "Thinking about ping..."}}]
    }

    with patch("requests.post", return_value=mock_resp):
        res = service.test_model_connection("deepseek/deepseek-r1:free")
        assert res["success"] is True
        assert "Thinking" in res["message"]


def test_generate_fanpage_post_null_content_reasoning_fallback():
    """Test that post generation gracefully uses reasoning if content is null."""
    service = OpenRouterService(api_key="sk-or-test")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "reasoning": "🔥 BẬT MÍ CÁCH BẢO VỆ MÁY TÍNH #TechTips",
                }
            }
        ]
    }

    with patch("requests.post", return_value=mock_resp):
        res = service.generate_fanpage_post(topic="Bảo vệ máy tính", use_search=False)
        assert "BẬT MÍ CÁCH" in res["content"]
        assert "#TechTips" in res["suggested_hashtags"]



def test_rewrite_content_empty_raises():
    """Test that rewrite_content raises ValueError on empty content."""
    service = OpenRouterService(api_key="sk-or-test")
    with pytest.raises(ValueError, match="không được để trống"):
        service.rewrite_content("")
    with pytest.raises(ValueError, match="không được để trống"):
        service.rewrite_content("   ")


def test_rewrite_content_success():
    """Test successful content rewriting with OpenRouter."""
    service = OpenRouterService(api_key="sk-or-test")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Bản viết lại cực kỳ tự nhiên không máy móc.",
                }
            }
        ]
    }

    with patch("requests.post", return_value=mock_resp) as mock_post:
        rewritten = service.rewrite_content("Nội dung ban đầu.", style_key="natural_rhythm")
        assert rewritten == "Bản viết lại cực kỳ tự nhiên không máy móc."
        assert mock_post.called
        payload = mock_post.call_args[1]["json"]
        user_msg = payload["messages"][1]["content"]
        assert "Viết lại văn bản này theo cách phản ánh cách con người thực sự suy nghĩ" in user_msg


def test_openrouter_post_with_target_hashtags():
    """Test that target_hashtags and target_page_name are included in OpenRouter prompt."""
    service = OpenRouterService(api_key="sk-or-test")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Sửa máy tính tại BMT chuyên nghiệp #Bmt #BuonMaThuot",
                }
            }
        ]
    }

    with patch("requests.post", return_value=mock_resp) as mock_post:
        res = service.generate_fanpage_post(
            topic="Cài đặt Windows tại nhà",
            target_page_name="Sửa Máy Tính Tại Nhà BMT",
            target_hashtags="#Bmt #BuonMaThuot #PhuongTanLap",
        )
        assert "#Bmt" in res["content"]
        assert mock_post.called
        payload = mock_post.call_args[1]["json"]
        user_msg = payload["messages"][0]["content"]
        assert "Sửa Máy Tính Tại Nhà BMT" in user_msg
        assert "#Bmt #BuonMaThuot #PhuongTanLap" in user_msg
