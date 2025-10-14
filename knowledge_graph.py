"""
This script creates a knowledge graph out of the extracted data.
"""

import os
import asyncio
import time
import json
import re
from dotenv import load_dotenv
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_neo4j import Neo4jGraph
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.document_loaders import UnstructuredFileLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from graph_schema import get_allowed_nodes, get_allowed_relationships, NODE_TYPES

load_dotenv()
NEO4J_URL = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

class KnowledgeGraph:
    def __init__(self, data_dir='Data', model_name='gemini-2.0-flash-exp', requests_per_minute=15,chunk_size=4000, chunk_overlap=200):
        self.data_dir = data_dir
        self.model_name = model_name
        self.requests_per_minute = requests_per_minute
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.graph = Neo4jGraph(
            url=NEO4J_URL, 
            username=NEO4J_USERNAME, 
            password=NEO4J_PASSWORD,
            enhanced_schema=False,
            refresh_schema=False
        )
        self.llm = ChatGoogleGenerativeAI(model=self.model_name, google_api_key=GEMINI_API_KEY, temperature=0)
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self._initialize_schema()

    def _initialize_schema(self):
        from graph_schema import generate_neo4j_constraints
        try:
            for constraint in generate_neo4j_constraints():
                try:
                    self.graph.query(constraint)
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        print(f"Warning: {e}")
        except Exception as e:
            print(f"Schema initialization skipped: {e}")

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
                if os.path.isdir(program_path) and len(os.listdir(program_path)) > 0:
                    knowledge_dict[university][program] = [os.path.join(program_path, f) for f in os.listdir(program_path) if not f.startswith('.')]
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
                            doc.metadata['source_file'] = file_path
                        documents.extend(loaded_docs)
                    except Exception as e:
                        print(f"Error loading file {file_path}: {e}")
        return documents

    def chunk_documents(self, documents):
        chunked_docs = []
        for doc in documents:
            chunks = self.text_splitter.split_documents([doc])
            chunked_docs.extend(chunks)
        return chunked_docs

    def normalize_data(self, graph_docs):
        for graph_doc in graph_docs:
            for node in graph_doc.nodes:
                if 'gpa_min' in node.properties:
                    node.properties['gpa_min'] = self._normalize_gpa(node.properties['gpa_min'])
                if 'date' in node.properties:
                    node.properties['date'] = self._normalize_date(node.properties['date'])
                if 'tuition' in node.properties:
                    node.properties['tuition'] = self._normalize_currency(node.properties['tuition'])
        return graph_docs

    def _normalize_gpa(self, gpa_value):
        if isinstance(gpa_value, (int, float)):
            return float(gpa_value)
        if isinstance(gpa_value, str):
            match = re.search(r'(\d+\.?\d*)', gpa_value)
            return float(match.group(1)) if match else None
        return None

    def _normalize_date(self, date_value):
        return str(date_value).strip() if date_value else None

    def _normalize_currency(self, currency_value):
        if isinstance(currency_value, str):
            match = re.search(r'[\d,]+', currency_value.replace('$', '').replace(',', ''))
            return int(match.group(0)) if match else None
        return currency_value

    def create_knowledge_graph(self, documents, batch_size=10):
        self.min_delay = 60.0 / self.requests_per_minute
        allowed_nodes = get_allowed_nodes()
        allowed_relationships = get_allowed_relationships()
        
        llm_graph_transformer = LLMGraphTransformer(
            llm=self.llm,
            allowed_nodes=allowed_nodes,
            allowed_relationships=allowed_relationships,
            node_properties=NODE_TYPES,
            relationship_properties=True,
            strict_mode=False
        )

        for i in range(0, len(documents), batch_size):
            batch = documents[i:i+batch_size]
            batch_num = i//batch_size + 1
            total_batches = (len(documents)-1)//batch_size + 1
            print(f"Processing batch {batch_num}/{total_batches}")
            
            start_time = time.time()
            graph_docs = asyncio.run(llm_graph_transformer.aconvert_to_graph_documents(batch))
            graph_docs = self.normalize_data(graph_docs)
            
            for graph_doc in graph_docs:
                for node in graph_doc.nodes:
                    node_label = node.type
                    node_props = {k: v for k, v in node.properties.items() if v is not None}
                    self.graph.query(
                        f"MERGE (n:{node_label} {{id: $id}}) SET n += $props",
                        {"id": node.id, "props": node_props}
                    )
                
                for rel in graph_doc.relationships:
                    self.graph.query(
                        f"""MATCH (a:{rel.source.type} {{id: $source_id}})
                            MATCH (b:{rel.target.type} {{id: $target_id}})
                            MERGE (a)-[r:{rel.type}]->(b)""",
                        {"source_id": rel.source.id, "target_id": rel.target.id}
                    )
            
            elapsed = time.time() - start_time
            if batch_num < total_batches:
                delay = max(0, self.min_delay - elapsed)
                if delay > 0:
                    print(f"Rate limiting: waiting {delay:.1f}s")
                    time.sleep(delay)

    def run(self):
        knowledge_dict = self.collect_data_files(self.data_dir)
        print(f"Found {sum(len(progs) for progs in knowledge_dict.values())} programs")
        
        documents = self.create_documents(knowledge_dict)
        print(f"Loaded {len(documents)} documents")
        
        chunked_docs = self.chunk_documents(documents)
        print(f"Created {len(chunked_docs)} chunks")
        
        self.create_knowledge_graph(chunked_docs)
        print("Knowledge graph created successfully")

if __name__ == "__main__":
    kg = KnowledgeGraph(data_dir='Data2', model_name='gemini-2.0-flash', requests_per_minute=20)
    kg.run()


