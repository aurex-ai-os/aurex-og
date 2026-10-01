import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading
import sys
import os

class AurexInstaller:
    def __init__(self, root):
        self.root = root
        self.root.title("Aurex Setup Wizard")
        self.root.geometry("600x400")
        self.root.configure(bg="#0D0D0F")
        
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TLabel", background="#0D0D0F", foreground="white", font=("Arial", 11))
        style.configure("TButton", font=("Arial", 10, "bold"), background="#50fa7b", foreground="black")
        
        # Header
        ttk.Label(root, text="Welcome to the Aurex Installer", font=("Arial", 16, "bold")).pack(pady=20)
        ttk.Label(root, text="This wizard will install all necessary dependencies for Aurex to run.").pack(pady=5)
        
        # Progress Log
        self.log_area = tk.Text(root, height=12, width=70, bg="#1E1E2E", fg="#A6ACCD", font=("Courier", 9))
        self.log_area.pack(pady=15)
        
        # Install Button
        self.install_btn = ttk.Button(root, text="Install Dependencies", command=self.start_install)
        self.install_btn.pack(pady=10)

    def log(self, message):
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.root.update_idletasks()

    def run_command(self, cmd):
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            self.log(line.strip())
        process.wait()
        return process.returncode

    def install_worker(self):
        self.install_btn.config(state="disabled")
        
        self.log("[1/4] Upgrading pip...")
        self.run_command(f"{sys.executable} -m pip install --upgrade pip")
        
        self.log("[2/4] Installing Python requirements...")
        self.run_command(f"{sys.executable} -m pip install -r requirements.txt")
        self.run_command(f"{sys.executable} -m pip install python-magic duckduckgo-search pdfminer.six chromadb pywebview")
        
        self.log("[3/4] Installing Node.js & Playwright MCP (NPM)...")
        # Attempt to run npm, if it fails, instruct user to install Node.js
        ret = self.run_command("npm install -g @playwright/mcp@latest")
        if ret != 0:
            self.log("WARNING: npm failed. Please install Node.js manually from nodejs.org")
            
        self.log("[4/4] Setup Complete!")
        messagebox.showinfo("Success", "Aurex dependencies have been installed successfully!\n\nYou can now run 'python app.py' to start the server.")
        self.install_btn.config(state="normal", text="Finished")

    def start_install(self):
        threading.Thread(target=self.install_worker, daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = AurexInstaller(root)
    root.mainloop()
