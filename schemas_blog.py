from typing import List
from pydantic import BaseModel, Field

class Reference(BaseModel):
    title: str
    url: str

class ResearchLetter(BaseModel):
    introduction: str = Field(description="Introduction section of the research letter")
    body: str = Field(description="Main body with trends, insights, and analysis")
    conclusion: str = Field(description="Conclusion summarizing key points")
    references: List[Reference] = Field(description="List of references with title and URL")

class BlogPost(BaseModel):
    title: str = Field(description="Blog post title")
    introduction: str = Field(description="Blog introduction section")
    background: str = Field(description="Background context section")
    body: str = Field(description="Main body with detailed analysis and insights")
    conclusion: str = Field(description="Blog conclusion")
    references: List[Reference] = Field(description="List of references with title and URL")

class FinalAssets(BaseModel):
    letter_content: str = Field(description="Complete formatted research letter ready for email")
    blog_content: str = Field(description="Complete formatted blog post ready for web publishing")