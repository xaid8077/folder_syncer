import os
import shutil
import json
import hashlib
import threading
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, scrolledtext

# ---------------- CONFIG ---------------- #
CONFIG = {
    "folder_a": r"\\lntsonas\WSD\WSD INST\129. South East Guwahati (LE26M183)",
    "folder_b": r"D:\OneDrive - L&T Construction\9. South East Guwahati",
    "log_file": "sync.log",
    "state_file": "sync_state.json",
    "backup_dir": ".sync_backup",
    "trash_dir": ".sync_trash",
    "dry_run": False
}

# ---------------- LOGGING ---------------- #
def log(msg, level="INFO", gui=None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [{level}] {msg}"
    print(line)

    with open(CONFIG["log_file"], "a", encoding="utf-8") as f:
        f.write(line + "\n")

    if gui:
        gui.log(line)

# ---------------- HASH ---------------- #
def compute_hash(filepath, chunk_size=65536):
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()

def ensure_hash(file_dict, base_path, rel_path):
    if file_dict["hash"] is None:
        full_path = os.path.join(base_path, rel_path)
        file_dict["hash"] = compute_hash(full_path)
    return file_dict["hash"]

# ---------------- UTIL ---------------- #
def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def safe_copy(src, dst, gui=None):
    if CONFIG["dry_run"]:
        log(f"[DRY RUN] COPY: {src} -> {dst}", gui=gui)
        return

    ensure_dir(os.path.dirname(dst))
    tmp = dst + ".tmp"
    shutil.copy2(src, tmp)
    os.replace(tmp, dst)
    log(f"COPY: {src} -> {dst}", gui=gui)

def backup_file(base, filepath, gui=None):
    if not os.path.exists(filepath):
        return

    rel = os.path.relpath(filepath, base)
    backup_path = os.path.join(base, CONFIG["backup_dir"], rel)

    if CONFIG["dry_run"]:
        log(f"[DRY RUN] BACKUP: {filepath}", gui=gui)
        return

    ensure_dir(os.path.dirname(backup_path))
    shutil.copy2(filepath, backup_path)
    log(f"BACKUP: {filepath}", gui=gui)

def move_to_trash(base, filepath, gui=None):
    if not os.path.exists(filepath):
        return

    rel = os.path.relpath(filepath, base)
    trash_path = os.path.join(base, CONFIG["trash_dir"], rel)

    if CONFIG["dry_run"]:
        log(f"[DRY RUN] TRASH: {filepath}", gui=gui)
        return

    ensure_dir(os.path.dirname(trash_path))
    shutil.move(filepath, trash_path)
    log(f"TRASH: {filepath}", gui=gui)

# ---------------- SCAN ---------------- #
def get_files(base):
    files = {}
    for root, _, filenames in os.walk(base):
        if CONFIG["backup_dir"] in root or CONFIG["trash_dir"] in root:
            continue

        for f in filenames:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, base)
            stat = os.stat(full)

            files[rel] = {
                "mtime": stat.st_mtime,
                "size": stat.st_size,
                "hash": None
            }
    return files

# ---------------- STATE ---------------- #
def load_state():
    if not os.path.exists(CONFIG["state_file"]):
        return {}
    with open(CONFIG["state_file"], "r") as f:
        return json.load(f)

def save_state(state):
    with open(CONFIG["state_file"], "w") as f:
        json.dump(state, f, indent=2)

