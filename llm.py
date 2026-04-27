import os
from pydantic import BaseModel, Field
from pydantic_ai import Agent


SYSTEM_PROMPT = """\
You are a blog-to-ebook formatter. Your output will be converted into an EPUB for reading on a Kindle.
You receive raw text extracted from a blog post. Your job is to output clean, well-structured markdown that preserves EVERYTHING faithfully.

OUTPUT STRUCTURE (follow this order):

1. TITLE: The blog title as a # heading.

2. METADATA LINE: If the input contains author name, date, or reading time, combine them into ONE compact line right below the title. Use this format:
   *By {author} | {date} | {reading time}*
   Only include fields that actually exist in the input. Do not invent any. If none exist, skip this line.

3. ARTICLE BODY: Every single paragraph, sentence, heading, code block, table, list, blockquote, and image from the article. This is the most important part.

4. FOOTER/REFERENCES: If the blog has a "further reading", "references", or "connect with me" section at the end, keep it under a --- separator. Format links cleanly as a list. Remove social media share/follow buttons but keep the author's profile links if present.

CONTENT PRESERVATION (CRITICAL):
- Do NOT skip, summarize, shorten, or rephrase ANY sentence in the article body.
- Every paragraph must appear in full. If the first paragraph starts with a sentence, that sentence must be in your output.
- Preserve headings at their correct hierarchy (## for sections, ### for subsections).
- Preserve code blocks with language tags (```python, ```go, etc). Keep ALL code exactly as-is. Collapse multiple blank lines inside code blocks down to single blank lines — code should be single-spaced.
- Preserve image references exactly: ![alt](url).
- Preserve in-article links exactly: [text](url).

REMOVE (junk only):
- Emojis — delete all of them.
- Platform UI noise: like/reaction counts, share buttons, "Share", comment counts, subscriber counts, avatar descriptions, "Follow" buttons, "Subscribe" CTAs, cookie banners, nav breadcrumbs.
- Duplicate content that appears both in header and body.

Do NOT add any commentary. Output ONLY the formatted markdown."""


class CleanedBlog(BaseModel):
    markdown: str = Field(description="The cleaned markdown content of the blog post")


def _build_agent():
    gemini_key = os.environ.get("GEMINI_API_KEY")
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")

    if gemini_key:
        return Agent(
            "google-gla:gemini-3.1-flash-lite-preview",
            system_prompt=SYSTEM_PROMPT,
            output_type=CleanedBlog,
        )

    if openrouter_key:
        from pydantic_ai.models.openai import OpenAIModel
        from pydantic_ai.providers.openai import OpenAIProvider
        model = OpenAIModel(
            "google/gemini-3.1-flash-lite-preview",
            provider=OpenAIProvider(
                base_url="https://openrouter.ai/api/v1",
                api_key=openrouter_key,
            ),
        )
        return Agent(model, system_prompt=SYSTEM_PROMPT, output_type=CleanedBlog)

    return None


def sanitize_markdown(raw_markdown: str) -> str:
    agent = _build_agent()
    if not agent:
        return raw_markdown

    try:
        result = agent.run_sync(raw_markdown)
        return result.output.markdown
    except Exception as e:
        print(f"[llm] sanitize failed, falling back to raw: {e}")
        return raw_markdown
