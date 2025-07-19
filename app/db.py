import os
import json
import shutil
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.agents import Tool, initialize_agent
from langchain.agents.agent_types import AgentType
from langchain.chains import RetrievalQA
from dotenv import load_dotenv

# Your existing ChromaIndexer class with some modifications
class ChromaIndexer:
    def __init__(self, json_data=None, persist_dir="chroma_db"):
        self.json_data = json_data
        self.persist_dir = persist_dir
        self.embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        self.vectorstore = None
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=10,
            separators=["\n\n", "\n", " ", ""]
        )
        
        # Load existing vectorstore if it exists
        if os.path.exists(self.persist_dir):
            self.vectorstore = Chroma(
                persist_directory=self.persist_dir,
                embedding_function=self.embedding_model
            )

    def build_index_from_data(self, json_data=None):
        """Build index from JSON data variable"""
        if json_data is None:
            json_data = self.json_data
        
        if json_data is None:
            raise ValueError("❌ No JSON data provided. Pass json_data parameter or set it during initialization.")

        if not isinstance(json_data, list):
            raise ValueError("❌ JSON data must be a list of dictionaries.")

        all_documents = []
        for entry in json_data:
            content = entry.get("content", "")
            if not content.strip():
                continue

            document = Document(
                page_content=content,
                metadata={
                    "url": entry.get("URL", ""),
                    "site_type": entry.get("site_type", "unknown")
                }
            )
            all_documents.append(document)

        # Split using the new method
        doc_chunks = self.text_splitter.split_documents(all_documents)

        # Create new vectorstore from documents
        self.vectorstore = Chroma.from_documents(
            documents=doc_chunks,
            embedding=self.embedding_model,
            persist_directory=self.persist_dir
        )

        print(f"✅ Successfully pushed {len(doc_chunks)} chunks to ChromaDB.")

    def get_retriever(self, k=3):
        """Returns a retriever for the vectorstore"""
        if self.vectorstore is None:
            raise ValueError("Vectorstore not initialized. Run build_index_from_json() first.")
        return self.vectorstore.as_retriever(search_kwargs={"k": k})

    def search_with_score(self, query: str, k: int = 3):
        if self.vectorstore is None:
            return []
        results = self.vectorstore.similarity_search_with_score(query, k=k)
        return results

    def delete_index(self):
        if os.path.exists(self.persist_dir):
            shutil.rmtree(self.persist_dir)
            print(f"🗑️ Deleted ChromaDB directory: {self.persist_dir}")
        else:
            print(f"ℹ️ ChromaDB directory does not exist: {self.persist_dir}")

# Create retriever tool functions
def create_website_search_tool(chroma_indexer):
    """Creates a tool for searching website content"""
    def search_website(query: str) -> str:
        try:
            results = chroma_indexer.search_with_score(query, k=10)
            if not results:
                return "No relevant information found in the website database."
            
            formatted_results = []
            for doc, score in results:
                content = doc.page_content
                url = doc.metadata.get('url', 'Unknown URL')
                formatted_results.append(f"Source: {url}\nContent: {content}\nScore: {score:.4f}")
            
            return "\n\n---\n\n".join(formatted_results)
        except Exception as e:
            return f"Error searching website database: {str(e)}"
    
    return Tool(
        name="SearchWebsite",
        func=search_website,
        description="Search through crawled website content. Use this to find specific information from the analyzed website pages. Input should be a search query about the website content."
    )

def create_retrieval_qa_tool(chroma_indexer, llm):
    """Creates a RetrievalQA tool for more sophisticated Q&A"""
    def qa_search(query: str) -> str:
        try:
            retriever = chroma_indexer.get_retriever(k=10)
            qa_chain = RetrievalQA.from_chain_type(
                llm=llm,
                chain_type="stuff",
                retriever=retriever,
                return_source_documents=True
            )
            
            result = qa_chain({"query": query})
            answer = result["result"]
            sources = [doc.metadata.get('url', 'Unknown') for doc in result["source_documents"]]
            
            return f"Answer: {answer}\n\nSources: {', '.join(set(sources))}"
        except Exception as e:
            return f"Error in QA search: {str(e)}"
    
    return Tool(
        name="WebsiteQA",
        func=qa_search,
        description="Ask questions about the website content and get detailed answers with sources. Use this for complex questions that require reasoning over the website content."
    )
    
def create_build_index_tool(chroma_indexer):
    """Creates a tool for building index from JSON data"""
    def build_index_from_json(json_data_str: str) -> str:
        try:
            # Parse JSON string to list
            json_data = json.loads(json_data_str)
            
            if not isinstance(json_data, list):
                return "❌ Error: JSON data must be a list of dictionaries."
            
            # Build index from data
            chroma_indexer.build_index_from_data(json_data)
            
            return f"✅ Successfully built index from {len(json_data)} entries. Vector database is ready for searching."
            
        except json.JSONDecodeError as e:
            return f"❌ Error parsing JSON: {str(e)}"
        except Exception as e:
            return f"❌ Error building index: {str(e)}"
    
    return Tool(
        name="BuildIndex",
        func=build_index_from_json,
        description="Build vector database index from JSON data. Input should be a JSON string containing a list of dictionaries with 'URL', 'content', and 'site_type' fields. This tool processes the data and creates a searchable vector database."
    )

   