# ---------------- SYNC ---------------- #
def sync(gui=None):
    state = load_state()

    files_a = get_files(CONFIG["folder_a"])
    files_b = get_files(CONFIG["folder_b"])

    all_keys = set(files_a) | set(files_b)

    for key in all_keys:
        a = files_a.get(key)
        b = files_b.get(key)

        path_a = os.path.join(CONFIG["folder_a"], key)
        path_b = os.path.join(CONFIG["folder_b"], key)

        # Only in A
        if a and not b:
            safe_copy(path_a, path_b, gui)

        # Only in B
        elif b and not a:
            safe_copy(path_b, path_a, gui)

        # Both exist
        elif a and b:
            if a["size"] != b["size"] or abs(a["mtime"] - b["mtime"]) > 2:

                hash_a = ensure_hash(a, CONFIG["folder_a"], key)
                hash_b = ensure_hash(b, CONFIG["folder_b"], key)

                if hash_a == hash_b:
                    continue

                # Conflict detection
                if key in state:
                    old = state[key]
                    if old.get("hash") not in (hash_a, hash_b):
                        log(f"CONFLICT: {key}", "WARNING", gui)
                        conflict_copy = path_a + ".conflict"
                        safe_copy(path_b, conflict_copy, gui)
                        continue

                # Normal update
                if a["mtime"] > b["mtime"]:
                    backup_file(CONFIG["folder_b"], path_b, gui)
                    safe_copy(path_a, path_b, gui)
                else:
                    backup_file(CONFIG["folder_a"], path_a, gui)
                    safe_copy(path_b, path_a, gui)

    # Safe deletion
    for key in state:
        if key not in files_a and key in files_b:
            move_to_trash(CONFIG["folder_b"], os.path.join(CONFIG["folder_b"], key), gui)

        if key not in files_b and key in files_a:
            move_to_trash(CONFIG["folder_a"], os.path.join(CONFIG["folder_a"], key), gui)

    # Save state (with hashes)
    new_state = {}
    for key in set(files_a) | set(files_b):
        file_info = files_a.get(key) or files_b.get(key)
        if file_info:
            if file_info["hash"] is None:
                base = CONFIG["folder_a"] if key in files_a else CONFIG["folder_b"]
                file_info["hash"] = compute_hash(os.path.join(base, key))
            new_state[key] = file_info

    save_state(new_state)

# ---------------- GUI ---------------- #
class SyncGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Folder Sync Tool")
        self.root.geometry("750x550")

        self.folder_a = tk.StringVar()
        self.folder_b = tk.StringVar()
        self.dry_run = tk.BooleanVar()

        tk.Label(root, text="Folder A").pack()
        tk.Entry(root, textvariable=self.folder_a, width=90).pack()
        tk.Button(root, text="Browse", command=self.pick_a).pack()

        tk.Label(root, text="Folder B").pack()
        tk.Entry(root, textvariable=self.folder_b, width=90).pack()
        tk.Button(root, text="Browse", command=self.pick_b).pack()

        tk.Checkbutton(root, text="Dry Run", variable=self.dry_run).pack()

        tk.Button(root, text="Start Sync", command=self.run_sync).pack(pady=10)

        self.log_box = scrolledtext.ScrolledText(root, height=20)
        self.log_box.pack(fill="both", expand=True)

    def pick_a(self):
        self.folder_a.set(filedialog.askdirectory())

    def pick_b(self):
        self.folder_b.set(filedialog.askdirectory())

    def log(self, msg):
        self.log_box.insert(tk.END, msg + "\n")
        self.log_box.see(tk.END)

    def run_sync(self):
        CONFIG["folder_a"] = self.folder_a.get()
        CONFIG["folder_b"] = self.folder_b.get()
        CONFIG["dry_run"] = self.dry_run.get()

        thread = threading.Thread(target=self.safe_sync)
        thread.start()

    def safe_sync(self):
        self.log("==== SYNC START ====")
        try:
            sync(self)
            self.log("SYNC COMPLETED")
        except Exception as e:
            self.log(f"ERROR: {e}")
        self.log("==== SYNC END ====")

# ---------------- MAIN ---------------- #
if __name__ == "__main__":
    import sys

    if "--auto" in sys.argv:
        log("==== AUTO SYNC START ====")
        try:
            sync()
            log("AUTO SYNC COMPLETED")
        except Exception as e:
            log(f"ERROR: {e}", "ERROR")
        log("==== AUTO SYNC END ====")
    else:
        root = tk.Tk()
        app = SyncGUI(root)
        root.mainloop()