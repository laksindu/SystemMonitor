import tkinter as tk
from tkinter import ttk, scrolledtext
import subprocess
import os
import threading
import time
import sys
import webbrowser
import socket


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

class ServerManager:
    def __init__(self, output_widget, status_widget, ip_widget):
        self.server_process = None
        self.output_widget = output_widget
        self.status_widget = status_widget
        self.ip_widget = ip_widget
        self.ip_address = get_local_ip()
        self.port = 5000
        
    def start_server(self):
        if self.server_process is None:
            self.server_process = subprocess.Popen(
                [sys.executable, 'app.py'],# Ensure 'app.py' is in the same directory
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            self.log_message(f"Server started at http://{self.ip_address}:{self.port}")
            self.update_status("Running", "green")
        else:
            self.log_message("Server is already running.")

    def stop_server(self):
        if self.server_process:
            self.server_process.terminate()
            self.server_process = None
            self.log_message("Server stopped.")
            self.update_status("Stopped", "red")
        else:
            self.log_message("Server is not running.")
    
    def is_running(self):
        return self.server_process and self.server_process.poll() is None

    def log_message(self, message):
        self.output_widget.config(state=tk.NORMAL)
        self.output_widget.insert(tk.END, f"{message}\n")
        self.output_widget.see(tk.END)
        self.output_widget.config(state=tk.DISABLED)

    def update_status(self, status, color):
        self.status_widget.config(text=status, foreground=color)

def main():
    root = tk.Tk()
    root.title("Backend Manager")
    root.geometry("500x400")
    

    main_frame = ttk.Frame(root, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    title_label = ttk.Label(main_frame, text="System Monitor Backend Manager", font=("Helvetica", 16, "bold"))
    title_label.pack(pady=(0, 10))

    status_frame = ttk.Frame(main_frame)
    status_frame.pack(fill=tk.X, pady=(0, 5))
    ttk.Label(status_frame, text="Status:").pack(side=tk.LEFT, padx=(0, 5))
    status_label = ttk.Label(status_frame, text="Stopped", foreground="red")
    status_label.pack(side=tk.LEFT)

    ip_frame = ttk.Frame(main_frame)
    ip_frame.pack(fill=tk.X, pady=(0, 5))
    ttk.Label(ip_frame, text="Server URL:").pack(side=tk.LEFT, padx=(0, 5))
    ip_label = ttk.Label(ip_frame, text=f"http://{get_local_ip()}:5000", foreground="blue")
    ip_label.pack(side=tk.LEFT)
    
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=10)
    
    output_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, height=10, state=tk.DISABLED)
    output_text.pack(fill=tk.BOTH, expand=True)
    
 
    manager = ServerManager(output_text, status_label, ip_label)

    start_button = ttk.Button(button_frame, text="Start Server", command=manager.start_server)
    start_button.pack(side=tk.LEFT, padx=5)

    stop_button = ttk.Button(button_frame, text="Stop Server", command=manager.stop_server)
    stop_button.pack(side=tk.LEFT, padx=5)
    
    docs_button = ttk.Button(button_frame, text="Open Documentation", command=lambda: webbrowser.open("http://your-documentation-url-here.com"))
    docs_button.pack(side=tk.LEFT, padx=5)
    
    exit_button = ttk.Button(button_frame, text="Exit", command=root.quit)
    exit_button.pack(side=tk.LEFT, padx=5)

 
    def check_status_thread():
        while True:
            is_running = manager.is_running()
            if is_running:
                manager.update_status("Running", "green")
            else:
                manager.update_status("Stopped", "red")
            time.sleep(1)
            
    threading.Thread(target=check_status_thread, daemon=True).start()
    
    root.protocol("WM_DELETE_WINDOW", lambda: [manager.stop_server(), root.destroy()])
    
    root.mainloop()

if __name__ == "__main__":
    main()