import csv

with open(r"C:\Users\dawar\Documents\MeezanBank_Internship\Projects\Proj6-Rag2\data\cleaning_report.csv") as f:
    reader = csv.DictReader(f)
    failed = [row["filename"] for row in reader if row["status"] == "start_marker_not_found"]

print(failed)