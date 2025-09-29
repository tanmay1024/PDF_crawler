"""
This script creates a knowledge graph out of the extracted data.
"""

import os
import asyncio
from dotenv import load_dotenv
import pandas as pd
import json
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_neo4j import Neo4jGraph
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.document_loaders import UnstructuredFileLoader

load_dotenv()
NEO4J_URL = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

class KnowledgeGraph:
    def __init__(self, data_dir='Data', model_name='gemini-2.5-pro'):
        self.data_dir = data_dir
        self.model_name = model_name
        self.graph = Neo4jGraph(
            url=NEO4J_URL,
            username=NEO4J_USERNAME,
            password=NEO4J_PASSWORD,
            refresh_schema=False
        )
        self.llm = ChatGoogleGenerativeAI(
            model=self.model_name, google_api_key=GEMINI_API_KEY
        )

    def collect_data_files(self, data_dir):
        """
        Create a dictionary that organises data file locations by university and program.
        
        Args:
            data_dir (str): Directory containing the CSV file with extracted data.
        """
        def safe_remove(list_dir):
            return [f for f in list_dir if not f.startswith('.')]
        
        universities = safe_remove(os.listdir(data_dir))
        knowledge_dict = {}
        for university in universities:
            uni_path = os.path.join(data_dir, university)
            programs = safe_remove(os.listdir(uni_path))
            knowledge_dict[university] = {}
            for program in programs:
                program_path = os.path.join(uni_path, program)
                if len(os.listdir(program_path)) != 0:
                    knowledge_dict[university][program] = [os.path.join(program_path, f) for f in os.listdir(program_path)]

        return knowledge_dict

    def create_documents(self, knowledge_dict):
        """
        Create langchain_core.documents.Document objects from the knowledge dictionary.
        
        Args:
            knowledge_dict (dict): Dictionary with structure {university: {program: [file_paths]}}
        """
        documents = []
        for university, programs in knowledge_dict.items():
            for program, file_paths in programs.items():
                for file_path in file_paths:
                    try:
                        loader = UnstructuredFileLoader(file_path)
                        loaded_docs = loader.load()                        
                        for doc in loaded_docs:
                            doc.metadata['university'] = university
                            doc.metadata['program'] = program
                        documents.extend(loaded_docs)
                    except Exception as e:
                        print(f"Error loading file {file_path}: {e}")
        return documents

    def create_knowledge_graph(self, documents):
        """
        Create a knowledge graph from a dictionary that has organised data file locations
        
        Args:
            knowledge_dict (dict): Dictionary with structure {university: {program: [file_paths]}}
        """
        allowed_nodes = ["University", "Program", "Course"]
        llm_graph_transformer = LLMGraphTransformer(llm=self.llm, allowed_nodes=allowed_nodes, strict_mode=False)
        data = asyncio.run(llm_graph_transformer.aconvert_to_graph_documents(documents))
        self.graph.add_graph_documents(data)

    
    def run(self):
        knowledge_dict = self.collect_data_files(self.data_dir)
        print("Collected data files:", json.dumps(knowledge_dict, indent=2))
        documents = self.create_documents(knowledge_dict)
        print(f"Created {len(documents)} documents.")
        self.create_knowledge_graph(documents)
        print("Knowledge graph creation process finished.")


if __name__ == "__main__":
    kg = KnowledgeGraph(data_dir='Data', model_name='gemini-2.5-flash')
    kg.run()

