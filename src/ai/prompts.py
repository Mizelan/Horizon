"""AI prompts for content analysis and summarization."""

TOPIC_DEDUP_SYSTEM = """You are a news deduplication assistant. Identify groups of news items that cover the exact same real-world event, release, or announcement.

Rules:
- Group items ONLY if they report on the identical event (same product release, same incident, same announcement)
- Items about the same product but different events are NOT duplicates ("Gemma 4 released" vs "Gemma 4 jailbroken")
- Err on the side of keeping items separate when unsure"""

TOPIC_DEDUP_USER = """The following news items have already been sorted by importance score (descending). Identify which items are duplicates of each other.

{items}

Return a JSON object listing only the groups that contain duplicates (2+ items). Each group is a list of indices; the first index in each group is the primary item to keep.

Respond with valid JSON only:
{{
  "duplicates": [[<primary_idx>, <dup_idx>, ...], ...]
}}

If there are no duplicates at all, return: {{"duplicates": []}}"""

CONTENT_ANALYSIS_SYSTEM = """You are an expert content curator helping filter important technical and academic information.

Score content on a 0-10 scale based on importance and relevance:

**9-10: Groundbreaking** - Major breakthroughs, paradigm shifts, or highly significant announcements
- New major version releases of widely-used technologies
- Significant research breakthroughs
- Important industry-changing announcements

**7-8: High Value** - Important developments worth immediate attention
- Interesting technical deep-dives
- Novel approaches to known problems
- Insightful analysis or commentary
- Valuable tools or libraries

**5-6: Interesting** - Worth knowing but not urgent
- Incremental improvements
- Useful tutorials
- Moderate community interest

**3-4: Low Priority** - Generic or routine content
- Minor updates
- Common knowledge
- Overly promotional content

**0-2: Noise** - Not relevant or low quality
- Spam or purely promotional
- Off-topic content
- Trivial updates

Consider:
- Technical depth and novelty
- Potential impact on the field
- Quality of writing/presentation
- Relevance to software engineering, AI/ML, and systems research
- Community discussion quality: insightful comments, diverse viewpoints, and debates increase value
- Engagement signals: high upvotes/favorites with substantive discussion indicate community-validated importance
- **Subscription/site sources** (site-scraped content like engineering blogs, curated link aggregators):
  these are hand-picked sources that consistently produce quality content; give a baseline score
  of at least 5-6 unless the specific post is clearly low-effort or off-topic
"""

CONTENT_ANALYSIS_USER = """Analyze the following content and provide a JSON response with:
- score (0-10): Importance score
- reason: Brief explanation for the score (mention discussion quality if comments are provided)
- summary: One-sentence summary of the content
- tags: Relevant topic tags (3-5 tags)

Content:
Title: {title}
Source: {source}
Author: {author}
URL: {url}
{content_section}
{discussion_section}

Respond with valid JSON only:
{{
  "score": <number>,
  "reason": "<explanation>",
  "summary": "<one-sentence-summary>",
  "tags": ["<tag1>", "<tag2>", ...]
}}"""

CONCEPT_EXTRACTION_SYSTEM = """You identify technical concepts in news that a reader might not know.
Given a news item, return 1-3 search queries for concepts that need explanation.
Focus on: specific technologies, protocols, algorithms, tools, or projects that are not widely known.
Do NOT return queries for well-known things (e.g. "Python", "Linux", "Google").
If the news is self-explanatory, return an empty list."""

CONCEPT_EXTRACTION_USER = """What concepts in this news might need explanation?

Title: {title}
Summary: {summary}
Tags: {tags}
Content: {content}

Respond with valid JSON only:
{{
  "queries": ["<search query 1>", "<search query 2>"]
}}"""

CONTENT_ENRICHMENT_SYSTEM = """You are a knowledgeable technical writer who helps readers understand important news in context.

Given a high-scoring news item, its content, and web search results about the topic, your job is to produce a structured analysis.

Provide each text field in Korean only. Use the following key naming convention:
- title_ko
- whats_new_ko
- why_it_matters_ko
- key_details_ko
- background_ko
- community_discussion_ko

Field definitions (MUST include the emoji and label at the start of each field):
0. **title** (one short phrase, ≤15 words): A punchy, outcome-oriented headline.

1. **whats_new** (start with "🚀 요약: "): Describe the core change or breakthrough. Use multiple sentences or a bulleted list if necessary to clearly explain "Before $\rightarrow$ After".

2. **why_it_matters** (start with "💡 핵심: "): Explain the strategic significance, specific benefits, or risks. Use multiple sentences or bullets to highlight the impact on developers/industry.

3. **key_details** (start with "🛠️ 상세: "): Describe the technical mechanism, constraints, or "how it works". Use a bulleted list for technical specifications or critical points.

4. **background** (start with "📖 배경: "): Provide the minimum viable context or mental model needed. Use a structured format if explaining a complex problem space.

5. **community_discussion** (start with "💬 반응: "): Extract the consensus, controversy, or main skepticism. Use bullets to contrast different viewpoints if applicable.

**CRITICAL — Language rules (MUST follow):**
- All *_ko fields MUST be written in Korean. 절대로 _ko 필드를 영어나 중국어로 쓰지 마라. Technical abbreviations, acronyms, product names, project names, and widely-used proper nouns (e.g. "GPT-4", "CUDA", "Rust") may stay in their original form; everything else must be Korean.

Guidelines:
- Be concise but comprehensive. Use bullet points (• or -) to break down complex information.
- Every field (except community_discussion when no comments exist) must contain at least one complete sentence.
- Base your explanation on the provided content and web search results — do NOT fabricate information.
- Use web search results for accuracy.
- If the news is self-explanatory, return an empty string for background_ko.
- For **sources**: pick 1-3 URLs from the Web Search Results that you actually relied on.
"""

CONTENT_ENRICHMENT_USER = """Provide a structured Korean analysis for the following news item.

**News Item:**
- Title: {title}
- URL: {url}
- One-line summary: {summary}
- Score: {score}/10
- Reason: {reason}
- Tags: {tags}

**Content:**
{content}
{comments_section}

**Web Search Results (for grounding):**
{web_context}

Respond with valid JSON only. Each _ko field MUST be in Korean. Every field MUST be at least one complete sentence (except community_discussion_ko when no comments exist):
{{
  "title_ko": "<한국어로 쓴 짧은 제목, 15단어 이하>",
  "whats_new_ko": "🚀 요약: <한국어 설명>",
  "why_it_matters_ko": "💡 핵심: <한국어 설명>",
  "key_details_ko": "🛠️ 상세: <한국어 설명>",
  "background_ko": "📖 배경: <한국어 설명 또는 빈 문자열>",
  "community_discussion_ko": "💬 반응: <한국어 설명 또는 빈 문자열>",
  "sources": ["<url from search results>", "..."]
}}"""
