import os

# Define the structure
structure = {
    "data": [
        "raw_html",    # Stores the raw source
        "docs",        # Final processed text
        "logs"         # Error logs for debugging
    ],
    "src": [
        "crawlers",    # Crawlee logic
        "utils"        # Helpers for parsing/cleaning
    ]
}

def create_structure(base_path="."):
    for folder, subfolders in structure.items():
        # Create main directory
        main_path = os.path.join(base_path, folder)
        os.makedirs(main_path, exist_ok=True)
        print(f"Created directory: {main_path}")
        
        # Create subdirectories
        for sub in subfolders:
            sub_path = os.path.join(main_path, sub)
            os.makedirs(sub_path, exist_ok=True)
            # Create a placeholder .gitkeep to ensure folder is tracked in Git
            with open(os.path.join(sub_path, ".gitkeep"), "w") as f:
                f.write("")
            print(f"  Created subdirectory: {sub_path}")

if __name__ == "__main__":
    create_structure()