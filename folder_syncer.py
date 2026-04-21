import os
import shutil
from datetime import datetime

FOLDER_A = r"C:\Users\YourName\OneDrive\Folder"
FOLDER_B = r"D:\LocalServer\Folder"

LOG_FILE = "sync.log"
BACKUP_DIR = ".sync_backup"
TRASH_DIR = ".sync_trash"

def log(message):
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
line = f"[{timestamp}] {message}"
print(line)
with open(LOG_FILE, "a", encoding="utf-8") as f:
f.write(line + "\n")

def ensure_dir(path):
os.makedirs(path, exist_ok=True)

def backup_file(base, filepath):
rel = os.path.relpath(filepath, base)
backup_path = os.path.join(base, BACKUP_DIR, rel)
ensure_dir(os.path.dirname(backup_path))
shutil.copy2(filepath, backup_path)
log(f"BACKUP: {filepath} -> {backup_path}")

def move_to_trash(base, filepath):
rel = os.path.relpath(filepath, base)
trash_path = os.path.join(base, TRASH_DIR, rel)
ensure_dir(os.path.dirname(trash_path))
shutil.move(filepath, trash_path)
log(f"TRASH: {filepath} -> {trash_path}")

def get_files(base):
files = {}
for root, _, filenames in os.walk(base):
if BACKUP_DIR in root or TRASH_DIR in root:
continue
for f in filenames:
full = os.path.join(root, f)
rel = os.path.relpath(full, base)
stat = os.stat(full)
files[rel] = {
"path": full,
"mtime": stat.st_mtime,
"size": stat.st_size
}
return files

def copy_file(src, dst):
ensure_dir(os.path.dirname(dst))
shutil.copy2(src, dst)
log(f"COPY: {src} -> {dst}")

def sync():
files_a = get_files(FOLDER_A)
files_b = get_files(FOLDER_B)

```
all_keys = set(files_a) | set(files_b)

for key in all_keys:
    a = files_a.get(key)
    b = files_b.get(key)

    path_a = os.path.join(FOLDER_A, key)
    path_b = os.path.join(FOLDER_B, key)

    # Case 1: Exists only in A
    if a and not b:
        copy_file(path_a, path_b)

    # Case 2: Exists only in B
    elif b and not a:
        copy_file(path_b, path_a)

    # Case 3: Exists in both
    else:
        if a["size"] != b["size"] or abs(a["mtime"] - b["mtime"]) > 2:
            if a["mtime"] > b["mtime"]:
                backup_file(FOLDER_B, path_b)
                copy_file(path_a, path_b)
            else:
                backup_file(FOLDER_A, path_a)
                copy_file(path_b, path_a)

# Deletion sync
# If file existed before but now missing → move other side to trash
for key in files_a:
    if key not in files_b:
        path_b = os.path.join(FOLDER_B, key)
        if os.path.exists(path_b):
            move_to_trash(FOLDER_B, path_b)

for key in files_b:
    if key not in files_a:
        path_a = os.path.join(FOLDER_A, key)
        if os.path.exists(path_a):
            move_to_trash(FOLDER_A, path_a)
```

if **name** == "**main**":
log("==== SYNC START ====")
sync()
log("==== SYNC END ====")
