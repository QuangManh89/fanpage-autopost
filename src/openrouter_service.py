import os
import re
from typing import Any
import requests
from src.gemini_service import REWRITE_STYLES


class OpenRouterService:
    """Service for generating Facebook Fanpage posts using OpenRouter API."""

    BASE_URL = "https://openrouter.ai/api/v1"

    DEFAULT_FREE_MODELS = [
        "deepseek/deepseek-chat:free",
        "deepseek/deepseek-r1:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "qwen/qwen-2.5-72b-instruct:free",
        "google/gemini-2.0-flash-exp:free",
    ]

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "deepseek/deepseek-chat:free",
    ) -> None:
        """Initialize OpenRouterService.

        Args:
            api_key: OpenRouter API key. Defaults to OPENROUTER_API_KEY environment variable.
            model: OpenRouter model identifier (defaults to free DeepSeek V3).

        Raises:
            ValueError: If api_key is missing or empty.
        """
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key or not self.api_key.strip():
            raise ValueError(
                "OPENROUTER_API_KEY is required. Please provide it in constructor or set OPENROUTER_API_KEY environment variable."
            )
        self.api_key = self.api_key.strip()
        self.model = model or "deepseek/deepseek-chat:free"

    def _get_headers(self) -> dict[str, str]:
        """Return standardized authorization and app headers for OpenRouter."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "http://localhost:8501",
            "X-Title": "Facebook Fanpage Auto-Poster",
            "Content-Type": "application/json",
        }

    def verify_key(self) -> dict[str, Any]:
        """Verify the OpenRouter API key against auth endpoint.

        Returns:
            dict containing:
                - valid (bool): True if key is valid.
                - label (str): Key label/name.
                - usage (float): Current credits used.
                - limit (float | None): Credit limit if any.
                - is_free_tier (bool): Whether the key is on free tier.
                - error (str | None): Error message if invalid.
        """
        url = f"{self.BASE_URL}/auth/key"
        try:
            res = requests.get(url, headers=self._get_headers(), timeout=15)
            data = res.json()
            if res.status_code == 200 and "data" in data:
                key_data = data["data"]
                return {
                    "valid": True,
                    "label": key_data.get("label", "Default Key"),
                    "usage": key_data.get("usage", 0.0),
                    "limit": key_data.get("limit"),
                    "is_free_tier": key_data.get("is_free_tier", True),
                    "error": None,
                }
            error_msg = data.get("error", {}).get("message", f"HTTP {res.status_code}")
            return {
                "valid": False,
                "label": "",
                "usage": 0.0,
                "limit": None,
                "is_free_tier": False,
                "error": error_msg,
            }
        except Exception as e:
            return {
                "valid": False,
                "label": "",
                "usage": 0.0,
                "limit": None,
                "is_free_tier": False,
                "error": str(e),
            }

    def get_available_models(self, only_free: bool = False) -> list[dict[str, Any]]:
        """Fetch models available on OpenRouter with metadata.

        Args:
            only_free: If True, only returns models that are 100% free (:free tag or zero cost).

        Returns:
            list of dicts containing id, name, context_length, pricing, is_free.
        """
        url = f"{self.BASE_URL}/models"
        try:
            res = requests.get(url, headers=self._get_headers(), timeout=15)
            if res.status_code != 200:
                return []
            data = res.json()
            raw_models = data.get("data", [])
            results = []
            for m in raw_models:
                m_id = m.get("id", "")
                pricing = m.get("pricing", {}) or {}
                try:
                    prompt_cost = float(pricing.get("prompt", 1.0) or 0.0)
                    completion_cost = float(pricing.get("completion", 1.0) or 0.0)
                except (ValueError, TypeError):
                    prompt_cost = 1.0
                    completion_cost = 1.0
                is_free = ":free" in m_id or (prompt_cost == 0 and completion_cost == 0)

                if only_free and not is_free:
                    continue

                results.append({
                    "id": m_id,
                    "name": m.get("name", m_id),
                    "context_length": m.get("context_length", 0),
                    "pricing": pricing,
                    "is_free": is_free,
                })
            return results
        except Exception:
            return []

    def test_model_connection(self, model_id: str) -> dict[str, Any]:
        """Send a lightweight ping to a specific OpenRouter model to test connectivity.

        Args:
            model_id: The OpenRouter model ID to check.

        Returns:
            dict containing:
                - success (bool): True if model responded.
                - model (str): Tested model ID.
                - latency_ms (int): Response time in milliseconds.
                - message (str): Response text or error explanation.
        """
        import time

        url = f"{self.BASE_URL}/chat/completions"
        payload = {
            "model": model_id,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 15,
        }
        start = time.perf_counter()
        try:
            res = requests.post(url, headers=self._get_headers(), json=payload, timeout=20)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            data = res.json()
            if res.status_code == 200:
                choices = data.get("choices", [])
                reply = "OK"
                if choices:
                    msg = choices[0].get("message", {}) or {}
                    raw_content = msg.get("content")
                    if not raw_content:
                        raw_content = msg.get("reasoning") or msg.get("reasoning_content") or ""
                    reply = str(raw_content).strip() if raw_content else "OK"
                return {
                    "success": True,
                    "model": model_id,
                    "latency_ms": elapsed_ms,
                    "message": reply or "Kết nối thành công (200 OK)",
                }
            err_msg = data.get("error", {}).get("message", f"HTTP {res.status_code}")
            return {
                "success": False,
                "model": model_id,
                "latency_ms": elapsed_ms,
                "message": err_msg,
            }
        except Exception as e:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return {
                "success": False,
                "model": model_id,
                "latency_ms": elapsed_ms,
                "message": str(e),
            }

    def _build_prompt(self, topic: str, tone: str, include_hashtags: bool) -> str:
        """Construct prompt for Facebook Fanpage content creation."""
        hashtag_instruction = (
            "5. Hashtags: Thêm cụm 3-7 hashtags thịnh hành và liên quan mật thiết ở cuối bài viết."
            if include_hashtags
            else "5. Hashtags: KHÔNG thêm bất kỳ hashtag (#) nào vào bài viết."
        )

        return f"""Bạn là một người sáng tạo nội dung mạng xã hội (Facebook Content Creator) xuất sắc, viết bài tự nhiên như một con người thực sự có chuyên môn sâu về chủ đề này.
