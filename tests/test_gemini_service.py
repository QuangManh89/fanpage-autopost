from unittest.mock import MagicMock, patch
import pytest

from src.gemini_service import GeminiService


@pytest.fixture
def mock_genai_client():
    mock_client = MagicMock()
    return mock_client


def test_init_without_api_key_raises_error(monkeypatch):
    """Test that initializing GeminiService without an API key raises ValueError."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        GeminiService()


def test_init_with_api_key_param():
    """Test initializing with an explicit API key parameter."""
    with patch("src.gemini_service.genai.Client") as mock_client_cls:
        service = GeminiService(api_key="test-param-api-key")
        assert service.api_key == "test-param-api-key"
        mock_client_cls.assert_called_once_with(api_key="test-param-api-key")


def test_init_with_env_var(monkeypatch):
    """Test initializing with GEMINI_API_KEY from environment variables."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-env-api-key")
    with patch("src.gemini_service.genai.Client") as mock_client_cls:
        service = GeminiService()
        assert service.api_key == "test-env-api-key"
        mock_client_cls.assert_called_once_with(api_key="test-env-api-key")


def test_generate_fanpage_post_empty_topic(mock_genai_client):
    """Test that empty or whitespace topic raises ValueError."""
    service = GeminiService(api_key="test-key", client=mock_genai_client)
    with pytest.raises(ValueError, match="Topic cannot be empty"):
        service.generate_fanpage_post("")
    with pytest.raises(ValueError, match="Topic cannot be empty"):
        service.generate_fanpage_post("   ")


def test_generate_fanpage_post_with_search_success(mock_genai_client):
    """Test successful post generation with search grounding enabled."""
    sample_content = (
        "🔥 ĐỘT PHÁ CÔNG NGHỆ AI NĂM 2026! 🚀\n\n"
        "Trí tuệ nhân tạo đang thay đổi cách chúng ta làm việc mỗi ngày.\n\n"
        "📌 Điểm nổi bật:\n"
        "• Tự động hóa nội dung đa kênh\n"
        "• Tìm kiếm thông tin tức thời theo thời gian thực\n"
        "• Tối ưu tương tác Fanpage vượt trội\n\n"
        "👉 Bạn đã ứng dụng AI vào công việc chưa? Bình luận ngay để cùng trao đổi nhé!\n\n"
        "#AI2026 #CongNghe #FanpageMarketing"
    )

    mock_response = MagicMock()
    mock_response.text = sample_content

    chunk1 = MagicMock()
    chunk1.web.uri = "https://techradar.com/ai-2026"
    chunk1.web.title = "AI in 2026"

    chunk2 = MagicMock()
    chunk2.web.uri = "https://vnexpress.net/ai-breakthrough"
    chunk2.web.title = "Đột phá AI"

    mock_candidate = MagicMock()
    mock_candidate.grounding_metadata.grounding_chunks = [chunk1, chunk2]
    mock_response.candidates = [mock_candidate]

    mock_genai_client.models.generate_content.return_value = mock_response

    service = GeminiService(api_key="test-key", client=mock_genai_client)
    result = service.generate_fanpage_post(
        topic="Xu hướng AI 2026",
        tone="chuyên nghiệp, hấp dẫn",
        include_hashtags=True,
        use_search=True,
    )

    # Verify return structure
    assert isinstance(result, dict)
    assert result["content"] == sample_content
    assert result["sources"] == [
        "https://techradar.com/ai-2026",
        "https://vnexpress.net/ai-breakthrough",
    ]
    assert result["suggested_hashtags"] == [
        "#AI2026",
        "#CongNghe",
        "#FanpageMarketing",
    ]

    # Verify client call
    assert mock_genai_client.models.generate_content.called
    call_args = mock_genai_client.models.generate_content.call_args
    assert "Xu hướng AI 2026" in call_args.kwargs["contents"]
    config = call_args.kwargs["config"]
    assert config is not None
    assert config.tools is not None
    assert len(config.tools) > 0


def test_generate_fanpage_post_without_search(mock_genai_client):
    """Test post generation when use_search=False."""
    sample_content = (
        "💡 MẸO SỐNG KHỎE MỖI NGÀY! 🌱\n\n"
        "Uống đủ 2 lít nước mỗi ngày giúp bạn tràn đầy năng lượng!\n\n"
        "👉 Thử ngay nhé!\n\n"
        "#SucKhoe #SongKhoe"
    )

    mock_response = MagicMock()
    mock_response.text = sample_content
    mock_response.candidates = [MagicMock(grounding_metadata=None)]
    mock_genai_client.models.generate_content.return_value = mock_response

    service = GeminiService(api_key="test-key", client=mock_genai_client)
    result = service.generate_fanpage_post(
        topic="Uống nước đúng cách",
        use_search=False,
        include_hashtags=True,
    )

    assert result["content"] == sample_content
    assert result["sources"] == []
    assert result["suggested_hashtags"] == ["#SucKhoe", "#SongKhoe"]

    # Check config tools when search is disabled
    call_args = mock_genai_client.models.generate_content.call_args
    config = call_args.kwargs.get("config")
    if config:
        assert config.tools is None or len(config.tools) == 0


