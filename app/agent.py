from langchain.agents import Tool, initialize_agent
from langchain.agents.agent_types import AgentType
from langchain.memory import ConversationBufferMemory
from langchain_google_genai import ChatGoogleGenerativeAI
from llm_define import OllamaLLM
from llm_define import HuggingFaceChatLLM

from dotenv import load_dotenv
from db import ChromaIndexer,create_retrieval_qa_tool,create_website_search_tool,create_build_index_tool
from web_scraper import create_website_extracter_tool
import os 
load_dotenv()


# Initialize your RAG components
def initialize_rag_agent():
    """Initialize the RAG agent with ChromaDB and tools"""
    try:
        chroma_indexer = ChromaIndexer()
        
        # Initialize LLM
        GEMINI_API_KEY=os.getenv("GEMINI_API_KEY")
     
        llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=GEMINI_API_KEY)
        # llm = OllamaLLM(
        #             model_name="tinydolphin:latest",  # Lightweight for Railway
        #             base_url="http://localhost:11434"
        #         )
        
        
       


        
        # Create tools
        search_tool = create_website_search_tool(chroma_indexer)
        website_analyzer_tool=create_website_extracter_tool()
        build_index_tool = create_build_index_tool(chroma_indexer)

        tools = [search_tool,website_analyzer_tool,build_index_tool]
        
        # if llm:
        #     retriver_tool = create_retrieval_qa_tool(chroma_indexer, llm)
        #     tools.append(retriver_tool)
            
        
        memory = ConversationBufferMemory(memory_key="chat_history")

        # Custom prompt
        custom_prompt = """You are a helpful assistant who can search through website content and answer questions.
                You have access to a database of crawled website content. Use the SearchWebsite tool for simple searches and provide detial answer . 
                in your answer provide detial answer and provide the source of that answer like the url of the site .
                Always explain your thinking, then choose an action from the available tools.
                """
                
        agent = initialize_agent(
                    tools=tools,
                    llm=llm,
                    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
                    verbose=True,
                    agent_kwargs={"prefix": custom_prompt},
                    memory=memory,
                    handle_parsing_errors=True
                )
        
        return agent, chroma_indexer
    
    except Exception as e:
        print(f"Error initializing RAG agent: {e}")
        return None, None

        


