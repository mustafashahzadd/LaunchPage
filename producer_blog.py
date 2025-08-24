# producer_blog.py
import os
import datetime as dt
from langchain_core.prompts import ChatPromptTemplate
# from langchain_groq import ChatGroq
from schemas_blog import ResearchLetter, BlogPost, FinalAssets
import streamlit as st

from langchain_openai import ChatOpenAI  # ⬅️ new import

llm = ChatOpenAI(
    api_key=st.secrets["OPENAI_API_KEY"],
    model=st.secrets.get("OPENAI_MODEL_PRODUCER", "gpt-5"),
    temperature=0.25,
)


# # ---------- LLM ----------
# GROQ_API_KEY = os.getenv("GROQ_API_KEYs")
# GROQ_MODEL = os.getenv("GROQ_MODEL_PRODUCER", "llama-3.1-8b-instant")



# ---------- Prompt ----------
final_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are an assistant that transforms structured research and blog plans "
     "into final, polished publications."),
    ("user", """Today's date: {date_context}
Topic/Goal: {goal}

Research Letter Structure:
{letter_structure}

Blog Structure:
{blog_structure}

Generate the final outputs as high-quality text. 
Return them in the fields letter_content and blog_content."""),
])

# ---------- Producer chain ----------
producer_chain = final_prompt | llm.with_structured_output(FinalAssets)


# ---------- Function ----------
def generate_final_assets(
    goal: str,
    letter_structure: ResearchLetter,
    blog_structure: BlogPost,
    date_context: str
) -> FinalAssets:
    """Generate final, publication-ready letter and blog content."""

    from schemas_blog import FinalAssets as FA

    # Flatten structures into readable text
    letter_text = f"""
    Introduction: {letter_structure.introduction}

    Body: {letter_structure.body}

    Conclusion: {letter_structure.conclusion}

    References:
    {chr(10).join([f"- {ref.title}: {ref.url}" for ref in letter_structure.references])}
    """.strip()

    blog_text = f"""
    Title: {blog_structure.title}

    Introduction: {blog_structure.introduction}

    Background: {blog_structure.background}

    Body: {blog_structure.body}

    Conclusion: {blog_structure.conclusion}

    References:
    {chr(10).join([f"- {ref.title}: {ref.url}" for ref in blog_structure.references])}
    """.strip()

    # 1) Try structured output
    try:
        result = producer_chain.invoke({
            "date_context": date_context,
            "goal": goal,
            "letter_structure": letter_text,
            "blog_structure": blog_text
        })

        # Normalize escapes and validate
        lc = (getattr(result, "letter_content", "") or "").replace("\\n", "\n").replace("\\t", "\t").strip()
        bc = (getattr(result, "blog_content", "") or "").replace("\\n", "\n").replace("\\t", "\t").strip()

        if lc or bc:
            result.letter_content = lc
            result.blog_content = bc
            return result

    except Exception:
        # fall through to fallback
        pass

    # 2) Fallback: plain generation (prompt | llm)
    fallback_prompt = ChatPromptTemplate.from_messages([
        ("system", "Generate publication-ready content. Use actual line breaks, not \\n."),
        ("user", """Generate two pieces of content for the topic '{goal}':

1) A professional research letter (start with LETTER:)
2) A blog post (start with BLOG:)

Base it on this research:
{letter_structure}

Use proper formatting with real line breaks.""")
    ])
    fallback_chain = fallback_prompt | llm

    try:
        fb = fallback_chain.invoke({
            "goal": goal,
            "letter_structure": letter_text
        })
        content = (getattr(fb, "content", "") or "").replace("\\n", "\n").replace("\\t", "\t")

        letter_content = ""
        blog_content = ""

        if "LETTER:" in content and "BLOG:" in content:
            parts = content.split("BLOG:", 1)
            letter_content = parts[0].replace("LETTER:", "").strip()
            blog_content = parts[1].strip()
        else:
            # If parsing fails, reuse whole text for both
            letter_content = f"Dear Reader,\n\n{content.strip()}\n\nBest regards,\n[Your Name]"
            blog_content = content.strip()

        if letter_content.strip() or blog_content.strip():
            return FA(letter_content=letter_content, blog_content=blog_content)

    except Exception:
        # fall through to last resort
        pass

    # 3) Last resort basic content so the app never gets empties
    basic_letter = f"""Dear Reader,

I'm writing to share insights on {goal}.

{letter_structure.introduction}

{letter_structure.body}

{letter_structure.conclusion}

Best regards,
[Your Name]"""

    basic_blog = f"""# {goal}

{blog_structure.introduction}

## Background
{blog_structure.background}

## Analysis
{blog_structure.body}

## Conclusion
{blog_structure.conclusion}"""

    return FA(letter_content=basic_letter, blog_content=basic_blog)
