import os
import subprocess
import glob
from tqdm import tqdm
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import threading
import queue

def compress_video(input_file, output_file, target_size_mb=7, progress_queue=None, ffmpeg_path='ffmpeg'):
    """
    Compress a video file to target size in MB using FFmpeg
    """
    # Get original file size in bytes
    original_size = os.path.getsize(input_file)
    original_size_mb = original_size / (1024 * 1024)
    
    # Calculate target bitrate (kbps) based on the target size
    # We'll use a simple formula: (target_size_in_bytes * 8) / duration_in_seconds
    # First, get the video duration using ffprobe
    ffprobe_path = 'ffprobe'
    if ffmpeg_path != 'ffmpeg':
        # ffmpeg_path bir özel yolsa, ffprobe'un da özel yolunu belirle
        ffprobe_path = os.path.join(os.path.dirname(ffmpeg_path), 'ffprobe.exe')
    
    duration_cmd = [
        ffprobe_path, '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', input_file
    ]
    
    try:
        duration = float(subprocess.check_output(duration_cmd).decode('utf-8').strip())
    except:
        if progress_queue:
            progress_queue.put(f"Error getting duration for {input_file}")
        return False
    
    # Calculate target bitrate (in kilobits per second)
    target_size_bytes = target_size_mb * 1024 * 1024
    target_bitrate = int((target_size_bytes * 8) / duration / 1000)
    
    # Subtract audio bitrate (assume 128k for audio)
    video_bitrate = max(target_bitrate - 128, 64)  # ensure minimum video bitrate
    
    if progress_queue:
        progress_queue.put(f"Compressing {os.path.basename(input_file)} ({original_size_mb:.2f} MB) to target {target_size_mb} MB")
    
    # Compress the video using ffmpeg
    compress_cmd = [
        ffmpeg_path, '-i', input_file, 
        '-c:v', 'libx264', '-preset', 'slow', '-b:v', f'{video_bitrate}k',
        '-c:a', 'aac', '-b:a', '128k',
        '-y', output_file
    ]
    
    try:
        subprocess.run(compress_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        new_size = os.path.getsize(output_file) / (1024 * 1024)
        if progress_queue:
            progress_queue.put(f"Completed: {os.path.basename(input_file)} - New size: {new_size:.2f} MB")
        return True
    except subprocess.CalledProcessError as e:
        if progress_queue:
            progress_queue.put(f"Error compressing {input_file}: {e}")
        return False

class VideoCompressorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Compressor")
        self.root.geometry("700x500")
        self.root.resizable(True, True)
        
        # Set up styles
        self.style = ttk.Style()
        self.style.configure("TButton", padding=6, relief="flat", font=('Arial', 10))
        self.style.configure("TLabel", font=('Arial', 10))
        self.style.configure("Header.TLabel", font=('Arial', 12, 'bold'))
        
        # Variables
        self.video_files = []
        self.target_size = tk.StringVar(value="7")
        self.output_dir = tk.StringVar()
        self.progress_queue = queue.Queue()
        self.ffmpeg_path = None
        
        # Create main frame
        main_frame = ttk.Frame(root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Video Compressor", style="Header.TLabel")
        title_label.pack(pady=(0, 20))
        
        # Target size frame
        size_frame = ttk.Frame(main_frame)
        size_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(size_frame, text="Target Size (MB):").pack(side=tk.LEFT, padx=(0, 10))
        size_entry = ttk.Entry(size_frame, textvariable=self.target_size, width=10)
        size_entry.pack(side=tk.LEFT)
        
        # Video selection frame
        select_frame = ttk.Frame(main_frame)
        select_frame.pack(fill=tk.X, pady=10)
        
        self.add_button = ttk.Button(select_frame, text="Add Videos", command=self.add_videos)
        self.add_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.clear_button = ttk.Button(select_frame, text="Clear List", command=self.clear_videos)
        self.clear_button.pack(side=tk.LEFT)
        
        # Output directory frame
        output_frame = ttk.Frame(main_frame)
        output_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(output_frame, text="Output Directory:").pack(side=tk.LEFT, padx=(0, 10))
        output_entry = ttk.Entry(output_frame, textvariable=self.output_dir, width=40)
        output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        self.browse_button = ttk.Button(output_frame, text="Browse", command=self.browse_output)
        self.browse_button.pack(side=tk.LEFT)
        
        # Video list frame
        list_frame = ttk.LabelFrame(main_frame, text="Selected Videos")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Listbox for videos
        self.video_listbox = tk.Listbox(list_frame, selectmode=tk.EXTENDED, height=10)
        self.video_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Configure scrollbar
        self.video_listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.video_listbox.yview)
        
        # Progress frame
        progress_frame = ttk.LabelFrame(main_frame, text="Progress")
        progress_frame.pack(fill=tk.X, pady=10)

        # Current operation label
        self.operation_var = tk.StringVar(value="Ready")
        operation_label = ttk.Label(progress_frame, textvariable=self.operation_var, font=('Arial', 9))
        operation_label.pack(anchor=tk.W, pady=(5, 0), padx=5)

        # Progress bar
        self.progress_bar = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL, mode='determinate')
        self.progress_bar.pack(fill=tk.X, pady=5, padx=5)

        # Status label with percentages
        self.progress_percent = tk.StringVar(value="0%")
        percent_label = ttk.Label(progress_frame, textvariable=self.progress_percent)
        percent_label.pack(anchor=tk.E, padx=5)

        # Status label
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(progress_frame, textvariable=self.status_var)
        status_label.pack(anchor=tk.W, pady=(0, 5), padx=5)
        
        # Log frame
        log_frame = ttk.LabelFrame(main_frame, text="Log")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Log scrollbar
        log_scrollbar = ttk.Scrollbar(log_frame)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Log text
        self.log_text = tk.Text(log_frame, height=6, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Configure log scrollbar
        self.log_text.config(yscrollcommand=log_scrollbar.set)
        log_scrollbar.config(command=self.log_text.yview)
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        # Add a "Remove Selected" button
        self.remove_button = ttk.Button(button_frame, text="Remove Selected", command=self.remove_selected_videos)
        self.remove_button.pack(side=tk.LEFT)

        # Add spacer
        spacer = ttk.Frame(button_frame)
        spacer.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Add Start button with a different style
        self.style.configure("Start.TButton", font=('Arial', 11, 'bold'), padding=8)
        self.compress_button = ttk.Button(
            button_frame, 
            text="Start Compression", 
            command=self.start_compression,
            style="Start.TButton"
        )
        self.compress_button.pack(side=tk.RIGHT)

        # Initially disable the start button until videos are selected
        self.compress_button.config(state=tk.DISABLED)
        
        # Check if ffmpeg is installed
        self.check_ffmpeg()
        
        # Start polling the queue
        self.root.after(100, self.process_queue)
    
    def check_ffmpeg(self):
        try:
            # Önce PATH'de FFmpeg'i kontrol et
            subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.ffmpeg_path = 'ffmpeg'
        except FileNotFoundError:
            # PATH'de yoksa, uygulama klasöründe kontrol et
            app_dir = os.path.dirname(os.path.abspath(__file__))
            ffmpeg_binary = os.path.join(app_dir, 'ffmpeg', 'bin', 'ffmpeg.exe')
            ffprobe_binary = os.path.join(app_dir, 'ffmpeg', 'bin', 'ffprobe.exe')
            
            if os.path.exists(ffmpeg_binary) and os.path.exists(ffprobe_binary):
                self.ffmpeg_path = ffmpeg_binary
            else:
                # FFmpeg bulunamadı - uzak bir FFmpeg indirme seçeneği sunun
                response = messagebox.askyesno(
                    "FFmpeg Not Found", 
                    "FFmpeg is required but not found on your system.\n"
                    "Would you like to download and install FFmpeg automatically?"
                )
                
                if response:
                    self.status_var.set("Downloading FFmpeg...")
                    threading.Thread(target=self.download_ffmpeg, daemon=True).start()
                else:
                    messagebox.showerror(
                        "Error", 
                        "FFmpeg is required for this application to work.\n"
                        "Please install FFmpeg manually and restart the application."
                    )
                    self.compress_button.config(state=tk.DISABLED)

    def download_ffmpeg(self):
        try:
            import requests
            from io import BytesIO
            import zipfile
            
            # FFmpeg'i indir (daha küçük bir derleme - yaklaşık 40MB)
            url = "https://github.com/GyanD/codexffmpeg/releases/download/2023-06-21-git-1bcb8a7338/ffmpeg-2023-06-21-git-1bcb8a7338-essentials_build.zip"
            
            self.log_text.insert(tk.END, "Downloading FFmpeg... This may take a few minutes.\n")
            self.log_text.see(tk.END)
            
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            # Veriyi bellekte bir buffer'a aktar
            buffer = BytesIO()
            total_size = int(response.headers.get('content-length', 0))
            
            # İndirme ilerlemesini göster
            downloaded = 0
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    buffer.write(chunk)
                    downloaded += len(chunk)
                    # İlerleme çubuğunu güncelle
                    progress = (downloaded / total_size) * 100 if total_size > 0 else 0
                    self.progress_queue.put({"progress": progress})
                    self.status_var.set(f"Downloading FFmpeg: {progress:.1f}%")
                    
            buffer.seek(0)
            
            # Çıkartılacak klasörü hazırla
            app_dir = os.path.dirname(os.path.abspath(__file__))
            ffmpeg_dir = os.path.join(app_dir, 'ffmpeg')
            os.makedirs(ffmpeg_dir, exist_ok=True)
            
            self.log_text.insert(tk.END, "Extracting FFmpeg...\n")
            self.log_text.see(tk.END)
            
            with zipfile.ZipFile(buffer) as zip_ref:
                zip_ref.extractall(ffmpeg_dir)
            
            # FFmpeg yapısını düzenle (genellikle bir alt klasördedir)
            extracted_dir = None
            for item in os.listdir(ffmpeg_dir):
                if os.path.isdir(os.path.join(ffmpeg_dir, item)) and 'ffmpeg' in item.lower():
                    extracted_dir = os.path.join(ffmpeg_dir, item)
                    break
            
            if extracted_dir:
                # FFmpeg dosyalarını doğru konuma taşı
                import shutil
                for item in os.listdir(extracted_dir):
                    shutil.move(
                        os.path.join(extracted_dir, item),
                        os.path.join(ffmpeg_dir, item)
                    )
                # Geçici klasörü temizle
                shutil.rmtree(extracted_dir)
            
            # FFmpeg yollarını ayarla
            self.ffmpeg_path = os.path.join(ffmpeg_dir, 'bin', 'ffmpeg.exe')
            
            # Kontrol et
            if os.path.exists(self.ffmpeg_path):
                self.log_text.insert(tk.END, "FFmpeg downloaded and installed successfully!\n")
                self.log_text.see(tk.END)
                self.status_var.set("Ready")
                self.progress_bar["value"] = 0
                self.compress_button.config(state=tk.NORMAL)
            else:
                raise Exception("FFmpeg installation failed")
                
        except Exception as e:
            self.log_text.insert(tk.END, f"Error downloading FFmpeg: {str(e)}\n")
            self.log_text.see(tk.END)
            self.status_var.set("FFmpeg download failed")
            messagebox.showerror(
                "Error", 
                f"Failed to download FFmpeg: {str(e)}\n"
                "Please install FFmpeg manually and restart the application."
            )

    def add_videos(self):
        filetypes = (
            ('Video files', '*.mp4 *.avi *.mov *.mkv *.wmv'),
            ('All files', '*.*')
        )
        files = filedialog.askopenfilenames(
            title='Select videos',
            filetypes=filetypes
        )
        
        if files:
            for file in files:
                if file not in self.video_files:
                    self.video_files.append(file)
                    filename = os.path.basename(file)
                    file_size = os.path.getsize(file) / (1024 * 1024)
                    self.video_listbox.insert(tk.END, f"{filename} ({file_size:.2f} MB)")
            
            # Set default output directory to the parent directory of the first selected file
            if not self.output_dir.get() and self.video_files:
                default_output = os.path.dirname(self.video_files[0])
                self.output_dir.set(os.path.join(default_output, "compressed"))
            
            # Enable the start button when videos are added
            if self.video_files:
                self.compress_button.config(state=tk.NORMAL)
    
    def clear_videos(self):
        self.video_files = []
        self.video_listbox.delete(0, tk.END)
        # Disable start button when videos are cleared
        self.compress_button.config(state=tk.DISABLED)
    
    def remove_selected_videos(self):
        """Remove selected videos from the list"""
        selected_indices = self.video_listbox.curselection()
        if not selected_indices:
            return
        
        # Remove in reverse order to maintain correct indices
        for index in sorted(selected_indices, reverse=True):
            del self.video_files[index]
            self.video_listbox.delete(index)
        
        # Update the start button state
        if not self.video_files:
            self.compress_button.config(state=tk.DISABLED)
    
    def browse_output(self):
        directory = filedialog.askdirectory(title='Select output directory')
        if directory:
            self.output_dir.set(directory)
    
    def start_compression(self):
        if not self.video_files:
            messagebox.showwarning("Warning", "No videos selected for compression.")
            return
        
        try:
            target_size = float(self.target_size.get())
            if target_size <= 0:
                messagebox.showwarning("Warning", "Target size must be greater than 0.")
                return
        except ValueError:
            messagebox.showwarning("Warning", "Please enter a valid number for target size.")
            return
        
        output_dir = self.output_dir.get()
        if not output_dir:
            messagebox.showwarning("Warning", "Please select an output directory.")
            return
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Disable controls
        self.add_button.config(state=tk.DISABLED)
        self.clear_button.config(state=tk.DISABLED)
        self.browse_button.config(state=tk.DISABLED)
        self.compress_button.config(state=tk.DISABLED)
        self.remove_button.config(state=tk.DISABLED)
        
        # Clear log
        self.log_text.delete(1.0, tk.END)
        
        # Set up progress bar
        self.progress_bar["maximum"] = len(self.video_files)
        self.progress_bar["value"] = 0
        
        # Start compression in a separate thread
        self.status_var.set("Compressing videos...")
        threading.Thread(target=self.compress_videos, daemon=True).start()
    
    def compress_videos(self):
        output_dir = self.output_dir.get()
        target_size = float(self.target_size.get())
        
        total_files = len(self.video_files)
        processed = 0
        
        # Önce toplam işlem sayısını log'a yazalım
        self.progress_queue.put(f"Starting compression of {total_files} videos...")
        
        for i, video_file in enumerate(self.video_files):
            filename = os.path.basename(video_file)
            output_file = os.path.join(output_dir, filename)
            
            # Şu anki ilerlemeyi göster
            current_progress = (i / total_files) * 100
            self.progress_queue.put({"progress": current_progress})
            self.progress_queue.put(f"Processing video {i+1}/{total_files}: {filename}")
            
            # Video sıkıştırma
            success = compress_video(video_file, output_file, target_size, self.progress_queue, self.ffmpeg_path)
            
            processed += 1
            self.progress_queue.put({"progress": (processed / total_files) * 100})
            
            # Sıkıştırma sonucunu raporla
            if success:
                orig_size = os.path.getsize(video_file) / (1024 * 1024)
                new_size = os.path.getsize(output_file) / (1024 * 1024)
                reduction = ((orig_size - new_size) / orig_size) * 100
                self.progress_queue.put(f"Video {i+1}/{total_files} compressed: {orig_size:.2f}MB → {new_size:.2f}MB ({reduction:.1f}% reduction)")
            else:
                self.progress_queue.put(f"Failed to compress video {i+1}/{total_files}: {filename}")
        
        self.progress_queue.put({"done": True})
    
    def process_queue(self):
        try:
            while True:
                message = self.progress_queue.get_nowait()
                
                if isinstance(message, dict):
                    if "progress" in message:
                        progress_value = message["progress"]
                        self.progress_bar["value"] = progress_value
                        self.progress_percent.set(f"{progress_value:.1f}%")
                    
                    if "done" in message:
                        self.status_var.set("Compression completed!")
                        self.operation_var.set("All videos processed")
                        self.progress_percent.set("100%")
                        # Re-enable controls
                        self.add_button.config(state=tk.NORMAL)
                        self.clear_button.config(state=tk.NORMAL)
                        self.browse_button.config(state=tk.NORMAL)
                        self.compress_button.config(state=tk.NORMAL)
                        self.remove_button.config(state=tk.NORMAL)
                        messagebox.showinfo("Success", "Video compression completed!")
                else:
                    # Log mesajını işle
                    self.log_text.insert(tk.END, message + "\n")
                    self.log_text.see(tk.END)  # En sona kaydır
                    
                    # Eğer ilerleme ile ilgili bir mesajsa, işlem etiketini güncelle
                    if "Processing video" in message or "Compressing" in message:
                        self.operation_var.set(message)
                
                self.progress_queue.task_done()
        except queue.Empty:
            pass
        
        # 100ms sonra tekrar kontrol et
        self.root.after(100, self.process_queue)

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoCompressorGUI(root)
    root.mainloop()