"""Gemini Service with Google Search Grounding for Facebook Fanpage Auto-Poster."""

from __future__ import annotations

import os
import re
from typing import Any
from google import genai
from google.genai import types



REWRITE_STYLES = {
    "human_editor": {
        "name": "👤 Biên tập như người thật có kinh nghiệm",
        "description": "Loại bỏ cách diễn đạt máy móc, câu sáo rỗng, tạo cảm giác được viết bởi người có kinh nghiệm thực tế.",
        "prompt": (
            "Hãy đóng vai một biên tập viên con người, không phải AI.\n"
            "Viết lại nội dung dưới đây để nó có cảm giác được viết tự nhiên bởi một người thực sự có kinh nghiệm về chủ đề này.\n"
            "Loại bỏ:\n"
            "- Cách diễn đạt máy móc.\n"
            "- Những cấu trúc câu quá dễ đoán.\n"
            "- Ngôn ngữ quá hoàn hảo hoặc sáo rỗng.\n"
            "- Những phần giải thích không cần thiết.\n"
            "Giữ nguyên ý nghĩa chính nhưng làm cho cách diễn đạt tự nhiên, có cá tính và gần với cách một người thật sự sẽ viết.\n\n"
            "Văn bản:\n"
        ),
    },
    "natural_rhythm": {
        "name": "🌊 Tạo nhịp văn tự nhiên (Ngắn / Dài xen kẽ)",
        "description": "Độ dài câu xen kẽ, ngắt nhịp tự nhiên, tránh cấu trúc đoạn quá đều và công thức lặp lại.",
        "prompt": (
            "Viết lại văn bản này theo cách phản ánh cách con người thực sự suy nghĩ và nói chuyện.\n"
            "Hãy sử dụng:\n"
            "- Độ dài câu khác nhau.\n"
            "- Những khoảng ngắt tự nhiên.\n"
            "- Câu ngắn xen kẽ câu dài khi phù hợp.\n"
            "- Cách diễn đạt rõ ràng nhưng không quá hoàn hảo.\n"
            "Tránh:\n"
            "- Các đoạn văn có cấu trúc quá đều.\n"
            "- Sự đối xứng máy móc giữa các câu.\n"
            "- Công thức viết lặp đi lặp lại.\n"
            "Mục tiêu là khiến nội dung có nhịp điệu tự nhiên như một người thật đang chia sẻ suy nghĩ.\n\n"
            "Văn bản:\n"
        ),
    },
    "anti_formulaic": {
        "name": "🚫 Phá vỡ khuôn mẫu máy móc & sáo rỗng",
        "description": "Loại bỏ câu chuyển ý chung chung, không giải thích thừa, tránh câu kết rập khuôn.",
        "prompt": (
            "Viết lại văn bản này và chủ động loại bỏ những kiểu diễn đạt khiến nội dung có cảm giác quá khuôn mẫu.\n"
            "Tránh:\n"
            "- Những câu chuyển ý chung chung.\n"
            "- Giải thích quá nhiều những điều người đọc đã hiểu.\n"
            "- Các đoạn có cấu trúc giống nhau.\n"
            "- Việc cố cân bằng mọi quan điểm một cách máy móc.\n"
            "- Những câu kết quá hoàn hảo hoặc sáo rỗng.\n"
            "Hãy giữ cách viết tự nhiên, trực tiếp và giống cách một người thật sẽ diễn đạt khi họ thực sự hiểu chủ đề.\n\n"
            "Văn bản:\n"
        ),
    },
    "consistent_voice": {
        "name": "🎙️ Giữ giọng văn nhất quán, gần gũi",
        "description": "Mang cảm giác một cá nhân cụ thể đang viết, tránh văn phong doanh nghiệp cứng nhắc.",
        "prompt": (
            "Viết lại nội dung này bằng một giọng văn tự nhiên và nhất quán.\n"
            "Giữ cùng một cá tính xuyên suốt bài viết nhưng cho phép tông giọng thay đổi tự nhiên tùy từng đoạn.\n"
            "Tránh:\n"
            "- Lặp lại cùng một cụm từ.\n"
            "- Lặp cấu trúc câu.\n"
            "- Những cách chuyển ý dễ đoán.\n"
            "- Giọng văn quá trang trọng hoặc giống tài liệu doanh nghiệp.\n"
            "Ưu tiên cách diễn đạt gần gũi, có nhịp điệu và mang cảm giác một người cụ thể đang viết.\n\n"
            "Văn bản:\n"
        ),
    },
    "reader_experience": {
        "name": "🎯 Viết theo góc nhìn người đọc (Dễ hiểu ngay)",
        "description": "Dễ đọc lướt, hiểu ngay khi đọc newsfeed, chỉ giữ câu tạo giá trị thực sự.",
        "prompt": (
            "Viết lại văn bản này dựa trên cách một người đọc thực sự sẽ tiếp nhận nó.\n"
            "Ưu tiên:\n"
            "- Dễ đọc.\n"
            "- Dễ hiểu ngay.\n"
            "- Có nhịp tự nhiên.\n"
            "- Các ý nối với nhau hợp lý.\n"
            "- Chỉ giữ những câu thực sự tạo thêm giá trị.\n"
            "Đừng cố làm cho nội dung nghe quá tối ưu, quá hướng dẫn hoặc quá hoàn hảo.\n"
            "Nếu một câu nghe giống ngôn ngữ máy móc hoặc không giống cách con người thường nói, hãy viết lại đơn giản và tự nhiên hơn.\n\n"
            "Văn bản:\n"
        ),
    },
    "final_polish": {
        "name": "🔍 Lượt rà soát & biên tập cuối cùng (Final Polish)",
        "description": "Rà soát từng câu: loại bỏ câu máy móc, sáo rỗng mà không thay đổi thông điệp chính.",
        "prompt": (
            "Hãy lấy bản nháp dưới đây và thực hiện một lượt biên tập cuối cùng chỉ tập trung vào việc khiến nó có cảm giác được một người thật viết.\n"
            "Kiểm tra từng câu.\n"
            "Nếu câu nào: Quá trang trọng, quá hoàn hảo, máy móc, sáo rỗng, có cấu trúc dễ đoán, hoặc không giống cách một người bình thường sẽ diễn đạt => Hãy viết lại câu đó.\n"
            "Không thay đổi thông điệp chính hoặc tự thêm thông tin mới.\n"
            "Kết quả cuối cùng phải rõ ràng, tự nhiên, có cá tính và dễ đọc.\n\n"
            "Văn bản:\n"
        ),
    },
}


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
        if client:
            self.client = client
        else:
            self.client = genai.Client(api_key=self.api_key)

    def _build_prompt(
        self,
        topic: str,
        tone: str,
        include_hashtags: bool,
        target_hashtags: str | None = None,
        target_page_name: str | None = None,
    ) -> str:
        """Construct an optimized prompt for generating a viral Facebook Fanpage post."""
        if include_hashtags:
            if target_hashtags and str(target_hashtags).strip():
                clean_target_tags = str(target_hashtags).strip()
                page_info = f" cho Fanpage '{target_page_name}'" if target_page_name else ""
                hashtag_instruction = (
                    f"5. Hashtags: Thêm cụm 3-7 hashtags thịnh hành về chủ đề VÀ BẮT BUỘC bao gồm các hashtag khu vực địa phương sau{page_info}: {clean_target_tags} ở cuối bài viết."
                )
            else:
                hashtag_instruction = (
                    "5. Hashtags: Thêm cụm 3-7 hashtags thịnh hành và liên quan mật thiết ở cuối bài viết."
                )
        else:
            hashtag_instruction = "5. Hashtags: KHÔNG thêm bất kỳ hashtag (#) nào vào bài viết."

        prompt = f"""Bạn là một người sáng tạo nội dung mạng xã hội (Facebook Content Creator) xuất sắc, viết bài tự nhiên như một con người thực sự có chuyên môn sâu về chủ đề này.
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

Lưu ý: Chỉ trả về nội dung bài viết hoàn chỉnh để đăng ngay, không kèm bất kỳ lời dẫn hay giải thích kỹ thuật nào bên ngoài bài viết."""
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
        target_hashtags: str | None = None,
        target_page_name: str | None = None,
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
            topic=topic.strip(),
            tone=tone,
            include_hashtags=include_hashtags,
            target_hashtags=target_hashtags,
            target_page_name=target_page_name,
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

    def rewrite_content(self, content: str, style_key: str = "final_polish") -> str:
        """Biên tập và viết lại văn bản theo phong cách người thật (Humanize AI).

        Args:
            content: Nội dung văn bản hiện tại cần biên tập.
            style_key: Khóa phong cách biên tập trong REWRITE_STYLES.

        Returns:
            Văn bản đã được biên tập tự nhiên như người thật.
        """
        if not content or not str(content).strip():
            raise ValueError("Nội dung bài viết không được để trống khi yêu cầu biên tập lại.")

        style = REWRITE_STYLES.get(style_key, REWRITE_STYLES["final_polish"])
        system_instruction = (
            "Bạn là một biên tập viên con người xuất sắc, chuyên gia làm mượt và nhân bản hóa văn phong (Humanize AI text). "
            "Chỉ trả về trực tiếp nội dung bài viết đã viết lại, không thêm lời chào, giải thích hay định dạng thừa bên ngoài."
        )
        prompt = f"{style['prompt']}\n{str(content).strip()}"

        models_to_try = [self.model]
        if "gemini-3.5-flash-lite" not in models_to_try:
            models_to_try.append("gemini-3.5-flash-lite")
        if "gemini-3.8-flash" not in models_to_try:
            models_to_try.append("gemini-3.8-flash")

        last_error = None
        for m in models_to_try:
            try:
                config = types.GenerateContentConfig(
                    temperature=0.75,
                    system_instruction=system_instruction,
                )
                response = self.client.models.generate_content(
                    model=m,
                    contents=prompt,
                    config=config,
                )
                rewritten_text = getattr(response, "text", "") or ""
                if rewritten_text.strip():
                    return rewritten_text.strip()
            except Exception as e:
                last_error = e
                continue

        if last_error:
            raise last_error
        raise RuntimeError("Không thể biên tập lại nội dung với Gemini.")