def test_generate_fanpage_post_without_hashtags(mock_genai_client):
    """Test post generation when include_hashtags=False."""
    sample_content = (
        "🌟 CHÀO NGÀY MỚI ĐẦY NĂNG LƯỢNG! ☀️\n\n"
        "Chúc mọi người một ngày làm việc hiệu quả và nhiều niềm vui!\n\n"
        "👉 Hãy mỉm cười thật tươi nhé!"
    )

    mock_response = MagicMock()
    mock_response.text = sample_content
    mock_response.candidates = []
    mock_genai_client.models.generate_content.return_value = mock_response

    service = GeminiService(api_key="test-key", client=mock_genai_client)
    result = service.generate_fanpage_post(
        topic="Chào buổi sáng",
        include_hashtags=False,
        use_search=False,
    )

    assert result["content"] == sample_content
    assert result["suggested_hashtags"] == []
    assert result["sources"] == []


def test_generate_fanpage_post_custom_tone(mock_genai_client):
    """Test custom tone is included in prompt."""
    mock_response = MagicMock()
    mock_response.text = "Nội dung bài viết"
    mock_response.candidates = []
    mock_genai_client.models.generate_content.return_value = mock_response

    service = GeminiService(api_key="test-key", client=mock_genai_client)
    service.generate_fanpage_post(
        topic="Công nghệ mới",
        tone="hài hước, dí dỏm, gen Z",
    )

    call_args = mock_genai_client.models.generate_content.call_args
    prompt = call_args.kwargs["contents"]
    assert "hài hước, dí dỏm, gen Z" in prompt


def test_generate_fanpage_post_handles_missing_grounding_chunks(mock_genai_client):
    """Test that missing or None grounding_chunks does not raise exceptions."""
    mock_response = MagicMock()
    mock_response.text = "Nội dung không có nguồn web"
    mock_candidate = MagicMock()
    mock_candidate.grounding_metadata = MagicMock()
    mock_candidate.grounding_metadata.grounding_chunks = None
    mock_response.candidates = [mock_candidate]
    mock_genai_client.models.generate_content.return_value = mock_response

    service = GeminiService(api_key="test-key", client=mock_genai_client)
    result = service.generate_fanpage_post("Chủ đề bất kỳ", use_search=True)

    assert result["sources"] == []
    assert result["content"] == "Nội dung không có nguồn web"


def test_generate_fanpage_post_deduplicates_sources(mock_genai_client):
    """Test that duplicate web sources in grounding chunks are deduplicated."""
    mock_response = MagicMock()
    mock_response.text = "Nội dung bài viết #AI"
    chunk1 = MagicMock()
    chunk1.web.uri = "https://example.com/duplicate"
    chunk2 = MagicMock()
    chunk2.web.uri = "https://example.com/unique"
    chunk3 = MagicMock()
    chunk3.web.uri = "https://example.com/duplicate"

    mock_candidate = MagicMock()
    mock_candidate.grounding_metadata.grounding_chunks = [chunk1, chunk2, chunk3]
    mock_response.candidates = [mock_candidate]
    mock_genai_client.models.generate_content.return_value = mock_response

    service = GeminiService(api_key="test-key", client=mock_genai_client)
    result = service.generate_fanpage_post("Chủ đề trùng nguồn", use_search=True)

    assert result["sources"] == [
        "https://example.com/duplicate",
        "https://example.com/unique",
    ]



def test_rewrite_content_empty_raises(mock_genai_client):
    """Test that rewrite_content raises ValueError on empty content."""
    service = GeminiService(api_key="test-key", client=mock_genai_client)
    with pytest.raises(ValueError, match="không được để trống"):
        service.rewrite_content("")
    with pytest.raises(ValueError, match="không được để trống"):
        service.rewrite_content("   ")


def test_rewrite_content_success(mock_genai_client):
    """Test successful content rewriting with Gemini across styles."""
    mock_response = MagicMock()
    mock_response.text = "Bản viết lại cực kỳ tự nhiên như người thật."
    mock_genai_client.models.generate_content.return_value = mock_response

    service = GeminiService(api_key="test-key", client=mock_genai_client)
    rewritten = service.rewrite_content("Văn bản ban đầu có phần máy móc.", style_key="human_editor")

    assert rewritten == "Bản viết lại cực kỳ tự nhiên như người thật."
    mock_genai_client.models.generate_content.assert_called_once()
    call_args = mock_genai_client.models.generate_content.call_args
    assert "Hãy đóng vai một biên tập viên con người" in call_args.kwargs["contents"]


def test_generate_fanpage_post_with_target_hashtags(mock_genai_client):
    """Test that target_hashtags and target_page_name are included in Gemini prompt."""
    mock_response = MagicMock()
    mock_response.text = "Nội dung bài viết cho Conic #q8 #Conic"
    mock_candidate = MagicMock()
    mock_candidate.grounding_metadata = None
    mock_response.candidates = [mock_candidate]
    mock_genai_client.models.generate_content.return_value = mock_response

    service = GeminiService(api_key="test-key", client=mock_genai_client)
    result = service.generate_fanpage_post(
        topic="Sửa bản lề laptop",
        target_page_name="Sửa Laptop Conic",
        target_hashtags="#q8 #q4 #q6 #BinhChanh #Conic",
    )

    assert result["content"] == "Nội dung bài viết cho Conic #q8 #Conic"
    call_args = mock_genai_client.models.generate_content.call_args
    prompt = call_args.kwargs["contents"]
    assert "Sửa Laptop Conic" in prompt
    assert "#q8 #q4 #q6 #BinhChanh #Conic" in prompt
