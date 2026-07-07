import os

# Use raw string (r'') to avoid backslash issues
docs_dir = r'C:\Users\dawar\Documents\MeezanBank_Internship\Projects\Proj6-Rag2\data\docs'
MIN_SIZE = 500 

# 1. Collect a list of files to remove first
files_to_remove = []

for filename in os.listdir(docs_dir):
    filepath = os.path.join(docs_dir, filename)
    
    # Skip if it is not a file (like a sub-directory)
    if not os.path.isfile(filepath):
        continue
        
    if os.path.getsize(filepath) < MIN_SIZE:
        files_to_remove.append(filepath)
    else:
        # Check if it's a binary file
        with open(filepath, 'rb') as f:
            header = f.read(4)
            if header.startswith(b'%PDF') or header.startswith(b'\x50\x4B\x03\x04'):
                files_to_remove.append(filepath)

# 2. Perform the deletion outside the loop
for filepath in files_to_remove:
    print(f"Removing: {os.path.basename(filepath)}")
    os.remove(filepath)

print("Cleanup complete.")