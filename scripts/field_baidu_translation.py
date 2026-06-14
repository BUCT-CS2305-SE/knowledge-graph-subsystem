
from pathlib import Path
import sys

sys.path.insert(0, "data_processing/cleaning")
from baidu_translator import translate_csv_file

fields = [
    "title", "period", "type", "material",
    "description", "credit_line",
    "museum", "location",
    "aligned_museum", "aligned_period", "aligned_type", "aligned_material",
]

for p in sorted(Path("data_processing/alignment/by_dataset").glob("clean_*.csv")):
    print(f"\n=== translating {p} ===")
    translate_csv_file(str(p), str(p), fields=fields, delay=1.2)