Hãy viết một bài đăng Facebook Fanpage hoàn chỉnh, cuốn hút, chuẩn viral về chủ đề sau:

Chủ đề: {topic}
Giọng văn (Tone): {tone}
Ngôn ngữ: Tiếng Việt tự nhiên, phù hợp với phong cách đọc và thói quen lướt Facebook tại Việt Nam.

Quy tắc văn phong người thật (BẮT BUỘC):
1. Tiêu đề / Hook: Thu hút ngay trong 3 giây đầu tiên, đánh trúng tâm lý, tò mò hoặc sự chú ý thực tế của người đọc.
2. Nhịp văn tự nhiên: Xen kẽ câu ngắn và câu dài, ngắt nhịp thở tự nhiên như người thật đang trò chuyện hoặc chia sẻ góc nhìn.
3. Tránh tuyệt đối văn phong AI máy móc: KHÔNG dùng các câu mở đầu sáo rỗng (như 'Trong thời đại số...', 'Bạn có biết rằng...'), KHÔNG dùng câu chuyển ý cứng nhắc, KHÔNG ép buộc mọi đoạn đều phải có gạch đầu dòng và emoji giống hệt nhau.
4. Kêu gọi hành động (CTA): Tự nhiên, kích thích bình luận, chia sẻ quan điểm hoặc nhắn tin tư vấn mà không mang cảm giác gượng gạo.
{hashtag_instruction}

