import os

files = os.listdir(r"C:\Users\dawar\Documents\MeezanBank_Internship\Projects\Proj6-Rag2\data\docs_clean")
sizes = [os.path.getsize(os.path.join(r"C:\Users\dawar\Documents\MeezanBank_Internship\Projects\Proj6-Rag2\data\docs_clean", f)) for f in files]
print(f"Count: {len(sizes)}")
print(f"Min: {min(sizes)}, Max: {max(sizes)}, Avg: {sum(sizes)/len(sizes):.0f} bytes")