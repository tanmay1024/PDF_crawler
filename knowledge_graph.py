"""
This script creates a knowledge graph out of the extracted data.
"""

import os
import pandas as pd
import json

class KnowledgeGraph:
    def __init__(self, data_dir='data', model_name='gemini-2.5-pro'):
        self.data_dir = data_dir
        self.model_name = model_name


    def collect_data_files(self, data_dir):
        """
        Create a knowledge graph from the data in the specified directory.
        
        Args:
            data_dir (str): Directory containing the CSV file with extracted data.
        """

        universities = os.listdir(data_dir)
        knowledge_dict = {}
        for university in universities:
            uni_path = os.path.join(data_dir, university)
            programs = os.listdir(uni_path)
            knowledge_dict[university] = {}
            for program in programs:
                program_path = os.path.join(uni_path, program)
                if len(os.listdir(program_path)) != 0:
                    knowledge_dict[university][program] = [os.path.join(program_path, f) for f in os.listdir(program_path)]

        return knowledge_dict


    def create_knowledge_graph(knowledge_dict):
        """
        Create a knowledge graph from the data in the specified directory and save it to a JSON file.
        
        Args:
            data_dir (str): Directory containing the CSV file with extracted data.
            output_file (str): Path to the output JSON file.
        """
        knowledge_graph = collect_data_files(data_dir)
        with open(output_file, 'w') as f_out:
            json.dump(knowledge_graph, f_out, indent=4)