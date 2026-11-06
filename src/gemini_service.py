"""Gemini Service with Google Search Grounding for Facebook Fanpage Auto-Poster."""

from __future__ import annotations

import os
import re
from typing import Any
from google import genai
from google.genai import types


class GeminiService:
    """Service to generate high-engagement Facebook Fanpage posts using Google Gemini

    and optional Google Search Grounding.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-3.5-flash-lite",
        client: Any = None,
    ) -> None:
        """Initialize GeminiService.

        Args:
            api_key: Google Gemini API key. Defaults to GEMINI_API_KEY environment variable.
            model: Gemini model identifier. Defaults to 'gemini-3.5-flash-lite'.
            client: Optional pre-configured genai.Client instance (useful for testing).

        Raises:
            ValueError: If api_key is missing or empty.
        """
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key or not self.api_key.strip():
            raise ValueError(
                "GEMINI_API_KEY is required. Please provide it in constructor or set GEMINI_API_KEY environment variable."
            )
        self.model = os.environ.get("GEMINI_MODEL") or model or "gemini-3.5-flash-lite"
        self.client = client or genai.Client(api_key=self.api_key)

    def _build_prompt(
        self, topic: str, tone: str, include_hashtags: bool
    ) -> str:
        """Construct an optimized prompt for generating a viral Facebook Fanpage post."""
        hashtag_instruction = (
            "5. Hashtags: Thêm cụm 3-7 hashtags thịnh hành và liên quan mật thiết ở cuối bài viết."
            if include_hashtags
            else "5. Hashtags: KHÔNG thêm bất kỳ hashtag (#) nào vào bài viết."
        )

        prompt = f"""Bạn là một chuyên gia sáng tạo nội dung mạng xã hội (Facebook Content Creator) chuyên nghiệp và xuất sắc.
Hãy viết một bài đăng Facebook Fanpage hoàn chỉnh, cuốn hút, chuẩn viral về chủ đề sau:

Chủ đề: {topic}
Giọng văn (Tone): {tone}
Ngôn ngữ: Tiếng Việt tự nhiên, phù hợp với phong cách đọc của người dùng Facebook tại Việt Nam.

Cấu trúc bài viết bắt buộc:
1. Tiêu đề / Hook: Giật gân, gợi sự tò mò, bắt mắt với emoji phù hợp nhằm thu hút người đọc trong 3 giây đầu tiên.
2. Đoạn mở đầu (Intro): Đặt vấn đề chạm đúng nỗi đau (pain point) hoặc sự quan tâm lớn của độc giả.
3. Thân bài (Body): Trình bày súc tích, chia thành các ý gạch đầu dòng rõ ràng, sử dụng emoji trực quan, đưa ra thông tin hữu ích, số liệu hoặc sự thật cập nhật nếu có.
4. Kêu gọi hành động (Call To Action - CTA): Câu hỏi hoặc lời mời tương tác kích thích bình luận, chia sẻ hoặc thảo luận sôi nổi.
{hashtag_instruction}

Hãy viết bài đăng trực tiếp, tự nhiên, không kèm các lời giải thích thừa bên ngoài bài viết."""
        return prompt

    def _extract_sources(self, response: Any) -> list[str]:
        """Extract unique web source URLs from Gemini grounding metadata."""
        sources: list[str] = []
        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            grounding_metadata = getattr(candidate, "grounding_metadata", None)
            if not grounding_metadata:
                continue
            chunks = getattr(grounding_metadata, "grounding_chunks", None)
            if not chunks:
                continue
            for chunk in chunks:
                web = getattr(chunk, "web", None)
                if web:
                    uri = getattr(web, "uri", None)
                    if uri and uri not in sources:
                        sources.append(uri)
        return sources

    def _extract_hashtags(self, content: str) -> list[str]:
        """Extract unique hashtags from post content."""
        if not content:
            return []
        tags = re.findall(r"#[\w\d_]+", content, flags=re.UNICODE)
        unique_tags: list[str] = []
        for tag in tags:
            if tag not in unique_tags:
                unique_tags.append(tag)
        return unique_tags

    def generate_fanpage_post(
        self,
        topic: str,
        tone: str = "chuyên nghiệp, hấp dẫn",
        include_hashtags: bool = True,
        use_search: bool = True,
    ) -> dict[str, Any]:
        """Generate a Facebook Fanpage post based on topic and options.

        Args:
            topic: The topic or idea for the post.
            tone: The tone of voice (e.g., 'chuyên nghiệp, hấp dẫn', 'hài hước', 'sâu sắc').
            include_hashtags: Whether to generate and include hashtags.
            use_search: Whether to enable Google Search Grounding for real-time information.

        Returns:
            Dictionary containing:
                - 'content': Generated text of the post.
                - 'sources': List of web source URLs if search grounding was used.
                - 'suggested_hashtags': List of hashtags found in the post.

        Raises:
            ValueError: If topic is empty or whitespace.
        """
        if not topic or not topic.strip():
            raise ValueError("Topic cannot be empty")

        prompt = self._build_prompt(
            topic=topic.strip(), tone=tone, include_hashtags=include_hashtags
        )

        if use_search:
            config = types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )
        else:
            config = types.GenerateContentConfig()

        models_to_try = [self.model]
        for fallback_m in ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.8-flash"]:
            if fallback_m not in models_to_try:
                models_to_try.append(fallback_m)

        response = None
        last_error = None
        used_search = use_search

        for m in models_to_try:
            try:
                response = self.client.models.generate_content(
                    model=m,
                    contents=prompt,
                    config=config,
                )
                break
            except Exception as e:
                last_error = e
                # If Google Search tool quota was exhausted (429), retry without search
                if used_search and "429" in str(e):
                    try:
                        used_search = False
                        response = self.client.models.generate_content(
                            model=m,
                            contents=prompt,
                            config=types.GenerateContentConfig(),
                        )
                        break
                    except Exception as inner_e:
                        last_error = inner_e
                continue

        if response is None:
            if last_error:
                raise last_error
            raise RuntimeError("Không thể tạo nội dung từ Gemini.")

        content = getattr(response, "text", "") or ""
        sources = self._extract_sources(response) if used_search else []
        hashtags = self._extract_hashtags(content) if include_hashtags else []

        return {
            "content": content,
            "sources": sources,
            "suggested_hashtags": hashtags,
        }
