import os
import random
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import imagehash
import shutil
from datetime import datetime

# --- Styling Constants ---
BG_COLOR = "#1e1e1e"        # Dark background makes images pop
FG_COLOR = "#ffffff"        # White text
BTN_COLOR = "#333333"       # Dark grey buttons
BTN_ACTIVE = "#555555"      # Lighter grey on hover
FONT_TITLE = ("Helvetica", 24, "bold")
FONT_NORM = ("Helvetica", 14)

class PosterRanker(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Poster Ranker")
        self.geometry("1100x800")
        self.configure(bg=BG_COLOR)
        
        # Game State Variables
        self.target_location = ""
        self.image_paths = []
        self.elo_scores = {}  # Maps file path to Elo score
        self.comparisons_made = 0
        self.max_comparisons = 0  # NEW: Tracks the 3N target
        self.current_img1 = None
        self.current_img2 = None

        self.init_location_screen()

    def clear_window(self):
        """Removes all widgets from the current window."""
        for widget in self.winfo_children():
            widget.destroy()

    # ==========================================
    # SCREEN 1: SELECT LOCATION
    # ==========================================
    def init_location_screen(self):
        self.clear_window()
        
        tk.Label(self, text="Where are you picking posters for?", 
                 font=FONT_TITLE, bg=BG_COLOR, fg=FG_COLOR).pack(pady=80)

        locations = ["Kitchen", "Living Room", "Bed Room"]
        for loc in locations:
            btn = tk.Button(self, text=loc, font=FONT_NORM, width=20, height=2,
                            bg=BTN_COLOR, fg=FG_COLOR, activebackground=BTN_ACTIVE, activeforeground=FG_COLOR,
                            command=lambda l=loc: self.select_folder(l))
            btn.pack(pady=10)

    def select_folder(self, location):
        self.target_location = location
        folder = filedialog.askdirectory(title=f"Select folder with posters for {location}")
        
        if not folder:
            return # User canceled

        # Find all images in the folder
        valid_extensions = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
        raw_paths = []
        
        for f in os.listdir(folder):
            full_path = os.path.join(folder, f)
            # NEW: explicitly checks that this is a file and not a folder!
            if os.path.isfile(full_path) and os.path.splitext(f)[1].lower() in valid_extensions:
                raw_paths.append(full_path)

        if len(raw_paths) < 2:
            messagebox.showerror("Error", "You need at least 2 images in the folder to play!")
            return

        # Filter out visual duplicates before starting
        self.image_paths = self.remove_duplicates(raw_paths)

        if len(self.image_paths) < 2:
            messagebox.showerror("Error", "Not enough unique images left after removing duplicates!")
            return

        # Calculate the 3N target for automatic stopping
        self.max_comparisons = len(self.image_paths) * 3

        # Initialize Elo scores (every poster starts at 1200)
        for path in self.image_paths:
            self.elo_scores[path] = 1200

        self.play_game_screen()

    def remove_duplicates(self, paths):
        """Scans a list of images and removes visual duplicates using Perceptual Hashing."""
        
        # Show a loading screen since hashing hundreds of images takes a few seconds
        self.clear_window()
        tk.Label(self, text="Scanning for duplicates...", 
                 font=FONT_TITLE, bg=BG_COLOR, fg=FG_COLOR).pack(pady=150)
        self.update() # Forces the UI to draw the loading text immediately

        unique_paths = []
        unique_hashes = []
        duplicates_found = 0

        for path in paths:
            try:
                # Open image and calculate its visual fingerprint
                with Image.open(path) as img:
                    img_hash = imagehash.phash(img)
                    
                    is_duplicate = False
                    for seen_hash in unique_hashes:
                        # Subtracting hashes gives the difference. 
                        # A difference of < 5 catches resizing, compression, and minor crops.
                        if img_hash - seen_hash < 5: 
                            is_duplicate = True
                            duplicates_found += 1
                            break
                    
                    if not is_duplicate:
                        unique_hashes.append(img_hash)
                        unique_paths.append(path)
                        
            except Exception as e:
                print(f"Skipping broken file {path}: {e}")

        # Let the user know if we cleaned up the folder
        if duplicates_found > 0:
            messagebox.showinfo("Scan Complete", f"Found and removed {duplicates_found} duplicate/similar images!")

        return unique_paths

    # ==========================================
    # SCREEN 2: THE GAME (COMPARISON)
    # ==========================================
    def play_game_screen(self):
        self.clear_window()
        
        # Header
        header_frame = tk.Frame(self, bg=BG_COLOR)
        header_frame.pack(fill="x", pady=20)
        
        tk.Label(header_frame, text=f"Ranking for: {self.target_location}", 
                 font=FONT_TITLE, bg=BG_COLOR, fg=FG_COLOR).pack()
        
        # NEW: Show the user their progress towards the 3N target
        self.lbl_counter = tk.Label(header_frame, text=f"Comparisons: {self.comparisons_made} / {self.max_comparisons}", 
                                    font=FONT_NORM, bg=BG_COLOR, fg="#aaaaaa")
        self.lbl_counter.pack()

        # Image Container
        self.frame_images = tk.Frame(self, bg=BG_COLOR)
        self.frame_images.pack(expand=True, fill="both", padx=20)

        # Left Image
        self.lbl_img1 = tk.Label(self.frame_images, cursor="hand2", bg=BG_COLOR)
        self.lbl_img1.pack(side="left", expand=True)
        self.lbl_img1.bind("<Button-1>", lambda e: self.choose_winner(1))

        # Right Image
        self.lbl_img2 = tk.Label(self.frame_images, cursor="hand2", bg=BG_COLOR)
        self.lbl_img2.pack(side="right", expand=True)
        self.lbl_img2.bind("<Button-1>", lambda e: self.choose_winner(2))

        # Footer Button (Still here for early stopping)
        tk.Button(self, text="Finish & Show Top 10 Early", font=FONT_NORM, bg="#8b0000", fg=FG_COLOR,
                  activebackground="#a52a2a", activeforeground=FG_COLOR, height=2, width=25,
                  command=self.show_results).pack(pady=30)

        self.load_next_pair()

    def load_next_pair(self):
            # 1. Pick the first image completely at random
            self.current_img1 = random.choice(self.image_paths)

            # 2. Find the second image based on similar Elo score
            score1 = self.elo_scores[self.current_img1]
            
            # Create a list of all OTHER images and how far their score is from Image 1
            candidates = []
            for path in self.image_paths:
                if path != self.current_img1:
                    distance = abs(self.elo_scores[path] - score1)
                    candidates.append((path, distance))
            
            # Sort the list so the closest scores are at the top
            candidates.sort(key=lambda x: x[1])
            
            # 3. Pick randomly from the 5 closest matches
            # (We pick from the top 5 instead of just the #1 closest so you don't 
            # get stuck comparing the exact same two posters back-to-back)
            top_5_candidates = candidates[:5]
            self.current_img2 = random.choice(top_5_candidates)[0]

            # 4. Display them
            self.display_img(self.current_img1, self.lbl_img1, max_size=(450, 550))
            self.display_img(self.current_img2, self.lbl_img2, max_size=(450, 550))

    def display_img(self, path, label, max_size):
            """Resizes image while keeping aspect ratio and updates the label."""
            try:
                img = Image.open(path)
                img.thumbnail(max_size) # Resizes in-place, preserves aspect ratio
                photo = ImageTk.PhotoImage(img)
                label.config(image=photo)
                label.image = photo # Keep reference to prevent garbage collection
            except Exception as e:
                # If the image fails to open (e.g. path too long, corrupted file), 
                # display a text warning instead of crashing.
                label.config(image="", text=f"Error loading image:\n{os.path.basename(path)[:20]}...", fg="red")
                label.image = None

    def choose_winner(self, winner):
        self.comparisons_made += 1
        
        # NEW: Update the counter text
        self.lbl_counter.config(text=f"Comparisons: {self.comparisons_made} / {self.max_comparisons}")

        # Standard Elo Math
        rating1 = self.elo_scores[self.current_img1]
        rating2 = self.elo_scores[self.current_img2]

        expected1 = 1 / (1 + 10 ** ((rating2 - rating1) / 400))
        expected2 = 1 / (1 + 10 ** ((rating1 - rating2) / 400))

        K = 32 # The maximum amount of points that can be won/lost in one round
        
        if winner == 1:
            self.elo_scores[self.current_img1] += K * (1 - expected1)
            self.elo_scores[self.current_img2] += K * (0 - expected2)
        else:
            self.elo_scores[self.current_img1] += K * (0 - expected1)
            self.elo_scores[self.current_img2] += K * (1 - expected2)

        # NEW: Check if we have hit the 3N limit
        if self.comparisons_made >= self.max_comparisons:
            self.show_results()
        else:
            self.load_next_pair()

    # ==========================================
    # SCREEN 3: TOP 10 RESULTS & EXPORT
    # ==========================================
    def show_results(self):
        self.clear_window()
        
        tk.Label(self, text=f"Top Posters for {self.target_location}", 
                 font=FONT_TITLE, bg=BG_COLOR, fg=FG_COLOR).pack(pady=20)
        tk.Label(self, text=f"Total comparisons made: {self.comparisons_made}", 
                 font=FONT_NORM, bg=BG_COLOR, fg="#aaaaaa").pack()

        # Sort images by Elo score, descending. Take top 10.
        sorted_posters = sorted(self.elo_scores.items(), key=lambda x: x[1], reverse=True)[:10]

        # --- NEW AUTOMATIC EXPORT LOGIC ---
        # 1. Format date and time safely (e.g., "2026-07-05_15h37m")
        timestamp = datetime.now().strftime("%Y-%m-%d_%Hh%Mm")
        safe_location = self.target_location.replace(" ", "_") # Changes "Living Room" to "Living_Room"
        
        # 2. Create the new folder inside the original pictures folder
        original_folder = os.path.dirname(self.image_paths[0])
        export_dir = os.path.join(original_folder, f"{safe_location}_{timestamp}")
        os.makedirs(export_dir, exist_ok=True)

        # 3. Copy and rename the files
        for i, (path, score) in enumerate(sorted_posters):
            ext = os.path.splitext(path)[1] # Keeps the original .jpg or .png
            # Formats the number to always have two digits (01, 02... 10)
            new_name = f"poster_{i+1:02d}{ext}" 
            
            # Copy the file to the new folder with the new name
            shutil.copy2(path, os.path.join(export_dir, new_name))
            
        # Alert the user
        messagebox.showinfo("Export Successful", f"Your Top 10 have been saved to:\n{export_dir}")
        # ----------------------------------

        # Grid container for the Top 10 UI
        result_frame = tk.Frame(self, bg=BG_COLOR)
        result_frame.pack(fill="both", expand=True, pady=20)

        for i, (path, score) in enumerate(sorted_posters):
            # Layout in a 2x5 grid
            row = i // 5
            col = i % 5

            f = tk.Frame(result_frame, bg=BG_COLOR)
            f.grid(row=row, column=col, padx=15, pady=10)

            # Thumbnail
            try:
                img = Image.open(path)
                img.thumbnail((160, 160))
                photo = ImageTk.PhotoImage(img)

                lbl = tk.Label(f, image=photo, bg=BG_COLOR)
                lbl.image = photo
                lbl.pack()
            except Exception:
                tk.Label(f, text="Image Error", bg=BG_COLOR, fg="red").pack()

            # Rank & Score text
            tk.Label(f, text=f"#{i+1}", font=("Helvetica", 14, "bold"), 
                     bg=BG_COLOR, fg="#ffd700" if i==0 else FG_COLOR).pack()
            tk.Label(f, text=f"Score: {int(score)}", font=("Helvetica", 10), 
                     bg=BG_COLOR, fg="#aaaaaa").pack()

if __name__ == "__main__":
    app = PosterRanker()
    app.mainloop()