Lưu ý quan trọng:
- Bài viết phải hoàn chỉnh, có thể đăng ngay lên Fanpage.
- Không đưa vào các lời dẫn kỹ thuật hay ghi chú ngoài lề (như 'Dưới đây là bài viết...').
"""

    def _extract_hashtags(self, text: str) -> list[str]:
        """Extract unique hashtags from generated content."""
        tags = re.findall(r"#[A-Za-z0-9_À-ỹ]+", text)
        seen = set()
        unique = []
        for tag in tags:
            if tag.lower() not in seen:
                seen.add(tag.lower())
                unique.append(tag)
        return unique

    def generate_fanpage_post(
        self,
        topic: str,
        tone: str = "chuyên nghiệp, hấp dẫn",
        include_hashtags: bool = True,
        use_search: bool = True,
    ) -> dict[str, Any]:
        """Generate an engaging Facebook Fanpage post using OpenRouter.

        Args:
            topic: The topic or idea for the post.
            tone: Desired voice tone (e.g. chuyên nghiệp, hài hước, tin tức).
            include_hashtags: Whether to generate and extract hashtags.
            use_search: Whether to enable web search grounding via OpenRouter plugins.

        Returns:
            dict containing:
                - content (str): Full text of the generated post.
                - sources (list[str]): URLs used for search grounding.
                - suggested_hashtags (list[str]): Extracted hashtags.

        Raises:
            ValueError: If topic is empty or whitespace.
            RuntimeError: If OpenRouter returns an error or empty content.
        """
        if not topic or not topic.strip():
            raise ValueError("Vui lòng nhập chủ đề bài viết.")

        prompt = self._build_prompt(topic=topic.strip(), tone=tone, include_hashtags=include_hashtags)

        url = f"{self.BASE_URL}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
        }

        # Enable OpenRouter web search plugin if requested
        if use_search:
            payload["plugins"] = [{"id": "web"}]

        try:
            res = requests.post(
                url,
                headers=self._get_headers(),
                json=payload,
                timeout=60,
            )
            data = res.json()

            if res.status_code != 200:
                err_msg = data.get("error", {}).get("message", f"OpenRouter HTTP {res.status_code}")
                raise RuntimeError(f"Lỗi OpenRouter: {err_msg}")

            choices = data.get("choices", [])
            if not choices:
                raise RuntimeError("OpenRouter không trả về nội dung lựa chọn.")

            msg = choices[0].get("message", {}) or {}
            raw_content = msg.get("content")
            if not raw_content:
                # Fallback to reasoning / reasoning_content if content is null
                raw_content = msg.get("reasoning") or msg.get("reasoning_content") or ""

            content = str(raw_content or "").strip()
            if not content:
                raise RuntimeError("OpenRouter trả về nội dung rỗng.")

            # Extract citations/sources if available
            sources = []
            if use_search:
                citations = data.get("citations", [])
                for cit in citations:
                    if isinstance(cit, str) and cit not in sources:
                        sources.append(cit)

            hashtags = self._extract_hashtags(content) if include_hashtags else []

            return {
                "content": content,
                "sources": sources,
                "suggested_hashtags": hashtags,
            }

        except requests.RequestException as e:
            raise RuntimeError(f"Lỗi kết nối tới OpenRouter: {str(e)}")

    def rewrite_content(self, content: str, style_key: str = "final_polish") -> str:
        """Biên tập và viết lại văn bản theo phong cách người thật qua OpenRouter.

        Args:
            content: Nội dung văn bản hiện tại cần biên tập.
            style_key: Khóa phong cách biên tập trong REWRITE_STYLES.

        Returns:
            Văn bản đã được biên tập tự nhiên như người thật.
        """
        if not content or not str(content).strip():
            raise ValueError("Nội dung bài viết không được để trống khi yêu cầu biên tập lại.")

        style = REWRITE_STYLES.get(style_key, REWRITE_STYLES["final_polish"])
        prompt = f"{style['prompt']}\n{str(content).strip()}"

        headers = self._get_headers()
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Bạn là một biên tập viên con người xuất sắc, chuyên gia làm mượt và nhân bản hóa văn phong (Humanize AI text). "
                        "Chỉ trả về trực tiếp nội dung bài viết đã viết lại, không thêm lời chào, giải thích hay định dạng thừa bên ngoài."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.75,
        }

        try:
            res = requests.post(
                f"{self.BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
            data = res.json()

            if res.status_code != 200:
                err_msg = data.get("error", {}).get("message", f"OpenRouter HTTP {res.status_code}")
                raise RuntimeError(f"Lỗi OpenRouter: {err_msg}")

            choices = data.get("choices", [])
            if not choices:
                raise RuntimeError("OpenRouter không trả về nội dung lựa chọn.")

            msg = choices[0].get("message", {}) or {}
            raw_content = msg.get("content")
            if not raw_content:
                raw_content = msg.get("reasoning") or msg.get("reasoning_content") or ""

            rewritten_text = str(raw_content or "").strip()
            if not rewritten_text:
                raise RuntimeError("OpenRouter trả về nội dung rỗng.")

            return rewritten_text
        except requests.RequestException as e:
            raise RuntimeError(f"Lỗi kết nối tới OpenRouter: {str(e)}")
