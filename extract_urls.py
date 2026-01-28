import sys

try:
    with open("urls.json", "r") as f:
        lines = f.readlines()
        
    for line in lines:
        line = line.strip()
        # Remove PSQL line ending "+"
        if line.endswith("+"):
            line = line[:-1]
            
        # Look for lines that contain a URL in quotes
        start = line.find('"http')
        if start != -1:
            end = line.rfind('"')
            if end > start:
                url = line[start+1:end]
                print(url)

except Exception as e:
    sys.stderr.write(str(e))
    sys.exit(1)
