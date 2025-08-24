# researcher_blog.py
import streamlit as st
# from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from schemas_blog import ResearchLetter

# Access from st.secrets instead of os.getenv
# llm = ChatGroq(
#     api_key=st.secrets.get("GROQ_API_KEYs"),
#     model=st.secrets.get("GROQ_MODEL", "llama-3.1-8b-instant"),
#     temperature=0.3
# )


from langchain_openai import ChatOpenAI  # ⬅️ new import

llm = ChatOpenAI(
    api_key=st.secrets["OPENAI_API_KEY"],
    model=st.secrets.get("OPENAI_MODEL_PRODUCER", "gpt-5"),
    temperature=0.25,
)


research_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are an expert researcher. Your task is to research the given topic and provide:
    1. A comprehensive introduction to the topic
    2. Latest trends, insights, and analysis in the body
    3. Risks and considerations associated with the topic
    4. A conclusive summary
    5. Relevant references (minimum 3-5 credible sources)
    
    Focus on providing accurate, up-to-date information that would be valuable for the target audience."""),
    ("user", """Date Context: {date_context}
    
Research Topic: {goal}

Please provide comprehensive research on this topic with the structure:
- Introduction: Brief overview and importance of the topic
- Body: Latest trends, key insights, detailed analysis, and associated risks
- Conclusion: Summary of key findings and implications
- References: Credible sources (academic papers, industry reports, reputable websites)"""),
])

research_chain = research_prompt | llm.with_structured_output(ResearchLetter)

def make_research_for_letter(goal: str, date_context: str) -> ResearchLetter:
    """Generate comprehensive research content for the given topic."""
    try:
        result = research_chain.invoke({
            "goal": goal,
            "date_context": date_context
        })
        
        if isinstance(result, ResearchLetter):
            return result
        else:
            raise ValueError("Received unexpected result format from research chain")
            
    except Exception as e:
        raise Exception(f"Error in research generation: {str(e)}")