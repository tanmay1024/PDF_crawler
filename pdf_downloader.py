import os
import requests
import pandas as pd

def main():
    df = pd.read_csv('output.csv')
    current_dir = os.getcwd()
    for idx, row in df.iterrows():
        pdf_url = row['URL']
        university = row['University'].strip()
        program = row['Program'].strip()
        file_name = pdf_url.split("/")[-1]
        path = os.path.join(current_dir, university, program)
        if not os.path.exists(path):
            os.makedirs(path)
        file_name = os.path.join(path, file_name)
        os.chdir(path)
        try:
            os.system(f"curl -O {pdf_url}")
        except:
            os.system(f"wget '{pdf_url}' ")
            
        # with open(file_name, "wb") as f_out:
        #     print("Downloading", pdf_url)
        #     f_out.write(requests.get(pdf_url).content)

if __name__ == "__main__":
    main()