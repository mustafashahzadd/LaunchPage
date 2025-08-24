# planner_blog.py
import streamlit as st
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from schemas_blog import ResearchLetter, BlogPost

# Access from st.secrets instead of os.getenv


llm = ChatOpenAI(
    api_key=st.secrets["OPENAI_API_KEY"],
    model=st.secrets.get("OPENAI_MODEL_PLANNER", "gpt-5"),
    temperature=0.25,
)

# Letter planning prompt
letter_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a professional content planner specializing in research letters. 
    Transform the research content into a well-structured research letter suitable for email distribution.
    
    Structure requirements:
    - Introduction: Engaging opening that introduces the research topic
    - Body: Comprehensive analysis with trends, insights, and risks
    - Conclusion: Clear summary and key takeaways
    - References: Properly formatted citations"""),
    ("user", """Date Context: {date_context}

Research Topic: {goal}

Research Content to Structure:
Introduction: {introduction}
Body: {body}
Conclusion: {conclusion}
References: {references}

Please structure this into a professional research letter format."""),
])

# Blog planning prompt  
blog_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a professional content planner specializing in blog posts.
    Transform the research content into a well-structured blog post suitable for web publishing.
    
    Structure requirements:
    - Title: Compelling and SEO-friendly
    - Introduction: Hook the reader and introduce the topic
    - Background: Provide necessary context
    - Body: Detailed analysis with trends, insights, and practical implications
    - Conclusion: Summarize key points and provide actionable insights
    - References: Properly formatted for web"""),
    ("user", """Date Context: {date_context}

Research Topic: {goal}

Research Content to Structure:
Introduction: {introduction}
Body: {body}
Conclusion: {conclusion}
References: {references}

Please structure this into an engaging blog post format."""),
])

letter_chain = letter_prompt | llm.with_structured_output(ResearchLetter)
blog_chain = blog_prompt | llm.with_structured_output(BlogPost)

def make_research_letter(goal: str, research_content: ResearchLetter, date_context: str) -> ResearchLetter:
    """Plan and structure the research content into a professional letter format."""
    try:
        # Convert references to string format for the prompt
        refs_str = "\n".join([f"- {ref.title}: {ref.url}" for ref in research_content.references])
        
        result = letter_chain.invoke({
            "date_context": date_context,
            "goal": goal,
            "introduction": research_content.introduction,
            "body": research_content.body,
            "conclusion": research_content.conclusion,
            "references": refs_str
        })
        
        return result
    except Exception as e:
        raise Exception(f"Error in letter planning: {str(e)}")

def make_blog_post(goal: str, research_content: ResearchLetter, date_context: str) -> BlogPost:
    """Plan and structure the research content into a blog post format."""
    try:
        # Convert references to string format for the prompt
        refs_str = "\n".join([f"- {ref.title}: {ref.url}" for ref in research_content.references])
        
        result = blog_chain.invoke({
            "date_context": date_context,
            "goal": goal,
            "introduction": research_content.introduction,
            "body": research_content.body,
            "conclusion": research_content.conclusion,
            "references": refs_str
        })
        
        return result
    except Exception as e:
        raise Exception(f"Error in blog planning: {str(e)}")