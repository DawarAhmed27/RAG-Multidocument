import os
import shutil

# Correct path using absolute location
BASE_DIR = r"C:\Users\dawar\Documents\MeezanBank_Internship\Projects\Proj6-Rag2"
DOCS_DIR = os.path.join(BASE_DIR, "data", "docs")

def clean_up():
    print(f"Cleaning directory: {DOCS_DIR}")
    
    for filename in os.listdir(DOCS_DIR):
        filepath = os.path.join(DOCS_DIR, filename)
        
        # 1. DELETE JUNK (Binaries and Server files)
        if filename.endswith(('.pdf', '.zip', '.xlsx', '.php', '.csv')):
            print(f"Deleting binary/server file: {filename}")
            os.remove(filepath)
            continue
            
        # 2. RENAME FILES WITHOUT EXTENSION
        # If the file has no dot in the name, rename it to .txt
        if '.' not in filename:
            new_filename = filename + ".txt"
            print(f"Renaming {filename} -> {new_filename}")
            os.rename(filepath, os.path.join(DOCS_DIR, new_filename))

if __name__ == "__main__":
    clean_up()