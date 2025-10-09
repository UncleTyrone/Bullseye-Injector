#!/usr/bin/env python3
"""
Bullseye Injector GUI
A user-friendly interface for the PokeMMO sprite replacement pipeline.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import logging
import time
from datetime import datetime
from pathlib import Path
import json
import re
import queue
from functools import lru_cache
import gc
import os

# Import the core processing functionality
from mod_packager import ModPackager


class SpriteConverterGUI:
    """
    Main GUI application for Bullseye Injector.
    
    This class provides a comprehensive interface for sprite injection and mod creation,
    featuring intelligent file analysis, real-time preview, and automated processing.
    
    Key Features:
    - Intelligent sprite file matching and analysis
    - Real-time preview system with caching
    - Comprehensive file operation recommendations
    - Automated mod packaging and compilation
    - Progress tracking and error handling
    - Settings persistence and configuration management
    
    Attributes:
        root (tk.Tk): Main Tkinter root window
        move_dir (tk.StringVar): Bullseye sprites directory path
        sprite_dir (tk.StringVar): Custom sprites directory path
        output_dir (tk.StringVar): Output directory for generated mods
        log_dir (tk.StringVar): Directory for log files
        processing (bool): Whether processing is currently active
        current_recommendations (list): List of file operation recommendations
        unfulfilled_files (dict): Dictionary of unfulfilled files and their status
        preview_cache (dict): Cache for processed preview images
    """
    
    def __init__(self, root):
        self.root = root
        self.root.title("Bullseye Injector v1.0")
        self.root.geometry("800x800")
        self.root.minsize(750, 750)
        self.root.resizable(True, True)
        
        # Set icon if available
        self.set_application_icon()
        
        # Set a modern dark color scheme with purple accents
        self.root.configure(bg='#2a2a2a')
        
        # Variables
        self.move_dir = tk.StringVar()
        self.sprite_dir = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.log_dir = tk.StringVar(value="logs")  # Default log directory
        self.limit_var = tk.StringVar()
        self.process_all = tk.BooleanVar(value=True)
        self.show_logs = tk.BooleanVar(value=True)
        self.use_custom_log_dir = tk.BooleanVar(value=False)
        
        # Add trace callbacks to detect directory changes
        self.move_dir.trace('w', self.on_directory_change)
        self.sprite_dir.trace('w', self.on_directory_change)
        self.output_dir.trace('w', self.on_directory_change)
        
        # Processing state
        self.processing = False
        self.paused = False
        self.mod_creation_successful = False
        self.process_thread = None
        self.detect_files_scheduled = False  # Prevent double execution
        self.initial_setup = True  # Flag to prevent directory change detection during setup
        self.analysis_running = False  # Flag to track if file analysis is currently running
        self.file_detection_complete = False  # Flag to track if file detection has completed
        
        # Preview state
        self.preview_label = None
        self.preview_queue = []  # Queue of sprites to preview
        self.current_preview_index = 0
        self.preview_cycle_timer = None
        self.preview_display_duration = 800  # 0.8 seconds per sprite for faster cycling
        self.preview_cache = {}  # Cache for processed preview images (max 50 images)
        self.preview_cache_max_size = 50  # Maximum number of cached images
        self.preview_cache_order = []  # LRU tracking for cache
        
        # Initialize scaling configuration with defaults
        self.default_summary_scale = 2.7
        self.default_front_scale = 1.0
        self.default_back_scale = 1.0
        self.detection_threshold = 1.10
        self.summary_overrides = {}
        self.front_overrides = {}
        self.back_overrides = {}
        
        # Load settings
        self.load_settings()
        
        # Create GUI
        self.create_widgets()
        
        # Initial file detection after everything is set up (only if directories are set)
        self.root.after(500, self.initial_detect_files)
        
        # Set up proper cleanup on window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Center window
        self.center_window()
    
    def center_window(self):
        """Center the window on screen"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
    
    def set_application_icon(self):
        """
        Set the application icon for both development and built versions.
        
        This method handles icon setting across different execution contexts:
        - Development: Uses icon.ico from the project directory
        - Built executable: Uses the embedded icon from the executable
        - Fallback: Uses default system icon if no custom icon is available
        
        The method tries multiple approaches to ensure the icon is properly displayed
        in both development and production environments.
        """
        try:
            import sys
            import os
            
            # Try to set icon from file (for development)
            icon_path = Path("icon.ico")
            if icon_path.exists():
                self.root.iconbitmap(str(icon_path))
                return
            
            # For built executables, try multiple approaches
            if getattr(sys, 'frozen', False):
                # Running as built executable
                try:
                    # Method 1: Try to use the executable's embedded icon
                    if sys.platform == "win32":
                        exe_path = sys.executable
                        if exe_path and os.path.exists(exe_path):
                            self.root.iconbitmap(exe_path)
                            return
                    
                    # Method 2: Try to find the icon in the temporary directory
                    # PyInstaller extracts data files to a temp directory
                    base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
                    temp_icon_path = os.path.join(base_path, "icon.ico")
                    if os.path.exists(temp_icon_path):
                        self.root.iconbitmap(temp_icon_path)
                        return
                        
                except Exception:
                    pass  # If this fails, we'll just use the default icon
                    
        except Exception as e:
            # If all else fails, just use the default icon
            print(f"Could not set application icon: {e}")
    
    def create_widgets(self):
        """Create all GUI widgets"""
        # Main container with compact spacing
        main_container = tk.Frame(self.root, bg='#3a3a3a')
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Main content area - vertical layout
        content_frame = tk.Frame(main_container, bg='#3a3a3a')
        content_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 0))
        
        # Create sections in vertical order
        self.create_directory_section(content_frame)
        self.create_utility_bar(content_frame)
        self.create_preview_and_options_section(content_frame)
        self.create_progress_section(content_frame)
        self.create_log_section(content_frame)
        
        # Initialize the limit entry state
        self.toggle_limit()
    
    def create_directory_section(self, parent):
        """Create directory selection section"""
        # Directory section frame
        dir_frame = tk.LabelFrame(parent, text="📁 Directories", 
                                 font=("Segoe UI", 10, "bold"),
                                 bg='#3a3a3a', fg='#e0e0e0',
                                 relief=tk.FLAT, bd=1,
                                 highlightbackground='#555555', highlightthickness=1)
        dir_frame.pack(fill=tk.X, pady=(0, 8))
        
        # Compact directory layout - 2 columns
        left_col = tk.Frame(dir_frame, bg='#3a3a3a')
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=8)
        
        right_col = tk.Frame(dir_frame, bg='#3a3a3a')
        right_col.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=8, pady=8)
        
        # Left column - Bullseye and Replacement sprites
        self.create_dir_row(left_col, "Bullseye Sprites:", self.move_dir, self.browse_move_dir)
        self.create_dir_row(left_col, "Replacement Sprites:", self.sprite_dir, self.browse_sprite_dir)
        
        # Right column - Output and Log directories
        self.create_dir_row(right_col, "Output Directory:", self.output_dir, self.browse_output_dir)
        
        # Log directory (compact)
        log_frame = tk.Frame(right_col, bg='#3a3a3a')
        log_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.log_dir_cb = tk.Checkbutton(log_frame, text="Custom Log Dir:", 
                                       variable=self.use_custom_log_dir,
                                       command=self.toggle_log_dir,
                                       font=("Segoe UI", 8),
                                       bg='#3a3a3a', fg='#e0e0e0',
                                       selectcolor='#555555',
                                       activebackground='#3c3c3c',
                                       activeforeground='#e0e0e0')
        self.log_dir_cb.pack(side=tk.LEFT)
        
        self.log_entry = tk.Entry(log_frame, textvariable=self.log_dir, 
                                font=("Segoe UI", 8),
                                relief=tk.FLAT, bd=1, bg='#4a4a4a', fg='#e0e0e0',
                                insertbackground='#e0e0e0',
                                highlightthickness=1, highlightcolor='#8e44ad',
                                state=tk.DISABLED, disabledbackground='#5a5a5a')
        self.log_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        
        self.log_browse_btn = tk.Button(log_frame, text="...", 
                                      command=self.browse_log_dir,
                                      font=("Segoe UI", 8),
                                      bg='#555555', fg='white',
                                      relief=tk.FLAT, bd=0,
                                      padx=8, pady=3,
                                      cursor='hand2',
                                      state=tk.DISABLED,
                                      activebackground='#666666')
        self.log_browse_btn.pack(side=tk.LEFT)
        
        # File detection section
        self.create_file_detection_section(dir_frame)
    
    def create_dir_row(self, parent, label_text, var, command):
        """Create a compact directory selection row"""
        row_frame = tk.Frame(parent, bg='#3a3a3a')
        row_frame.pack(fill=tk.X, pady=2)
        
        # Label
        label = tk.Label(row_frame, text=label_text, 
                       font=("Segoe UI", 8), 
                       bg='#3a3a3a', fg='#e0e0e0',
                       width=20, anchor=tk.W)
        label.pack(side=tk.LEFT)
        
        # Entry
        entry = tk.Entry(row_frame, textvariable=var, 
                       font=("Segoe UI", 8),
                       relief=tk.FLAT, bd=1, bg='#4a4a4a', fg='#e0e0e0',
                       insertbackground='#e0e0e0',
                       highlightthickness=1, highlightcolor='#8e44ad',
                       width=25)
        entry.pack(side=tk.LEFT, padx=(5, 5))
        
        # Browse button
        btn = tk.Button(row_frame, text="...", 
                      command=command,
                      font=("Segoe UI", 8),
                      bg='#555555', fg='white',
                      relief=tk.FLAT, bd=0,
                      padx=8, pady=3,
                      cursor='hand2',
                      activebackground='#666666')
        btn.pack(side=tk.LEFT)
        
        # Hover effects
        btn.bind("<Enter>", lambda e, b=btn: b.config(bg='#666666'))
        btn.bind("<Leave>", lambda e, b=btn: b.config(bg='#555555'))
    
    def create_file_detection_section(self, parent):
        """Create file detection and validation section"""
        detection_frame = tk.Frame(parent, bg='#3a3a3a')
        detection_frame.pack(fill=tk.X, pady=(8, 0))
        
        # Load Files button
        self.refresh_btn = tk.Button(detection_frame, text="📁 Load Files", 
                              command=self.refresh_analysis,
                              font=("Segoe UI", 8),
                              bg='#555555', fg='white',
                              relief=tk.FLAT, bd=0,
                              padx=8, pady=3,
                              cursor='hand2')
        self.refresh_btn.pack(side=tk.RIGHT, padx=(0, 8))
        
        # Hover effects
        self.refresh_btn.bind("<Enter>", lambda e, b=self.refresh_btn: b.config(bg='#7f8c8d'))
        self.refresh_btn.bind("<Leave>", lambda e, b=self.refresh_btn: b.config(bg='#555555'))
    
    def create_preview_and_options_section(self, parent):
        """Create preview and options section side by side"""
        # Main container for preview and options
        main_frame = tk.Frame(parent, bg='#3a3a3a')
        main_frame.pack(fill=tk.X, pady=(0, 0))
        
        # Configure grid weights for centering
        main_frame.grid_columnconfigure(0, weight=1)  # Options section
        main_frame.grid_columnconfigure(1, weight=1)  # Center space
        main_frame.grid_columnconfigure(2, weight=1)  # Preview section
        
        # Left side - Options section
        self.create_options_section(main_frame)
        
        # Right side - Preview section
        self.create_preview_section(main_frame)
    
    def create_options_section(self, parent):
        """Create options section"""
        options_frame = tk.LabelFrame(parent, text="⚙️ Options", 
                                    font=("Segoe UI", 10, "bold"),
                                    bg='#3a3a3a', fg='#e0e0e0',
                                    relief=tk.FLAT, bd=1)
        options_frame.grid(row=0, column=0, sticky="nw", padx=(0, 10))
        
        # Vertical layout for all options
        options_container = tk.Frame(options_frame, bg='#3a3a3a')
        options_container.pack(fill=tk.X, padx=8, pady=(12, 8))
        
        # Process all checkbox
        self.process_all_cb = tk.Checkbutton(options_container, text="Process all", 
                                           variable=self.process_all,
                                           command=self.toggle_limit,
                                           font=("Segoe UI", 10),
                                           bg='#3a3a3a', fg='#e0e0e0',
                                           selectcolor='#555555',
                                           activebackground='#3c3c3c',
                                           activeforeground='#e0e0e0')
        self.process_all_cb.pack(anchor=tk.W, pady=(0, 8))
        
        # Limit option row
        limit_frame = tk.Frame(options_container, bg='#3a3a3a')
        limit_frame.pack(anchor=tk.W, pady=(0, 8))
        
        self.limit_label = tk.Label(limit_frame, text="Limit to:", 
                font=("Segoe UI", 10),
                bg='#3a3a3a', fg='#e0e0e0')
        self.limit_label.pack(side=tk.LEFT, padx=(0, 8))
        
        self.limit_entry = tk.Entry(limit_frame, textvariable=self.limit_var, 
                                  width=8, font=("Segoe UI", 10),
                                  relief=tk.FLAT, bd=1, bg='#4a4a4a', fg='#e0e0e0', insertbackground='#e0e0e0',
                                  highlightthickness=1, highlightcolor='#8e44ad',
                                  state=tk.DISABLED, disabledbackground='#5a5a5a')
        self.limit_entry.pack(side=tk.LEFT, padx=(0, 8))
        
        self.sprites_label = tk.Label(limit_frame, text="sprites", 
                font=("Segoe UI", 10),
                bg='#3a3a3a', fg='#e0e0e0')
        self.sprites_label.pack(side=tk.LEFT)
        
        # Show logs checkbox
        self.show_logs_cb = tk.Checkbutton(options_container, text="Show logs", 
                                         variable=self.show_logs,
                                         font=("Segoe UI", 10),
                                         bg='#3a3a3a', fg='#e0e0e0',
                                         selectcolor='#555555',
                                         activebackground='#3c3c3c',
                                         activeforeground='#e0e0e0')
        self.show_logs_cb.pack(anchor=tk.W)
    
    
    def create_utility_bar(self, parent):
        """Create utility bar with Start/Stop, Fix Issues, Issues, and preview"""
        utility_frame = tk.Frame(parent, bg='#3a3a3a', height=55)
        utility_frame.pack(fill=tk.X, pady=(10, 0))
        utility_frame.pack_propagate(False)
        
        # Left side - square Start/Stop buttons
        control_buttons_frame = tk.Frame(utility_frame, bg='#3a3a3a')
        control_buttons_frame.pack(side=tk.LEFT, padx=(0, 15))
        
        # Square Start button (initially disabled until analysis completes)
        self.start_button = tk.Button(control_buttons_frame, text="▶", 
                                    command=self.start_processing,
                                    font=("Segoe UI", 14, "bold"),
                                    bg='#27ae60', fg='white',
                                    disabledforeground='#95a5a6',  # Gray when disabled
                                    relief=tk.FLAT, bd=0,
                                    width=3, height=1,
                                    cursor='hand2',
                                    state=tk.DISABLED)  # Start disabled until analysis completes
        self.start_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # Square Pause button
        self.pause_button = tk.Button(control_buttons_frame, text="⏸", 
                                    command=self.pause_processing,
                                    font=("Segoe UI", 14, "bold"),
                                    bg='#f39c12', fg='white',
                                    disabledforeground='#888888',
                                    relief=tk.FLAT, bd=0,
                                    width=3, height=1,
                                    cursor='hand2',
                                    state=tk.DISABLED)
        self.pause_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # Square Stop button
        self.stop_button = tk.Button(control_buttons_frame, text="⏹", 
                                   command=self.stop_processing,
                                   font=("Segoe UI", 14, "bold"),
                                   bg='#e74c3c', fg='white',
                                   disabledforeground='#888888',
                                   relief=tk.FLAT, bd=0,
                                   width=3, height=1,
                                   cursor='hand2',
                                   state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT)
        
        # Center - sleek utility buttons
        utility_buttons_frame = tk.Frame(utility_frame, bg='#3a3a3a')
        utility_buttons_frame.pack(side=tk.LEFT, padx=(0, 15))
        
        # Fix Issues button removed - functionality merged into Issues tab
        
        # Issues button - longer and sleeker
        self.unfulfilled_button = tk.Button(utility_buttons_frame, text="Issues", 
                                           command=self.show_unfulfilled_files,
                                           font=("Segoe UI", 10, "bold"),
                                           bg='#e74c3c', fg='white',
                                           relief=tk.FLAT, bd=0,
                                           padx=25, pady=8,
                                           cursor='hand2',
                                           width=12)
        self.unfulfilled_button.pack(side=tk.LEFT, padx=(0, 8))
        
        
        # Add hover effects
        self.add_button_hover_effects()
    
    def add_button_hover_effects(self):
        """Add hover effects to buttons"""
        # Start button hover
        self.start_button.bind("<Enter>", lambda e: self.start_button.config(bg='#229954'))
        self.start_button.bind("<Leave>", lambda e: self.start_button.config(bg='#27ae60'))
        
        # Pause button hover
        self.pause_button.bind("<Enter>", lambda e: self.pause_button.config(bg='#e67e22'))
        self.pause_button.bind("<Leave>", lambda e: self.pause_button.config(bg='#f39c12'))
        
        # Stop button hover
        self.stop_button.bind("<Enter>", lambda e: self.stop_button.config(bg='#c0392b'))
        self.stop_button.bind("<Leave>", lambda e: self.stop_button.config(bg='#e74c3c'))
        
        # Fix Issues button hover removed - button no longer exists
        
        # Unfulfilled button hover
        self.unfulfilled_button.bind("<Enter>", lambda e: self.unfulfilled_button.config(bg='#c0392b'))
        self.unfulfilled_button.bind("<Leave>", lambda e: self.unfulfilled_button.config(bg='#e74c3c'))
    
    def create_preview_section(self, parent):
        """Create dedicated preview section"""
        preview_frame = tk.LabelFrame(parent, text="🖼️ Preview", 
                                    font=("Segoe UI", 10, "bold"),
                                    bg='#3a3a3a', fg='#e0e0e0',
                                    relief=tk.FLAT, bd=1,
                                    labelanchor='n')
        preview_frame.grid(row=0, column=1, sticky="n", padx=(10, 10))
        
        # Square preview area - fixed size to be perfectly square
        preview_container = tk.Frame(preview_frame, bg='#3a3a3a')
        preview_container.pack(pady=5, padx=5)
        preview_container.configure(width=200, height=200)  # Reasonable size that prevents overflow
        preview_container.pack_propagate(False)  # Prevent size changes
        
        # Create a frame for the preview content
        preview_content_frame = tk.Frame(preview_container, bg='#4a4a4a', relief=tk.SUNKEN, bd=1)
        preview_content_frame.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
        
        # Square preview label for the GIF
        self.preview_label = tk.Label(preview_content_frame, text="No sprites\nprocessed yet", 
                                     font=("Segoe UI", 10),
                                     fg='#95a5a6', bg='#4a4a4a',
                                     justify=tk.CENTER,
                                     anchor=tk.CENTER)  # Center the image within the label
        self.preview_label.pack(fill=tk.BOTH, expand=True)
    
    def create_progress_section(self, parent):
        """Create progress section"""
        progress_frame = tk.LabelFrame(parent, text="📊 Progress", 
                                     font=("Segoe UI", 10, "bold"),
                                     bg='#3a3a3a', fg='#e0e0e0',
                                     relief=tk.FLAT, bd=1)
        progress_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Compact progress layout
        progress_content = tk.Frame(progress_frame, bg='#3a3a3a')
        progress_content.pack(fill=tk.X, padx=8, pady=5)
        
        # Status and progress in one row
        status_frame = tk.Frame(progress_content, bg='#3a3a3a')
        status_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Status label
        self.status_var = tk.StringVar(value="Ready to process sprites")
        self.status_label = tk.Label(status_frame, textvariable=self.status_var,
                                   font=("Segoe UI", 9),
                                   bg='#3a3a3a', fg='#e0e0e0')
        self.status_label.pack(side=tk.LEFT)
        
        # Progress bar with custom styling (compact)
        self.progress_var = tk.DoubleVar()
        self.progress_bar = tk.Canvas(progress_frame, height=16, bg='#4a4a4a',
                                    highlightthickness=0, relief=tk.FLAT)
        self.progress_bar.pack(fill=tk.X, padx=10, pady=(0, 5))
        
        # File count label (compact)
        self.file_count_var = tk.StringVar()
        self.file_count_label = tk.Label(progress_frame, textvariable=self.file_count_var,
                                       font=("Segoe UI", 8),
                                       bg='#3a3a3a', fg='#b0b0b0')
        self.file_count_label.pack(pady=(0, 2))
    
    def create_log_section(self, parent):
        """Create log section"""
        log_frame = tk.LabelFrame(parent, text="📝 Log Output", 
                                font=("Segoe UI", 10, "bold"),
                                bg='#3a3a3a', fg='#e0e0e0',
                                relief=tk.FLAT, bd=1)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 2))
        
        # Log header with clear button
        log_header = tk.Frame(log_frame, bg='#3a3a3a', height=25)
        log_header.pack(fill=tk.X, padx=6, pady=(2, 0))
        log_header.pack_propagate(False)
        
        # Small clear logs button in top right
        clear_logs_btn = tk.Button(log_header, text="Clear", 
                                 command=self.clear_logs,
                                 font=("Segoe UI", 8),
                                 bg='#555555', fg='white',
                                 relief=tk.FLAT, bd=0,
                                 padx=8, pady=2,
                                 cursor='hand2')
        clear_logs_btn.pack(side=tk.RIGHT, pady=2)
        
        # Clear logs button hover effects
        clear_logs_btn.bind("<Enter>", lambda e: clear_logs_btn.config(bg='#666666'))
        clear_logs_btn.bind("<Leave>", lambda e: clear_logs_btn.config(bg='#555555'))
        
        # Log text area with modern styling (maximized for more lines)
        self.log_text = scrolledtext.ScrolledText(log_frame, 
                                                height=30, width=70,
                                                font=("Consolas", 8),
                                                bg='#2a2a2a', fg='#e0e0e0',
                                                insertbackground='#e0e0e0',
                                                selectbackground='#8e44ad',
                                                relief=tk.FLAT, bd=0,
                                                padx=6, pady=6,
                                                state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 2))
    
    def update_progress_bar(self, progress):
        """Update the custom progress bar"""
        self.progress_bar.delete("all")
        width = self.progress_bar.winfo_width()
        if width <= 1:  # Canvas not yet rendered
            self.root.after(100, lambda: self.update_progress_bar(progress))
            return
        
        # Draw progress bar
        progress_width = int((progress / 100) * (width - 4))
        self.progress_bar.create_rectangle(2, 2, progress_width, 18, 
                                         fill='#3498db', outline='')
        
        # Draw percentage text
        if progress > 0:
            self.progress_bar.create_text(width//2, 10, 
                                        text=f"{progress:.0f}%", 
                                        fill='#2c3e50', 
                                        font=("Segoe UI", 9, "bold"))
    
    def start_animated_progress(self):
        """Start animated progress bar that moves smoothly forward only"""
        import random
        
        self.progress_animation_active = True
        self.progress_animation_value = 0  # Start at 0%
        self.progress_animation_speed = random.uniform(0.3, 0.8)  # Random speed per update
        self.progress_animation_pause_chance = 0.1  # 10% chance to pause
        self.progress_animation_max_value = 99  # Maximum value before completion (99% so it waits for 100%)
        
        def animate_progress():
            if not self.progress_animation_active:
                return
            
            # Randomly decide whether to move forward or pause
            if random.random() > self.progress_animation_pause_chance:
                # Move forward with random speed (3x faster)
                increment = random.uniform(0.45, 1.35)  # 3x faster: 0.15-0.45 -> 0.45-1.35
                self.progress_animation_value += increment
                
                # Occasionally have bigger jumps to simulate real progress
                if random.random() < 0.05:  # 5% chance for bigger jump
                    self.progress_animation_value += random.uniform(2.25, 5.625)  # 3x faster: 0.75-1.875 -> 2.25-5.625
            
            # Keep it within bounds
            self.progress_animation_value = min(self.progress_animation_max_value, self.progress_animation_value)
            
            # Update the progress bar
            self.update_progress_bar(self.progress_animation_value)
            
            # Randomize the update interval for more natural feel (3x faster)
            update_interval = random.randint(33, 67)  # 3x faster: 100-200ms -> 33-67ms
            self.root.after(update_interval, animate_progress)
        
        # Start the animation
        animate_progress()
    
    def stop_animated_progress(self):
        """Stop animated progress and jump to 100%"""
        self.progress_animation_active = False
        self.update_progress_bar(100)
        # Update status immediately when progress completes
        self.root.after(0, lambda: self.status_var.set("✅ Analysis complete"))
    
    def browse_directory(self, var, title, log_message=None):
        """Generic directory browser with comprehensive validation"""
        directory = filedialog.askdirectory(title=title)
        if directory:
            # Validate the directory before setting it
            if not self.validate_directory(directory, var):
                return
            
            var.set(directory)
            if log_message:
                self.log_message(log_message.format(directory), "INFO")
            
            # Perform smart file analysis for all directories
            if var in [self.move_dir, self.sprite_dir]:
                self.analyze_sprite_directory(directory, var)
            elif var == self.output_dir:
                self.analyze_output_directory(directory)
    
    def validate_directory(self, directory, var):
        """Comprehensive directory validation"""
        dir_path = Path(directory)
        
        # 1. Check if directory is empty (skip this check for output directory)
        if var != self.output_dir:
            try:
                all_files = list(dir_path.iterdir())
                if not all_files:
                    dir_type = "Bullseye sprites" if var == self.move_dir else "replacement sprites"
                    messagebox.showerror("Empty Directory", 
                                       f"The selected {dir_type} directory is empty!\n\n"
                                       f"Directory: {directory}\n\n"
                                       f"Please select a directory that contains files.")
                    return False
            except Exception as e:
                messagebox.showerror("Directory Error", 
                                   f"Cannot access the selected directory!\n\n"
                                   f"Directory: {directory}\n"
                                   f"Error: {str(e)}")
                return False
        
        # 2. Check for duplicate directory usage
        other_dirs = []
        if var == self.move_dir:
            other_dirs = [self.sprite_dir.get(), self.output_dir.get()]
        elif var == self.sprite_dir:
            other_dirs = [self.move_dir.get(), self.output_dir.get()]
        elif var == self.output_dir:
            other_dirs = [self.move_dir.get(), self.sprite_dir.get()]
        
        for other_dir in other_dirs:
            if other_dir and Path(other_dir).resolve() == dir_path.resolve():
                dir_type = "Bullseye sprites" if var == self.move_dir else "replacement sprites" if var == self.sprite_dir else "output"
                other_type = "replacement sprites" if other_dir == self.sprite_dir.get() else "Bullseye sprites" if other_dir == self.move_dir.get() else "output"
                messagebox.showerror("Duplicate Directory", 
                                   f"Cannot use the same directory for {dir_type} and {other_type}!\n\n"
                                   f"Directory: {directory}\n\n"
                                   f"Please select different directories for each purpose.")
                return False
        
        # 3. For sprite directories only (not output), check for completely empty folders only
        if var in [self.move_dir, self.sprite_dir]:
            sprite_files = list(dir_path.glob("*.gif")) + list(dir_path.glob("*.png"))
            non_sprite_files = [f for f in all_files if f.is_file() and f not in sprite_files]
            
            # Only block if directory is completely empty
            if not all_files:
                dir_type = "Bullseye sprites" if var == self.move_dir else "replacement sprites"
                messagebox.showerror("Empty Directory", 
                                   f"The selected {dir_type} directory is empty!\n\n"
                                   f"Directory: {directory}\n\n"
                                   f"Please select a directory that contains files.")
                return False
            
            # If directory has files but no sprite files, block (need at least one valid sprite)
            if not sprite_files and non_sprite_files:
                dir_type = "Bullseye sprites" if var == self.move_dir else "replacement sprites"
                non_sprite_names = [f.name for f in non_sprite_files[:5]]  # Show first 5
                more_count = len(non_sprite_files) - 5
                more_text = f" and {more_count} more files" if more_count > 0 else ""
                
                messagebox.showerror("No Valid Sprite Files Found", 
                                   f"The {dir_type} directory contains no .gif or .png sprite files!\n\n"
                                   f"Non-sprite files found:\n" + "\n".join(non_sprite_names) + more_text + "\n\n"
                                   f"Directory: {directory}\n\n"
                                   f"At least one valid sprite file (.gif or .png) is required.\n"
                                   f"Please select a directory that contains sprite files.")
                return False
            
            # If directory has both sprite files and non-sprite files, just inform
            elif sprite_files and non_sprite_files:
                dir_type = "Bullseye sprites" if var == self.move_dir else "replacement sprites"
                non_sprite_count = len(non_sprite_files)
                # Just log a message, don't block - these might be fixable malformed files
                # (Removed verbose logging - non-sprite files are handled during processing)
        
        return True
    
    def analyze_sprite_directory(self, directory, var):
        """Perform smart file analysis for sprite directories"""
        try:
            dir_path = Path(directory)
            sprite_files = list(dir_path.glob("*.gif")) + list(dir_path.glob("*.png"))
            
            if not sprite_files:
                return
            
            # Analyze file patterns
            analysis = self.analyze_sprite_files(sprite_files)
            
            # Create smart one-line summary
            dir_type = "Bullseye" if var == self.move_dir else "Replacement"
            summary = self.create_file_analysis_summary(analysis, dir_type)
            
            # Log the analysis
            self.log_message(f"📊 {dir_type} Directory Analysis: {summary}", "INFO")
            
        except Exception as e:
            self.log_message(f"⚠️ Could not analyze directory {directory}: {str(e)}", "WARNING")
    
    def analyze_sprite_files(self, sprite_files):
        """Analyze sprite files and return detailed statistics"""
        analysis = {
            'total_files': len(sprite_files),
            'gif_count': 0,
            'png_count': 0,
            'front_files': 0,
            'back_files': 0,
            'normal_direction_files': 0,
            'shiny_files': 0,
            'normal_variant_files': 0,
            'male_files': 0,
            'female_files': 0,
            'base_files': 0,
            'pokemon_count': set(),
            'malformed_files': []
        }
        
        for file_path in sprite_files:
            filename = file_path.name
            
            # Count file types
            if filename.endswith('.gif'):
                analysis['gif_count'] += 1
            elif filename.endswith('.png'):
                analysis['png_count'] += 1
            
            # Parse filename for detailed analysis
            parsed = self.parse_sprite_filename(filename)
            if parsed:
                dex = parsed['dex']
                direction = parsed['direction']
                variant = parsed['variant']
                gender = parsed['gender']
                analysis['pokemon_count'].add(dex)
                
                # Count directions
                if direction == 'front':
                    analysis['front_files'] += 1
                elif direction == 'back':
                    analysis['back_files'] += 1
                elif direction == 'normal':
                    analysis['normal_direction_files'] += 1
                
                # Count variants
                if variant == 's':
                    analysis['shiny_files'] += 1
                elif variant == 'n':
                    analysis['normal_variant_files'] += 1
                
                # Count genders
                if gender == 'm':
                    analysis['male_files'] += 1
                elif gender == 'f':
                    analysis['female_files'] += 1
                elif gender == '':
                    analysis['base_files'] += 1
            else:
                analysis['malformed_files'].append(filename)
        
        analysis['unique_pokemon'] = len(analysis['pokemon_count'])
        return analysis
    
    def create_file_analysis_summary(self, analysis, dir_type):
        """Create a simple one-line summary of file analysis for directory selection"""
        parts = []
        
        # Basic count
        parts.append(f"{analysis['total_files']} sprite files")
        
        # File types
        if analysis['gif_count'] > 0 and analysis['png_count'] > 0:
            parts.append(f"({analysis['gif_count']} GIF, {analysis['png_count']} PNG)")
        elif analysis['gif_count'] > 0:
            parts.append(f"({analysis['gif_count']} GIF)")
        elif analysis['png_count'] > 0:
            parts.append(f"({analysis['png_count']} PNG)")
        
        # Pokemon count
        if analysis['unique_pokemon'] > 0:
            parts.append(f"• {analysis['unique_pokemon']} Pokemon")
        
        # Malformed files warning (only if significant)
        if analysis['malformed_files'] and len(analysis['malformed_files']) > 0:
            parts.append(f"⚠️ {len(analysis['malformed_files'])} malformed")
        
        return " | ".join(parts)
    
    def analyze_output_directory(self, directory):
        """Perform smart file analysis for output directory"""
        try:
            dir_path = Path(directory)
            all_files = list(dir_path.iterdir())
            
            if not all_files:
                self.log_message("📁 Output Directory Analysis: Empty directory (ready for new .mod files)", "INFO")
                return
            
            # Analyze different file types in output directory
            analysis = {
                'total_files': len(all_files),
                'mod_files': 0,
                'zip_files': 0,
                'sprite_files': 0,
                'other_files': 0,
                'mod_names': [],
                'zip_names': [],
                'other_names': []
            }
            
            for file_path in all_files:
                if file_path.is_file():
                    filename = file_path.name.lower()
                    if filename.endswith('.mod'):
                        analysis['mod_files'] += 1
                        analysis['mod_names'].append(file_path.name)
                    elif filename.endswith('.zip'):
                        analysis['zip_files'] += 1
                        analysis['zip_names'].append(file_path.name)
                    elif filename.endswith(('.gif', '.png')):
                        analysis['sprite_files'] += 1
                    else:
                        analysis['other_files'] += 1
                        analysis['other_names'].append(file_path.name)
            
            # Create smart one-line summary
            summary = self.create_output_analysis_summary(analysis)
            self.log_message(f"📁 Output Directory Analysis: {summary}", "INFO")
            
        except Exception as e:
            self.log_message(f"⚠️ Could not analyze output directory {directory}: {str(e)}", "WARNING")
    
    def create_output_analysis_summary(self, analysis):
        """Create a smart one-line summary of output directory analysis"""
        parts = []
        
        # Basic count
        parts.append(f"{analysis['total_files']} files")
        
        # File type breakdown
        type_parts = []
        if analysis['mod_files'] > 0:
            type_parts.append(f"{analysis['mod_files']} .mod")
        if analysis['zip_files'] > 0:
            type_parts.append(f"{analysis['zip_files']} .zip")
        if analysis['sprite_files'] > 0:
            type_parts.append(f"{analysis['sprite_files']} sprites")
        if analysis['other_files'] > 0:
            type_parts.append(f"{analysis['other_files']} other")
        
        if type_parts:
            parts.append(f"• {', '.join(type_parts)}")
        
        
        return " | ".join(parts)
    
    def validate_directories_for_analysis(self):
        """Comprehensive directory validation for analysis startup"""
        errors = []
        
        # Check if directories are selected
        if not self.move_dir.get():
            errors.append("Please select a Bullseye sprites directory")
        if not self.sprite_dir.get():
            errors.append("Please select a replacement sprites directory")
        if not self.output_dir.get():
            errors.append("Please select an output directory")
        
        # If any directories are missing, return early
        if errors:
            return errors
        
        # Validate sprite directories using the smart validation (output directory is allowed to be empty)
        sprite_directories_to_validate = [
            (self.move_dir.get(), "Bullseye sprites", self.move_dir),
            (self.sprite_dir.get(), "replacement sprites", self.sprite_dir)
        ]
        
        for directory, dir_type, var in sprite_directories_to_validate:
            if not self.validate_directory(directory, var):
                errors.append(f"Invalid {dir_type} directory: {directory}")
        
        # For output directory, only check if it exists and is accessible (allow empty)
        output_dir = self.output_dir.get()
        if output_dir:
            try:
                output_path = Path(output_dir)
                if not output_path.exists():
                    errors.append(f"Output directory does not exist: {output_dir}")
                elif not output_path.is_dir():
                    errors.append(f"Output path is not a directory: {output_dir}")
            except Exception as e:
                errors.append(f"Cannot access output directory: {output_dir} - {str(e)}")
        
        return errors
    
    def browse_move_dir(self):
        """Browse for bullseye sprites directory"""
        self.browse_directory(self.move_dir, "Select Bullseye Sprites Directory")
    
    def browse_sprite_dir(self):
        """Browse for replacement sprites directory"""
        self.browse_directory(self.sprite_dir, "Select Replacement Sprites Directory")
    
    def browse_output_dir(self):
        """Browse for output directory"""
        self.browse_directory(self.output_dir, "Select Output Directory")
    
    def browse_log_dir(self):
        """Browse for log directory"""
        self.browse_directory(self.log_dir, "Select Log Directory")
    
    def get_gender_variants(self, base_file):
        """Get male and female variants of a base file"""
        if base_file.endswith('.gif'):
            return (base_file.replace('.gif', '-m.gif'), base_file.replace('.gif', '-f.gif'))
        elif base_file.endswith('.png'):
            return (base_file.replace('.png', '-m.png'), base_file.replace('.png', '-f.png'))
        else:
            return (None, None)
    
    def toggle_limit(self):
        """Toggle limit entry state"""
        if self.process_all.get():
            # Process all is checked - disable limit entry
            self.limit_entry.config(state=tk.DISABLED, disabledbackground='#5a5a5a')
            self.limit_label.config(fg='#95a5a6')  # Gray out the label
            self.sprites_label.config(fg='#95a5a6')  # Gray out the label
        else:
            # Process all is unchecked - enable limit entry
            self.limit_entry.config(state=tk.NORMAL, bg='#4a4a4a', fg='#e0e0e0', insertbackground='#e0e0e0')
            self.limit_label.config(fg='#e0e0e0')  # Normal color
            self.sprites_label.config(fg='#e0e0e0')  # Normal color
    
    def toggle_log_dir(self):
        """Toggle log directory entry state"""
        if self.use_custom_log_dir.get():
            self.log_entry.config(state=tk.NORMAL, bg='#4a4a4a', fg='#e0e0e0', insertbackground='#e0e0e0')
            self.log_browse_btn.config(state=tk.NORMAL, bg='#555555')
        else:
            self.log_entry.config(state=tk.DISABLED, disabledbackground='#5a5a5a')
            self.log_browse_btn.config(state=tk.DISABLED, bg='#555555')
    
    def on_directory_change(self, *args):
        """Called when directory paths change - trigger file detection"""
        # Skip during initial setup to prevent duplicate detection
        if self.initial_setup:
            return
        
        # Disable start button since directory change invalidates current analysis
        self.start_button.config(state=tk.DISABLED)
        
        # Only run analysis if all three directories are selected
        if not (self.move_dir.get().strip() and 
                self.sprite_dir.get().strip() and 
                self.output_dir.get().strip()):
            return
        
        # Cancel any pending detection to prevent race conditions
        if hasattr(self, '_detect_job') and self._detect_job:
            try:
                self.root.after_cancel(self._detect_job)
            except:
                pass
            
        # Prevent double execution with debounce
        if not self.detect_files_scheduled:
            self.detect_files_scheduled = True
            self._detect_job = self.root.after(200, self._delayed_detect_files)
    
    def _delayed_detect_files(self):
        """Delayed file detection to prevent double execution"""
        self.detect_files_scheduled = False
        # Run file detection in a separate thread to prevent UI freezing
        import threading
        detection_thread = threading.Thread(target=self.detect_files, daemon=True)
        detection_thread.start()
    
    def initial_detect_files(self):
        """Initial file detection on startup - only run if directories are set"""
        # Only run initial detection if directories are actually set (not empty)
        if (self.move_dir.get().strip() and 
            self.sprite_dir.get().strip() and 
            self.output_dir.get().strip()):
            
            # Check if analysis is already running
            if self.analysis_running:
                return
            
            # Use the same validation chain as refresh_analysis
            validation_errors = self.validate_directories_for_analysis()
            if validation_errors:
                # Don't run analysis if validation fails
                return
            
            # Set analysis running flag and disable buttons (same as refresh_analysis)
            self.analysis_running = True
            self.file_detection_complete = False  # Reset file detection completion flag
            self.refresh_btn.config(state=tk.DISABLED)
            self.start_button.config(state=tk.DISABLED)
            
            # Clear the log console for fresh startup experience
            # self.log_text.delete(1.0, tk.END)  # Disabled for testing
            
            # Run file detection in a separate thread to prevent UI freezing (progress bar will be started in detect_files if needed)
            import threading
            detection_thread = threading.Thread(target=self.detect_files, daemon=True)
            detection_thread.start()
        
        # Clear the initial setup flag to enable directory change detection
        self.initial_setup = False
    
    
    
    def get_sprite_variant_type(self, filename):
        """Get the sprite variant type: 'normal' or 'shiny'"""
        if '-n.' in filename:
            return 'normal'
        elif '-s.' in filename:
            return 'shiny'
        else:
            return 'unknown'
    
    def get_sprite_direction_type(self, filename):
        """Get the sprite direction type (front, back, or normal) from filename"""
        if '-front-' in filename:
            return 'front'
        elif '-back-' in filename:
            return 'back'
        elif '-normal-' in filename:
            return 'normal'
        else:
            return 'unknown'
    
    def same_sprite_variant_type(self, filename1, filename2):
        """Check if two filenames have the same sprite variant type (normal vs shiny)"""
        type1 = self.get_sprite_variant_type(filename1)
        type2 = self.get_sprite_variant_type(filename2)
        return type1 == type2 and type1 != 'unknown'
    
    
    def refresh_analysis(self):
        """Refresh analysis with background processing and progress bar"""
        
        # Check if analysis is already running
        if self.analysis_running:
            return
        
        # Smart validation before starting analysis
        validation_errors = self.validate_directories_for_analysis()
        if validation_errors:
            # Show validation errors and don't start analysis
            error_message = "\n".join(validation_errors)
            messagebox.showerror("Directory Validation Failed", error_message)
            return
        
        # Set analysis running flag and disable buttons
        self.analysis_running = True
        self.file_detection_complete = False  # Reset file detection completion flag
        self.refresh_btn.config(state=tk.DISABLED)
        self.start_button.config(state=tk.DISABLED)
        
        # Clear the log console for fresh experience
        self.clear_logs()
        
        # Run analysis in background thread (progress bar will be started in detect_files if needed)
        import threading
        analysis_thread = threading.Thread(target=self.detect_files, daemon=True)
        analysis_thread.start()
    
    def detect_files(self):
        """
        Detect and validate sprite files in all directories with comprehensive error handling.
        
        This method performs the core file analysis that drives the entire application.
        It analyzes sprite files, generates recommendations, and prepares the system
        for processing.
        
        Process:
        1. Validates directory paths and checks for conflicts
        2. Scans for sprite files in Bullseye and custom directories
        3. Performs comprehensive file analysis and matching
        4. Generates file operation recommendations
        5. Creates unfulfilled files data structure
        6. Updates UI with analysis results
        
        The method runs in a background thread to prevent UI blocking and includes
        comprehensive error handling for various failure scenarios.
        
        Raises:
            Various exceptions are caught and logged, with graceful degradation
            to ensure the application remains functional even if analysis fails.
        """
        try:
            # Clear the log output at the start of analysis
            self.clear_logs()
            
            # Disable buttons during analysis (already done in refresh_analysis)
            self.unfulfilled_button.config(state=tk.DISABLED)
            
            # Update status to show we're working
            self.root.after(0, lambda: self.status_var.set("🔍 Analyzing files..."))
            
            # Start progress bar immediately for visual feedback (ensure it runs on main thread)
            self.root.after_idle(lambda: self.start_animated_progress())
            
            # Initialize error tracking
            self.detection_errors = []
            self.recovery_actions = []
            
            warning_summary = []
            warning_details = []
            info_summary = []
            info_details = []
            success_summary = []

            bullseye_dir = Path(self.move_dir.get()) if self.move_dir.get() else None
            replacement_dir = Path(self.sprite_dir.get()) if self.sprite_dir.get() else None
            output_dir = Path(self.output_dir.get()) if self.output_dir.get() else None
            
            # Directory validation is now handled by validate_directories_for_analysis()
            # which is called before detect_files() starts, so we can proceed directly
            
            # Debug logging (commented out to reduce log clutter)
            # self.log_message(f"DEBUG: Checking directories - Bullseye: {bullseye_dir}, Replacement: {replacement_dir}, Output: {output_dir}", "INFO")
            
            bullseye_files = set()
            replacement_files = set()
            output_files = set()
            
            # Check bullseye directory
            if bullseye_dir and bullseye_dir.exists():
                bullseye_files = set(f.name for f in bullseye_dir.glob("*.gif")) | set(f.name for f in bullseye_dir.glob("*.png"))
                if bullseye_files:
                    info_summary.append(f"Found {len(bullseye_files)} bullseye sprites")
                else:
                    warning_summary.append("No bullseye sprites found")
            elif bullseye_dir:
                warning_summary.append("Bullseye directory does not exist")
            
            # Exit if no valid sprite files found (need at least one valid sprite)
            if not bullseye_files:
                self.log_message("⚠️ No bullseye sprites found - please select a directory with Bullseye sprite files", "WARNING")
                self.log_message("💡 Analysis skipped - nothing to process", "INFO")
                self.analysis_running = False
                self.root.after(0, lambda: self.start_button.config(state=tk.DISABLED))
                self.root.after(0, lambda: self.refresh_btn.config(state=tk.NORMAL))
                return
            
            # Check replacement directory
            if replacement_dir and replacement_dir.exists():
                replacement_files = set(f.name for f in replacement_dir.glob("*.gif")) | set(f.name for f in replacement_dir.glob("*.png"))
                if replacement_files:
                    info_summary.append(f"Found {len(replacement_files)} replacement sprites")
                else:
                    warning_summary.append("No replacement sprites found")
            elif replacement_dir:
                warning_summary.append("Replacement directory does not exist")
            
            # Exit if no valid sprite files found (need at least one valid sprite)
            if not replacement_files:
                self.log_message("⚠️ No replacement sprites found - please select a directory with sprite files", "WARNING")
                self.log_message("💡 Analysis skipped - nothing to process", "INFO")
                self.analysis_running = False
                self.root.after(0, lambda: self.start_button.config(state=tk.DISABLED))
                self.root.after(0, lambda: self.refresh_btn.config(state=tk.NORMAL))
                return
            
            # Check output directory
            if output_dir and output_dir.exists():
                # Check for existing .mod files in output directory
                mod_files = list(output_dir.glob("*.mod"))
                if mod_files:
                    info_summary.append(f"{len(mod_files)} existing .mod files in output")
                else:
                    info_summary.append("Output directory empty; new .mod will be created")
            elif output_dir:
                warning_summary.append("Output directory does not exist (will be created)")
            
            
            # Only do comparison if both input directories have files
            if bullseye_files and replacement_files:
                # Simple file matching for basic statistics
                matches = set()
                for bullseye_file in bullseye_files:
                    if bullseye_file in replacement_files:
                        matches.add(bullseye_file)
                
                # Log basic file information
                if len(matches) == len(bullseye_files):
                    success_summary.append(f"✅ {len(matches)}/{len(bullseye_files)} bullseye files fulfilled")
                else:
                    warning_summary.append(f"⚠️ {len(matches)}/{len(bullseye_files)} bullseye files fulfilled")
                
                # Count back files
                all_back_files = [f for f in replacement_files if '-back-' in f]
                if all_back_files and len(all_back_files) > 5:
                    info_summary.append(f"{len(all_back_files)} back files (will be resized)")
                    
                # Back files fulfillment will be calculated after comprehensive analysis
                
                # Analyze output directory impact
                if output_dir:
                    self.analyze_output_impact(matches, output_files, len(bullseye_files))
                    
                    
                # Set up for comprehensive analysis
                max_recommendations = 999999
                    
                # COMPREHENSIVE BULLSEYE FULFILLMENT ANALYSIS - CALL IT HERE IN MAIN METHOD
                
                try:
                    
                    # Force flush the output
                    import sys
                    if sys.stdout:
                        sys.stdout.flush()
                    
                    bullseye_fulfillment_recommendations = self.analyze_bullseye_fulfillment_comprehensive(bullseye_files, replacement_files, max_recommendations)
                    
                    
                    if sys.stdout:
                        sys.stdout.flush()
                except Exception as e:
                    self.log_message(f"Error in comprehensive analysis: {e}", "ERROR")
                    import traceback
                    traceback.print_exc()
                    bullseye_fulfillment_recommendations = []
                
                # Use the comprehensive recommendations instead of the empty ones
                all_recommendations = bullseye_fulfillment_recommendations
                
                # Always store current file data for popups and processing
                self.current_bullseye_files = bullseye_files
                self.current_replacement_files = replacement_files
                self.current_matches = matches
                self.current_back_file_matches = set()  # Initialize empty set
                
                # Store recommendations
                self.current_recommendations = all_recommendations
                
                # Calculate back files fulfillment - simple and direct approach
                # 1. Take all front files that bullseye needs
                # 2. Convert each to its corresponding back file name  
                # 3. Check which of those back files we actually have
                required_back_files = set()
                for front_file in bullseye_files:
                    back_file = front_file.replace('-front-', '-back-')
                    required_back_files.add(back_file)
                
                # Count how many of the required back files we actually have
                fulfilled_back_files = []
                unfulfilled_back_files = []
                for required_back_file in required_back_files:
                    if required_back_file in replacement_files:
                        fulfilled_back_files.append(required_back_file)
                    else:
                        unfulfilled_back_files.append(required_back_file)
                
                if required_back_files:
                    if len(fulfilled_back_files) == len(required_back_files):
                        success_summary.append(f"✅ {len(fulfilled_back_files)}/{len(required_back_files)} back files fulfilled")
                    else:
                        warning_summary.append(f"⚠️ {len(fulfilled_back_files)}/{len(required_back_files)} back files fulfilled")
                
                # Debug: Show some examples of recommendations before consolidation
                
                # Consolidation disabled - new system generates simple operations that don't need consolidation
                # self.current_recommendations = self.consolidate_recommendations(self.current_recommendations)
                
                
                
                
                # Create unfulfilled_files data structure for the Issues tabs
                self.unfulfilled_files = {}
                
                # Method 1: Get unfulfilled files from recommendations (these are definitely unfulfilled and fixable)
                for rec in self.current_recommendations:
                    # Files mentioned in recommendations are unfulfilled and fixable
                    if isinstance(rec.get('to'), list):
                        # For operations that create multiple files
                        for target_file in rec['to']:
                            if target_file not in self.unfulfilled_files:
                                self.unfulfilled_files[target_file] = True  # Fixable
                                if '403-front-s.gif' in target_file:
                                    pass  # Debug check removed
                    elif rec.get('to'):
                        # For operations that create a single file
                        target_file = rec['to']
                        if target_file not in self.unfulfilled_files:
                            self.unfulfilled_files[target_file] = True  # Fixable
                            if '403-front-s.gif' in target_file:
                                pass  # Debug check removed
                
                # Method 2: DISABLED - Using new comprehensive system instead
                # The old system using normalize_filename has been replaced by analyze_bullseye_fulfillment_comprehensive
                
                # Method 3: Add missing back files (these are not fixable)
                if hasattr(self, 'current_unfulfilled_back_files'):
                    for back_file in self.current_unfulfilled_back_files:
                        # Skip if already found in recommendations or bullseye files
                        if back_file not in self.unfulfilled_files:
                            self.unfulfilled_files[back_file] = False  # Not fixable
                else:
                    pass  # No current_unfulfilled_back_files attribute found
                
                # Method 4: Add unfulfilled files from analysis (files that cannot be fulfilled)
                if hasattr(self, 'unfulfilled_files_from_analysis'):
                    for unfulfilled_file in self.unfulfilled_files_from_analysis:
                        if unfulfilled_file not in self.unfulfilled_files:
                            self.unfulfilled_files[unfulfilled_file] = False  # Not fixable
                else:
                    pass  # No unfulfilled_files_from_analysis attribute found
                
            
            # Check for missing required directories
            self.check_missing_directories(bullseye_dir, replacement_dir, output_dir)
            
            # Update file count display (compact)
            matches_count = len(matches) if bullseye_files and replacement_files else 0
            self.file_count_var.set(f"Files: B:{len(bullseye_files)} R:{len(replacement_files)} M:{matches_count} O:{len(output_files)}")
            
            # Consolidated logging at the end - organized flow
            # 1. File counts and basic info
            if info_summary:
                self.log_message(f"ℹ️ {'; '.join(info_summary)}", "INFO")
                for detail in info_details:
                    self.log_message(detail, "INFO")
            
            # 2. Critical errors (RED) - only for blocking issues
            if hasattr(self, 'pending_validation_issues'):
                validation_issues = self.pending_validation_issues
                critical_errors = []
                
                # Only show critical errors for blocking issues
                if validation_issues.get('base_conflicts'):
                    critical_errors.append(f"{len(validation_issues['base_conflicts'])} file conflicts")
                if validation_issues.get('back_base_conflicts'):
                    critical_errors.append(f"{len(validation_issues['back_base_conflicts'])} back file conflicts")
                
                if critical_errors:
                    self.log_message(f"❌ CRITICAL: {'; '.join(critical_errors)}", "ERROR")
            
            # 3. Warnings (YELLOW) - issues that should be addressed
            warning_items = list(warning_summary) if warning_summary else []
            
            # Add validation warnings to the warning summary
            if hasattr(self, 'pending_validation_issues'):
                validation_issues = self.pending_validation_issues
                if validation_issues.get('incomplete_variants'):
                    warning_items.append(f"{len(validation_issues['incomplete_variants'])} missing gender variants")
                if validation_issues.get('back_incomplete_variants'):
                    warning_items.append(f"{len(validation_issues['back_incomplete_variants'])} missing back variants")
            
            if warning_items:
                for warning_item in warning_items:
                    self.log_message(warning_item, "WARNING")
                for detail in warning_details:
                    self.log_message(detail, "WARNING")
            
            # Show success messages separately
            if success_summary:
                for success_msg in success_summary:
                    self.log_message(success_msg, "SUCCESS")
            
            # Show unfulfilled files count right after the files fulfilled warning
            if hasattr(self, 'unfulfilled_files') and self.unfulfilled_files:
                unfulfilled_count = len(self.unfulfilled_files)
                self.log_message(f"❌ {unfulfilled_count} files are unfulfilled", "ERROR")
            
            # 4. Recommendations summary
            if hasattr(self, 'current_recommendations') and self.current_recommendations:
                rec_count = len(self.current_recommendations)
                # Always use ERROR level (red) for auto-fix suggestions to make them prominent
                self.log_message(f"❌ {rec_count} auto-fix suggestions available! Click 'Fix Issues' to review and apply fixes.", "ERROR")
            
            # Stop animated progress now that ALL processing is complete
            self.stop_animated_progress()
            
            # Re-enable buttons after analysis completes
            self.analysis_running = False
            self.file_detection_complete = True  # Mark file detection as complete
            self.root.after(0, lambda: self.refresh_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.unfulfilled_button.config(state=tk.NORMAL))
            
            # Enable start button only if we have valid analysis results
            
            has_recommendations = hasattr(self, 'current_recommendations') and self.current_recommendations
            has_unfulfilled = hasattr(self, 'unfulfilled_files') and self.unfulfilled_files
            
            # Always show fulfilled file count
            fulfilled_count = len(self.current_recommendations) if has_recommendations else 0
            unfulfilled_count = len(self.unfulfilled_files) if has_unfulfilled else 0
            
            if has_recommendations:
                # We have fixes to apply
                self.root.after(0, lambda: self.start_button.config(state=tk.NORMAL))
                self.log_message("✅ Analysis complete", "SUCCESS")
                # Preload issues tabs in background for faster access
                self.root.after(100, self.preload_issues_tabs)
                
                # 5. Final status - Ready to process message comes AFTER analysis complete
                if bullseye_dir and replacement_dir and output_dir:
                    self.log_message("✅ Ready to process", "INFO")
            elif not has_unfulfilled:
                # No recommendations and no unfulfilled files = everything is perfect
                self.root.after(0, lambda: self.start_button.config(state=tk.NORMAL))
                self.log_message("✅ Analysis complete - no fixes needed", "SUCCESS")
                # 5. Final status - Ready to process message comes AFTER analysis complete
                if bullseye_dir and replacement_dir and output_dir:
                    self.log_message("✅ Ready to process", "INFO")
            else:
                # No recommendations but there are unfulfilled files = can't fix anything more
                self.root.after(0, lambda: self.start_button.config(state=tk.NORMAL))
                self.log_message("✅ Analysis complete - no additional fixes available", "SUCCESS")
                # 5. Final status - Ready to process message comes AFTER analysis complete
                if bullseye_dir and replacement_dir and output_dir:
                    self.log_message("✅ Ready to process", "INFO")
        
        except Exception as e:
            import traceback
            error_type = type(e).__name__
            error_msg = str(e)
            
            # Log the error with context
            self.log_message(f"❌ ERROR: File detection failed with exception: {error_type}", "ERROR")
            self.log_message(f"❌ ERROR: {error_msg}", "ERROR")
            
            # Add to error tracking
            self.detection_errors.append({
                'type': error_type,
                'message': error_msg,
                'timestamp': datetime.now().strftime("%H:%M:%S"),
                'context': 'file_detection'
            })
            
            # Attempt recovery based on error type
            recovery_suggestion = self.get_recovery_suggestion(error_type, error_msg)
            if recovery_suggestion:
                self.log_message(f"💡 RECOVERY: {recovery_suggestion}", "INFO")
                self.recovery_actions.append(recovery_suggestion)
            
            # Log detailed traceback for debugging
            self.log_message("❌ ERROR: File detection traceback:", "ERROR")
            for line in traceback.format_exc().split('\n'):
                if line.strip():
                    self.log_message(f"    {line}", "ERROR")
            
            # Update status to show error
            self.root.after(0, lambda: self.status_var.set("❌ Analysis failed"))
            
            # Stop progress bar and re-enable buttons even if analysis failed
            self.analysis_running = False
            self.file_detection_complete = True  # Mark file detection as complete (even if failed)
            self.stop_animated_progress()
            self.root.after(0, lambda: self.refresh_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.unfulfilled_button.config(state=tk.NORMAL))
            
            # Keep start button disabled on analysis failure
            self.root.after(0, lambda: self.start_button.config(state=tk.DISABLED))
    
    def _files_are_related(self, file1, file2):
        """Check if two files are related (same dex/direction/variant)"""
        try:
            # Parse both filenames
            parts1 = file1.split('-')
            parts2 = file2.split('-')
            
            if len(parts1) < 3 or len(parts2) < 3:
                return False
            
            # Check if they have the same dex number and direction
            dex1 = parts1[0]
            direction1 = parts1[1]
            dex2 = parts2[0]
            direction2 = parts2[1]
            
            # Must have same dex number and direction
            if dex1 != dex2 or direction1 != direction2:
                return False
            
            # Additional logic: if one is a base file and the other is a variant of the same type
            # This helps match operations like "create variants from base" with "remove unneeded variants"
            
            # Extract variant info
            variant1 = parts1[2] if len(parts1) > 2 else ""
            variant2 = parts2[2] if len(parts2) > 2 else ""
            
            # Extract gender info
            gender1 = parts1[3] if len(parts1) > 3 else ""
            gender2 = parts2[3] if len(parts2) > 3 else ""
            
            # If both have the same variant (e.g., both are 's' or both are 'n')
            if variant1 == variant2:
                return True
            
            # If one is base (no gender) and the other is a variant of the same direction
            if (not gender1 and gender2) or (gender1 and not gender2):
                return True
            
            # If both have gender variants but different genders, they're related
            if gender1 and gender2 and gender1 != gender2:
                return True
            
            return False
        except:
            return False

    def get_recovery_suggestion(self, error_type, error_msg):
        """Get recovery suggestions based on error type and message"""
        recovery_suggestions = {
            'FileNotFoundError': "Check that all directory paths are correct and accessible",
            'PermissionError': "Ensure you have read/write permissions for all directories",
            'OSError': "Check disk space and file system integrity",
            'MemoryError': "Try processing smaller batches or close other applications",
            'UnicodeDecodeError': "Check for files with invalid characters in names",
            'ValueError': "Verify file formats and naming conventions",
            'KeyError': "Check for missing configuration or corrupted settings",
            'AttributeError': "This may indicate a code issue - try restarting the application"
        }
        
        # Check for specific error patterns
        if 'directory' in error_msg.lower():
            return "Verify that all selected directories exist and are accessible"
        elif 'permission' in error_msg.lower():
            return "Run as administrator or check file permissions"
        elif 'space' in error_msg.lower():
            return "Free up disk space and try again"
        elif 'format' in error_msg.lower():
            return "Check that all files are valid GIF or PNG format"
        
        return recovery_suggestions.get(error_type, "Try restarting the application or check the log for more details")
    
    
    
    
    def analyze_bullseye_fulfillment_comprehensive(self, bullseye_files, replacement_files, max_recommendations=999999):
        """
        Comprehensive Bullseye fulfillment analysis engine.
        
        This method performs intelligent analysis of sprite files to determine what operations
        are needed to fulfill Bullseye mod requirements. It handles various file matching
        scenarios and generates appropriate recommendations.
        
        Args:
            bullseye_files (set): Set of sprite files required by Bullseye mod
            replacement_files (set): Set of available custom sprite files
            max_recommendations (int): Maximum number of recommendations to generate
            
        Returns:
            list: List of file operation recommendations
            
        The analysis includes:
        - Case sensitivity fixes (e.g., "Front" -> "front")
        - Extension normalization (e.g., "..gif" -> ".gif")
        - Gender variant creation from base files
        - Base file creation from gender variants
        - Cross-naming compatibility (front/back/normal)
        - Comprehensive operations for paired files
        - Cleanup of unnecessary files
        
        The method uses a multi-phase approach:
        1. Simple fixes (case, extensions, malformed files)
        2. Missing file analysis and source identification
        3. Gender variant and base file operations
        4. Cleanup of leftover files
        """
        # Comprehensive analysis started
        
        recommendations = []
        unfulfilled_files = []  # Track files that cannot be fulfilled
        
        # PHASE 1: Simple fixes
        
        # PHASE 1: Handle simple fixes first (case sensitivity, malformed files, extensions)
        for replacement_file in replacement_files:
            if len(recommendations) >= max_recommendations:
                break
                
            # Check for all types of file fixes
            fixes = self.check_file_fixes(replacement_file, bullseye_files)
            if fixes:
                # Add the first fix found (prioritize the most important ones)
                recommendations.extend(fixes)
                continue
        
        # PHASE 1 completed
        
        # PHASE 2: Simple, direct mapping for missing files
        # First, simulate what files will exist after ALL operations (rename, create, cleanup)
        files_after_operations = set(replacement_files)
        for rec in recommendations:
            if rec.get('action') == 'rename':
                files_after_operations.discard(rec.get('from'))
                files_after_operations.add(rec.get('to'))
            elif rec.get('action') in ['create_gender_variant', 'create_gender_variant_from_other', 'create_base_from_male', 'create_base_from_female', 'clone']:
                # These operations create new files
                if rec.get('to'):
                    # Handle both single files and lists of files (comprehensive operations)
                    if isinstance(rec.get('to'), list):
                        for target_file in rec.get('to'):
                            files_after_operations.add(target_file)
                    else:
                        files_after_operations.add(rec.get('to'))
            elif rec.get('action') == 'cleanup':
                # These operations remove files
                cleanup_files = rec.get('cleanup_files', [rec.get('from')])
                for cleanup_file in cleanup_files:
                    files_after_operations.discard(cleanup_file)
            elif rec.get('action') in ['remove', 'remove_base']:
                # These operations remove files
                files_after_operations.discard(rec.get('from'))
        
        # Find missing files (Bullseye needs but doesn't have after all operations)
        missing_files = set()
        # Checking bullseye files against available files
        for bullseye_file in bullseye_files:
            # Check if this file exists in replacement files (exact match) or will exist after all operations
            if bullseye_file not in files_after_operations:
                missing_files.add(bullseye_file)
        # Found directly missing bullseye files
        
        # PHASE 2.5: Back files detection
        
        # PHASE 2.5: Check for missing back files
        # Every front file that Bullseye requires should have a corresponding back file
        # Starting back files detection
        back_files_missing = set()
        
        # First, check for missing back files that Bullseye actually requires
        front_files_in_bullseye = 0
        for bullseye_file in bullseye_files:
            if '-front-' in bullseye_file:
                front_files_in_bullseye += 1
                # Bullseye needs this front file, so it also needs the corresponding back file
                back_file = bullseye_file.replace('-front-', '-back-')
                # Add to missing if we don't have the corresponding back file
                if back_file not in files_after_operations:
                    # We don't have the corresponding back file that Bullseye needs
                    back_files_missing.add(back_file)
        
        # Also check for missing back files for existing front files we have
        front_files_we_have = 0
        for replacement_file in files_after_operations:
            if '-front-' in replacement_file:
                front_files_we_have += 1
                # This is a front file we have, it should have a corresponding back file
                back_file = replacement_file.replace('-front-', '-back-')
                # Only add to missing if we don't have the corresponding back file
                # AND Bullseye actually needs this specific back file
                if back_file not in files_after_operations and back_file in bullseye_files:
                    # We don't have the corresponding back file that Bullseye needs - add it to missing files
                    back_files_missing.add(back_file)
        
        # Debug logging removed
        
        missing_files.update(back_files_missing)
        # Missing files updated with back files
        
        
        # For each missing file, find a source to create it from
        for missing_file in missing_files:
            if len(recommendations) >= max_recommendations:
                # Reached max recommendations limit
                break
                
            # Parse the missing file
            components = self.parse_sprite_filename(missing_file)
            if not components:
                continue
                
            dex = components['dex']
            direction = components['direction']
            variant = components['variant']
            gender = components['gender']
            
            can_fulfill = False
            
            if gender:
                # This is a gender variant (e.g., 019-front-n-f.gif)
                # Check if Bullseye actually needs this gender variant (or the corresponding file)
                should_create = False
                if missing_file in bullseye_files:
                    should_create = True
                    # Bullseye directly needs this file
                elif '-back-' in missing_file:
                    # For back files, check if Bullseye needs the corresponding front file
                    # OR if the corresponding front file already exists as a source file
                    corresponding_front_file = missing_file.replace('-back-', '-front-')
                    # Checking if we should create this back file
                    
                    # For back files, ONLY create gender variants if Bullseye needs the EXACT SPECIFIC corresponding front file
                    # This ensures that normal and shiny files are handled separately and identically
                    if corresponding_front_file in bullseye_files:
                        should_create = True
                        # Should create back gender variant
                    else:
                        # Additional check: Only create gender variants if we can create them from a base file
                        # AND Bullseye needs the corresponding gender variant front file
                        base_back_file = missing_file.replace('-m.gif', '.gif').replace('-f.gif', '.gif')
                        
                        # Only create if:
                        # 1. We have the base back file
                        # 2. Bullseye needs the corresponding gender variant front file (not just any front file)
                        if (base_back_file in replacement_files and 
                            corresponding_front_file in bullseye_files):
                            should_create = True
                            # Should create back gender variant from base file
                        else:
                            should_create = False
                            # Don't need back gender variant
                
                if should_create:
                    # Look for base file of the SAME direction and variant type
                    # Determine file extension from existing files
                    file_ext = ".gif"  # Default
                    if replacement_files:
                        # Find a file with the same dex, direction, and variant to get extension
                        for existing_file in replacement_files:
                            if existing_file.startswith(f"{dex:03d}-{direction}-{variant}"):
                                if existing_file.endswith('.png'):
                                    file_ext = ".png"
                                break
                    
                    base_file = f"{dex:03d}-{direction}-{variant}{file_ext}"
                    # Looking for base file to create gender variant
                    # Check in replacement_files first (what we actually have), then files_after_operations
                    if base_file in replacement_files or base_file in files_after_operations:
                        # Create comprehensive operation that handles both front and back files
                        paired_file = None
                        paired_base_file = None
                        
                        if direction == 'front':
                            paired_file = f"{dex:03d}-back-{variant}-{gender}{file_ext}"
                            paired_base_file = f"{dex:03d}-back-{variant}{file_ext}"
                        else:
                            paired_file = f"{dex:03d}-front-{variant}-{gender}{file_ext}"
                            paired_base_file = f"{dex:03d}-front-{variant}{file_ext}"
                        
                        # Check if the paired file is also missing and if we have the paired base file
                        # Create comprehensive operation if we have both base files and the paired file doesn't exist
                        if (paired_file not in files_after_operations and
                            paired_base_file in files_after_operations):
                            # Both files are missing and we have both base files - create comprehensive operation
                            operation = {
                                'action': 'create_gender_variant',
                                'from': [base_file, paired_base_file],
                                'to': [missing_file, paired_file],
                                'reason': f'Create both gender variants from base files'
                            }
                        else:
                            # Only create the specific missing file
                            operation = {
                                'action': 'create_gender_variant',
                                'from': base_file,
                                'to': missing_file,
                                'reason': f'Create gender variant from base file'
                            }
                        
                        recommendations.append(operation)
                        can_fulfill = True
                        # Creating gender variant from base file
                    else:
                        can_fulfill = False
                        # Cannot create gender variant - no base file available
                else:
                    should_create = False
                    # Skipping gender variant creation - Bullseye doesn't need this
                
                # Fallback: Look for the other gender variant of the SAME direction and variant type
                if not can_fulfill and should_create:
                    if gender == 'm':
                        other_gender_file = f"{dex:03d}-{direction}-{variant}-f.gif"
                        other_gender = 'female'
                    else:  # gender == 'f'
                        other_gender_file = f"{dex:03d}-{direction}-{variant}-m.gif"
                        other_gender = 'male'
                    
                    # Looking for other gender file to create this one
                    if other_gender_file in replacement_files or other_gender_file in files_after_operations:
                        # Create comprehensive operation that handles both front and back files
                        paired_file = None
                        paired_other_gender_file = None
                        
                        if direction == 'front':
                            paired_file = f"{dex:03d}-back-{variant}-{gender}.gif"
                            paired_other_gender_file = f"{dex:03d}-back-{variant}-{other_gender[0]}.gif"
                        else:
                            paired_file = f"{dex:03d}-front-{variant}-{gender}.gif"
                            paired_other_gender_file = f"{dex:03d}-front-{variant}-{other_gender[0]}.gif"
                        
                        # Check if the paired file is also missing and if we have the paired other gender file
                        # Create comprehensive operation if we have both other gender files and the paired file doesn't exist
                        if (paired_file not in files_after_operations and 
                            paired_other_gender_file in files_after_operations):
                            # Both files are missing and we have both other gender files - create comprehensive operation
                            operation = {
                                'action': 'create_gender_variant_from_other',
                                'from': [other_gender_file, paired_other_gender_file],
                                'to': [missing_file, paired_file],
                                'reason': f'Create both gender variants from {other_gender} variants (base files not available)'
                            }
                        else:
                            # Only create the specific missing file
                            operation = {
                                'action': 'create_gender_variant_from_other',
                                'from': other_gender_file,
                                'to': missing_file,
                                'reason': f'Create gender variant from {other_gender} variant (base file not available)'
                            }
                        
                        recommendations.append(operation)
                        can_fulfill = True
                        # Can create from other gender variant
            
            else:
                # This is a base file (e.g., 019-front-n.gif)
                
                # Only create base files from gender variants if Bullseye actually needs the base file
                # and we don't have a better source (like another base file)
                
                # Look for male/female variants of the SAME direction and variant type
                # Determine file extension from existing files
                file_ext = ".gif"  # Default
                if replacement_files:
                    # Find a file with the same dex, direction, and variant to get extension
                    for existing_file in replacement_files:
                        if existing_file.startswith(f"{dex:03d}-{direction}-{variant}"):
                            if existing_file.endswith('.png'):
                                file_ext = ".png"
                            break
                
                male_file = f"{dex:03d}-{direction}-{variant}-m{file_ext}"
                female_file = f"{dex:03d}-{direction}-{variant}-f{file_ext}"
                # Looking for male and female variants
                
                if male_file in files_after_operations:
                    # Only create base file from gender variant if Bullseye actually needs the base file
                    # For back files, check if the corresponding front file is needed by Bullseye
                    if missing_file not in bullseye_files:
                        # Check if this is a back file and if the corresponding front file is needed
                        if '-back-' in missing_file:
                            corresponding_front_file = missing_file.replace('-back-', '-front-')
                            if corresponding_front_file not in bullseye_files:
                                # Skipping - Bullseye doesn't need corresponding front file
                                continue
                        else:
                            # Skipping - Bullseye doesn't need this base file
                            continue
                    
                    # Create comprehensive operation that handles both front and back files
                    paired_file = None
                    paired_male_file = None
                    
                    if direction == 'front':
                        paired_file = f"{dex:03d}-back-{variant}.gif"
                        paired_male_file = f"{dex:03d}-back-{variant}-m.gif"
                    else:
                        paired_file = f"{dex:03d}-front-{variant}.gif"
                        paired_male_file = f"{dex:03d}-front-{variant}-m.gif"
                    
                    # Check if the paired file is also missing and if we have the paired male file
                    # Create comprehensive operation if we have both male files and the paired file doesn't exist
                    if (paired_file not in files_after_operations and 
                        paired_male_file in files_after_operations):
                        # Both files are missing and we have both male files - create comprehensive operation
                        operation = {
                            'action': 'create_base_from_male',
                            'from': [male_file, paired_male_file],
                            'to': [missing_file, paired_file],
                            'reason': f'Create both base files from male variants'
                        }
                    else:
                        # Only create the specific missing file
                        operation = {
                            'action': 'create_base_from_male',
                            'from': male_file,
                            'to': missing_file,
                            'reason': f'Create base file from male variant'
                        }
                        # Creating single operation from male file
                    
                    recommendations.append(operation)
                    can_fulfill = True
                    # Can create from male file
                elif female_file in files_after_operations:
                    # Only create base file from gender variant if Bullseye actually needs the base file
                    # For back files, check if the corresponding front file is needed by Bullseye
                    if missing_file not in bullseye_files:
                        # Check if this is a back file and if the corresponding front file is needed
                        if '-back-' in missing_file:
                            corresponding_front_file = missing_file.replace('-back-', '-front-')
                            if corresponding_front_file not in bullseye_files:
                                # Skipping - Bullseye doesn't need corresponding front file
                                continue
                        else:
                            # Skipping - Bullseye doesn't need this base file
                            continue
                    
                    # Create comprehensive operation that handles both front and back files
                    paired_file = None
                    paired_female_file = None
                    
                    if direction == 'front':
                        paired_file = f"{dex:03d}-back-{variant}.gif"
                        paired_female_file = f"{dex:03d}-back-{variant}-f.gif"
                    else:
                        paired_file = f"{dex:03d}-front-{variant}.gif"
                        paired_female_file = f"{dex:03d}-front-{variant}-f.gif"
                    
                    # Check if the paired file is also missing and if we have the paired female file
                    # Create comprehensive operation if we have both female files and the paired file doesn't exist
                    if (paired_file not in files_after_operations and 
                        paired_female_file in files_after_operations):
                        # Both files are missing and we have both female files - create comprehensive operation
                        operation = {
                            'action': 'create_base_from_female',
                            'from': [female_file, paired_female_file],
                            'to': [missing_file, paired_file],
                            'reason': f'Create both base files from female variants'
                        }
                    else:
                        # Only create the specific missing file
                        operation = {
                            'action': 'create_base_from_female',
                            'from': female_file,
                            'to': missing_file,
                            'reason': f'Create base file from female variant'
                        }
                        # Creating single operation from female file
                    
                    recommendations.append(operation)
                    can_fulfill = True
                    # Can create from female file
            
            if not can_fulfill:
                # Cannot fulfill - no source found
                unfulfilled_files.append(missing_file)
        
        # PHASE 3: Simple cleanup - collect files that need to be removed
        files_to_cleanup = []
        
        # Recalculate files_after_operations to include ALL operations (including newly generated ones)
        files_after_operations = set(replacement_files)
        for rec in recommendations:
            if rec.get('action') == 'rename':
                files_after_operations.discard(rec.get('from'))
                files_after_operations.add(rec.get('to'))
            elif rec.get('action') in ['create_gender_variant', 'create_gender_variant_from_other', 'create_base_from_male', 'create_base_from_female', 'clone']:
                # These operations create new files
                if rec.get('to'):
                    # Handle both single files and lists of files (comprehensive operations)
                    if isinstance(rec.get('to'), list):
                        for target_file in rec.get('to'):
                            files_after_operations.add(target_file)
                    else:
                        files_after_operations.add(rec.get('to'))
            elif rec.get('action') == 'cleanup':
                # These operations remove files
                cleanup_files = rec.get('cleanup_files', [rec.get('from')])
                for cleanup_file in cleanup_files:
                    files_after_operations.discard(cleanup_file)
            elif rec.get('action') in ['remove', 'remove_base']:
                # These operations remove files
                files_after_operations.discard(rec.get('from'))
        
        # Use the updated files_after_operations set that accounts for all operations
        # Find files that are not needed by Bullseye
        files_processed_for_cleanup = 0
        for replacement_file in files_after_operations:
            files_processed_for_cleanup += 1
            if files_processed_for_cleanup <= 10:  # Show first 10 for debugging
                # Processing file for cleanup
                # Check if this file is a source for any operation
                for rec in recommendations:
                    if rec.get('from') == replacement_file:
                        # Found operation source
                        break
            # Skip files that Bullseye actually needs
            if replacement_file in bullseye_files:
                continue
            
            # Check if this is a back file that should be kept because its corresponding front file exists
            should_keep_back_file = False
            if '-back-' in replacement_file:
                # This is a back file, check if we have the corresponding front file
                front_file = replacement_file.replace('-back-', '-front-')
                if front_file in files_after_operations:
                    # We have the front file, but only keep the back file if Bullseye actually needs the base files
                    # Since we already know replacement_file is NOT in bullseye_files (line 1485), 
                    # we only need to check if the front file is needed by Bullseye
                    if front_file in bullseye_files:
                        should_keep_back_file = True
                        # Keeping back file - front file needed by Bullseye
                    else:
                        should_keep_back_file = False
                        # Not keeping back file - Bullseye needs gender variants instead
                
                # Note: We don't set should_keep_back_file = True for source files here
                # because we want them to continue to the cleanup logic below
                # The cleanup logic will properly handle source files
            
            if should_keep_back_file:
                continue
                
            # Check if this file is a source for any operations (should be cleaned up)
            involved_in_operation = False
            for rec in recommendations:
                if rec.get('action') == 'rename' and rec.get('from') == replacement_file:
                    involved_in_operation = True
                    # Marking for cleanup - it's being renamed
                    break
                elif rec.get('action') == 'remove' and rec.get('from') == replacement_file:
                    involved_in_operation = True
                    # Marking for cleanup (explicit removal)
                    break
                elif rec.get('action') == 'remove_base' and rec.get('from') == replacement_file:
                    involved_in_operation = True
                    # Marking for cleanup (explicit base removal)
                    break
                elif rec.get('action') == 'create_base_from_male':
                    # Check if this file is a source for create_base_from_male operation
                    from_files = rec.get('from')
                    if isinstance(from_files, list):
                        if replacement_file in from_files:
                            involved_in_operation = True
                            # Marking for cleanup (source for create_base_from_male comprehensive operation)
                            break
                    elif from_files == replacement_file:
                        involved_in_operation = True
                        # Marking for cleanup (source for create_base_from_male single operation)
                        break
                elif rec.get('action') == 'create_base_from_female':
                    # Check if this file is a source for create_base_from_female operation
                    from_files = rec.get('from')
                    if isinstance(from_files, list):
                        if replacement_file in from_files:
                            involved_in_operation = True
                            # Marking for cleanup (source for create_base_from_female comprehensive operation)
                            break
                    elif from_files == replacement_file:
                        involved_in_operation = True
                        # Marking for cleanup (source for create_base_from_female single operation)
                        break
                elif rec.get('action') == 'create_gender_variant' and rec.get('from') == replacement_file:
                    involved_in_operation = True
                    # Marking for cleanup (source for create_gender_variant)
                    break
                elif rec.get('action') == 'create_gender_variant_from_other' and rec.get('from') == replacement_file:
                    involved_in_operation = True
                    # Marking for cleanup (source for create_gender_variant_from_other)
                    break
                # Handle comprehensive operations with lists
                elif isinstance(rec.get('from'), list) and replacement_file in rec.get('from', []):
                    involved_in_operation = True
                    # Marking for cleanup (source for comprehensive operation)
                    break
            
            # Add to cleanup if it's explicitly involved in an operation as a source file
            # (these will be cleaned up after the operation completes)
            if involved_in_operation:
                files_to_cleanup.append(replacement_file)
                # Added to cleanup list (source file - will be cleaned up after operation)
            else:
                # Check if this file is redundant due to base file creation
                # If this is a gender variant that's not needed by Bullseye, clean it up
                if '-m.' in replacement_file or '-f.' in replacement_file:
                    # This is a gender variant
                    base_file = replacement_file.replace('-m.', '.').replace('-f.', '.')
                    
                    # Check if Bullseye needs this specific gender variant
                    if replacement_file in bullseye_files:
                        # Bullseye needs this gender variant, so keep it
                        pass  # Keep this gender variant - Bullseye needs it
                    # For back files, also check if the corresponding front file is needed by Bullseye
                    elif '-back-' in replacement_file:
                        # This is a back gender variant, check if corresponding front file is needed
                        corresponding_front_file = replacement_file.replace('-back-', '-front-')
                        if corresponding_front_file in bullseye_files:
                            # Bullseye needs the corresponding front file, so keep this back file
                            pass  # Keep this back gender variant - Bullseye needs corresponding front file
                        else:
                            # Bullseye doesn't need the corresponding front file, so this back file is unnecessary
                            files_to_cleanup.append(replacement_file)
                            # Added to cleanup list - unnecessary back gender variant
                    # Check if Bullseye needs the base file (not the gender variant)
                    elif base_file in bullseye_files:
                        # Bullseye needs the base file, but only clean up this gender variant if it's not a source for creating the base file
                        is_source_for_base_creation = False
                        for rec in recommendations:
                            if ((rec.get('action') == 'create_base_from_male' or rec.get('action') == 'create_base_from_female')):
                                # Check if this gender variant is a source for creating the base file
                                from_files = rec.get('from')
                                to_files = rec.get('to')
                                
                                # Handle both single file and comprehensive operations
                                if isinstance(from_files, list) and isinstance(to_files, list):
                                    # Comprehensive operation - check if this file is in the source list
                                    if replacement_file in from_files and base_file in to_files:
                                        is_source_for_base_creation = True
                                        break
                                elif from_files == replacement_file and to_files == base_file:
                                    # Single file operation - direct match
                                    is_source_for_base_creation = True
                                    break
                        
                        if not is_source_for_base_creation:
                            # This gender variant is not needed to create the base file, so it's redundant
                            files_to_cleanup.append(replacement_file)
                            # Added to cleanup list - redundant gender variant (Bullseye needs base file but this variant isn't the source)
                    elif replacement_file not in bullseye_files:
                        # This gender variant is not needed by Bullseye and not a source of operations
                        files_to_cleanup.append(replacement_file)
                        # Added to cleanup list - unnecessary gender variant
                else:
                    pass  # For files not involved in operations, keep them if they're not explicitly unneeded
                    # Keeping - not involved in operations and not explicitly unneeded
        
        # Cleanup phase complete
        
        # DEDUPLICATION: Remove duplicate and conflicting operations
        # Before deduplication
        
        # Track which files will be created by operations to prevent conflicts
        files_being_created = set()
        operations_by_signature = {}  # Track operations by their signature to prevent exact duplicates
        deduplicated_recommendations = []
        
        for rec in recommendations:
            if rec.get('action') == 'cleanup':
                # Always keep cleanup operations
                deduplicated_recommendations.append(rec)
                continue
            
            # Create a signature for this operation to detect exact duplicates
            signature = f"{rec['action']}:{sorted(rec.get('from', []) if isinstance(rec.get('from'), list) else [rec.get('from')])}:{sorted(rec.get('to', []) if isinstance(rec.get('to'), list) else [rec.get('to')])}"
            
            if signature in operations_by_signature:
                # Skipping exact duplicate operation
                continue
            
            # Get target files that this operation will create
            target_files = []
            if isinstance(rec.get('to'), list):
                target_files = rec['to']
            elif rec.get('to'):
                target_files = [rec['to']]
            
            # Check if any target files are already being created by a previous operation
            conflict = False
            for target_file in target_files:
                if target_file in files_being_created:
                    # Skipping conflicting operation - target already being created
                    conflict = True
                    break
            
            if not conflict:
                # Add this operation and mark its target files as being created
                deduplicated_recommendations.append(rec)
                operations_by_signature[signature] = True
                files_being_created.update(target_files)
                # Keeping operation
        
        recommendations = deduplicated_recommendations
        # After deduplication
        
        # Create a single consolidated cleanup operation if there are files to clean up
        if files_to_cleanup:
            # Sort cleanup files by dex number (lowest to highest)
            def extract_dex_number(filename):
                try:
                    return int(filename.split('-')[0])
                except (ValueError, IndexError):
                    return 9999  # Put malformed files at the end
            
            files_to_cleanup.sort(key=extract_dex_number)
            
            # Count source operations (all operations except cleanup itself)
            source_operation_count = len([rec for rec in recommendations if rec.get('action') != 'cleanup'])
            
            recommendations.append({
                'action': 'cleanup',
                'from': files_to_cleanup[0],  # Use first file as the primary identifier
                'to': None,
                'reason': f'Remove {len(files_to_cleanup)} unneeded files (Bullseye does not require these files)',
                'cleanup_files': files_to_cleanup,  # List of all files to be cleaned up
                'source_operation_count': source_operation_count  # Count of operations that generated these files
            })
            # Created consolidated cleanup operation
        
        # Back files are now processed through the same comprehensive logic as front files in PHASE 2
        # The missing_files set already includes back_files_missing, so no separate processing needed
        
        # Generated recommendations and found unfulfilled files
        
        # Store unfulfilled files for later use
        self.unfulfilled_files_from_analysis = unfulfilled_files
        
        # Comprehensive analysis returning results
        import sys
        if sys.stdout:
            sys.stdout.flush()
        return recommendations
    
    def check_file_fixes(self, replacement_file, bullseye_files):
        """Comprehensive file checking for all types of fixes"""
        fixes = []
        
        # 1. Case sensitivity fixes (normal -> front)
        components = self.parse_sprite_filename(replacement_file)
        if components and components['direction'] == 'normal':
            # Convert normal to front
            front_file = f"{components['dex']:03d}-front-{components['variant']}"
            if components['gender']:
                front_file += f"-{components['gender']}"
            front_file += f".{components['extension']}"
            
            # Check if Bullseye needs this front file
            if front_file in bullseye_files:
                fixes.append({
                    'action': 'rename',
                    'from': replacement_file,
                    'to': front_file,
                    'reason': 'Fix case sensitivity (normal to front)'
                })
        
        # 2. Case sensitivity fixes - lowercase entire filename
        if replacement_file != replacement_file.lower():
            new_name = replacement_file.lower()
            fixes.append({
                'action': 'rename',
                'from': replacement_file,
                'to': new_name,
                'reason': 'Fix case sensitivity (lowercase entire filename)'
            })
        
        # 3. Malformed filename fixes (rrrrr)
        if '-rrrrr' in replacement_file:
            new_name = replacement_file.replace('-rrrrr', '')
            fixes.append({
                'action': 'rename',
                'from': replacement_file,
                'to': new_name,
                'reason': 'Fix malformed filename (remove rrrrr)'
            })
        
        # 4. Double extension fixes
        if '.gif.gif' in replacement_file:
            new_name = replacement_file.replace('.gif.gif', '.gif')
            fixes.append({
                'action': 'rename',
                'from': replacement_file,
                'to': new_name,
                'reason': 'Fix double extension (.gif.gif -> .gif)'
            })
        elif '.png.png' in replacement_file:
            new_name = replacement_file.replace('.png.png', '.png')
            fixes.append({
                'action': 'rename',
                'from': replacement_file,
                'to': new_name,
                'reason': 'Fix double extension (.png.png -> .png)'
            })
        
        # 4.5. Double dots fixes (..gif -> .gif, ..png -> .png)
        if '..gif' in replacement_file:
            new_name = replacement_file.replace('..gif', '.gif')
            fixes.append({
                'action': 'rename',
                'from': replacement_file,
                'to': new_name,
                'reason': 'Fix double dots (..gif -> .gif)'
            })
        elif '..png' in replacement_file:
            new_name = replacement_file.replace('..png', '.png')
            fixes.append({
                'action': 'rename',
                'from': replacement_file,
                'to': new_name,
                'reason': 'Fix double dots (..png -> .png)'
            })
        
        # 5. Files with underscores (malformed - should be removed)
        if '_2-' in replacement_file:
            fixes.append({
                'action': 'remove',
                'from': replacement_file,
                'to': None,
                'reason': 'Remove malformed file (contains underscores)'
            })
        
        return fixes
        
    
    def parse_sprite_filename(self, filename):
        """Parse a sprite filename into its components"""
        import re
        
        # Pattern: 001-front-n-m.gif or 001-back-s-f.gif or 001-normal-n.gif (supports both .gif and .png)
        pattern = r'^(\d{3})-([a-zA-Z]+)-([ns])-?([mf]?)\.(gif|png)$'
        match = re.match(pattern, filename)
        
        if match:
            dex_str, direction, variant, gender, extension = match.groups()
            return {
                'dex': int(dex_str),
                'direction': direction,
                'variant': variant,
                'gender': gender,
                'extension': extension,
                'original': filename
            }
        
        return None
    
    def analyze_output_impact(self, matches, output_files, total_bullseye_files):
        """Analyze what will happen to the output directory"""
        if not matches:
            return
        
        # Find files that will be overwritten
        files_to_overwrite = matches.intersection(output_files)
        # Find files that will be created new
        files_to_create = matches - output_files
        # Find existing files that won't be touched
        files_untouched = output_files - matches
        
        # Calculate custom sprites (user-provided replacements)
        custom_sprites = len(files_to_overwrite) + len(files_to_create)
        
        # Calculate remaining bullseye sprites (bullseye sprites that don't have replacements)
        remaining_bullseye = total_bullseye_files - custom_sprites
        
        # Output analysis for mod creation
        if files_to_overwrite and files_to_create:
            self.log_message(f"📁 Processing: {len(files_to_overwrite)} existing sprites, {len(files_to_create)} new sprites ({custom_sprites} total custom sprites)", "INFO")
        elif files_to_overwrite:
            self.log_message(f"📁 Processing: {len(files_to_overwrite)} existing sprites", "INFO")
        elif files_to_create:
            self.log_message(f"📁 Processing: {len(files_to_create)} new sprites", "INFO")
        
        # Show accurate mod content breakdown
        mod_parts = []
        if custom_sprites > 0:
            mod_parts.append(f"{custom_sprites} custom sprites")
        if remaining_bullseye > 0:
            mod_parts.append(f"{remaining_bullseye} remaining bullseye sprites")
        
        total_sprites = custom_sprites + remaining_bullseye
        mod_content = " + ".join(mod_parts) if mod_parts else "0 sprites"
        
        self.log_message(f"📦 Mod: Will create .mod file with {mod_content} = {total_sprites} total sprites", "INFO")
    
    def check_missing_directories(self, bullseye_dir, replacement_dir, output_dir):
        """Check for missing required directories and warn user"""
        missing_dirs = []
        
        if not bullseye_dir:
            missing_dirs.append("Bullseye Sprites directory")
        elif not bullseye_dir.exists():
            missing_dirs.append("Bullseye Sprites directory (does not exist)")
        
        if not replacement_dir:
            missing_dirs.append("Replacement Sprites directory")
        elif not replacement_dir.exists():
            missing_dirs.append("Replacement Sprites directory (does not exist)")
        
        if not output_dir:
            missing_dirs.append("Output directory")
        elif not output_dir.exists():
            missing_dirs.append("Output directory (does not exist)")
        
        if missing_dirs:
            if len(missing_dirs) == 1:
                self.log_message(f"WARNING: Please select {missing_dirs[0]} to proceed", "WARNING")
            else:
                self.log_message(f"WARNING: Please select the following directories: {', '.join(missing_dirs)}", "WARNING")
        # Ready to process message is now handled in consolidated logging
    
    def validate_inputs(self):
        """Validate input directories and settings with smart validation"""
        errors = []
        
        try:
            # Use smart directory validation for all directories
            validation_errors = self.validate_directories_for_analysis()
            if validation_errors:
                errors.extend(validation_errors)
                return errors  # Return early if basic validation fails
            
            # Additional validation for processing-specific requirements
            
            # Check for matching files if both directories are set
            if (self.move_dir.get() and self.sprite_dir.get() and 
                Path(self.move_dir.get()).exists() and Path(self.sprite_dir.get()).exists()):
                
                try:
                    bullseye_dir = Path(self.move_dir.get())
                    replacement_dir = Path(self.sprite_dir.get())
                    
                    bullseye_files = set(f.name for f in bullseye_dir.glob("*.gif")) | set(f.name for f in bullseye_dir.glob("*.png"))
                    replacement_files = set(f.name for f in replacement_dir.glob("*.gif")) | set(f.name for f in replacement_dir.glob("*.png"))
                    matches = bullseye_files.intersection(replacement_files)
                    
                    # Smart empty folder detection for better error messages
                    if not bullseye_files:
                        bullseye_all_files = list(bullseye_dir.iterdir())
                        bullseye_non_sprite = [f for f in bullseye_all_files if f.is_file()]
                        if bullseye_non_sprite:
                            errors.append("Bullseye directory contains no valid sprite files (only non-sprite files found)")
                        else:
                            errors.append("Bullseye directory is empty")
                    elif not replacement_files:
                        replacement_all_files = list(replacement_dir.iterdir())
                        replacement_non_sprite = [f for f in replacement_all_files if f.is_file()]
                        if replacement_non_sprite:
                            errors.append("Replacement directory contains no valid sprite files (only non-sprite files found)")
                        else:
                            errors.append("Replacement directory is empty")
                    elif not matches:
                        errors.append("No matching sprite files found between directories")
                    elif len(matches) == 0:
                        errors.append("No matching sprite files found between directories")
                    
                    # Check output directory impact (just log warning, don't block)
                    if self.output_dir.get() and Path(self.output_dir.get()).exists():
                        try:
                            output_files = set(f.name for f in Path(self.output_dir.get()).glob("*.gif")) | set(f.name for f in Path(self.output_dir.get()).glob("*.png"))
                            files_to_overwrite = matches.intersection(output_files)
                            if files_to_overwrite:
                                # Log warning but don't add to errors (allow overwriting)
                                self.log_message(f"WARNING: {len(files_to_overwrite)} files will be overwritten in output directory", "WARNING")
                        except Exception as e:
                            errors.append(f"Error scanning output directory: {str(e)}")
                            
                except Exception as e:
                    errors.append(f"Error scanning sprite directories: {str(e)}")
            
            if not self.output_dir.get():
                errors.append("Please select output directory")
            
            # Log directory is optional, but if custom is selected, it must be provided
            if self.use_custom_log_dir.get() and not self.log_dir.get():
                errors.append("Please select a custom log directory or uncheck the option")
            
            if not self.process_all.get():
                try:
                    limit = int(self.limit_var.get())
                    if limit <= 0:
                        errors.append("Limit must be a positive number")
                except ValueError:
                    errors.append("Limit must be a valid number")
                    
        except Exception as e:
            import traceback
            errors.append(f"Validation error: {str(e)}")
            self.log_message(f"❌ ERROR: Validation failed with exception: {type(e).__name__}", "ERROR")
            self.log_message(f"❌ ERROR: {str(e)}", "ERROR")
            self.log_message("❌ ERROR: Validation traceback:", "ERROR")
            for line in traceback.format_exc().split('\n'):
                if line.strip():
                    self.log_message(f"    {line}", "ERROR")
        
        return errors
    
    def _sanitize_mod_name(self, name: str) -> str:
        """
        Sanitize mod name for safe use in file systems and XML.
        
        Args:
            name: Raw mod name input
            
        Returns:
            Sanitized mod name safe for file systems and XML
        """
        if not name:
            return ""
        
        # Remove or replace invalid characters for file systems
        # Windows/Linux/Mac invalid characters: < > : " / \ | ? *
        sanitized = re.sub(r'[<>:"/\\|?*]', '', name)
        
        # Remove control characters (ASCII 0-31)
        sanitized = re.sub(r'[\x00-\x1f]', '', sanitized)
        
        # Remove leading/trailing spaces and dots (Windows restriction)
        sanitized = sanitized.strip('. ')
        
        # Replace multiple spaces with single space
        sanitized = re.sub(r'\s+', ' ', sanitized)
        
        # Limit length to avoid path issues (Windows has 260 char path limit)
        if len(sanitized) > 100:
            sanitized = sanitized[:100]
        
        return sanitized.strip()
    
    def _sanitize_mod_description(self, description: str) -> str:
        """
        Sanitize mod description for safe use in XML.
        
        Args:
            description: Raw mod description input
            
        Returns:
            Sanitized description safe for XML
        """
        if not description:
            return ""
        
        # Remove or replace XML special characters
        # & < > " ' are XML entities that need escaping
        sanitized = description
        
        # Escape XML entities
        sanitized = sanitized.replace('&', '&amp;')
        sanitized = sanitized.replace('<', '&lt;')
        sanitized = sanitized.replace('>', '&gt;')
        sanitized = sanitized.replace('"', '&quot;')
        sanitized = sanitized.replace("'", '&apos;')
        
        # Remove control characters (ASCII 0-31) except newlines and tabs
        sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', sanitized)
        
        # Replace multiple whitespace with single space, preserve line breaks
        sanitized = re.sub(r'[ \t]+', ' ', sanitized)
        sanitized = re.sub(r'\n\s*\n', '\n\n', sanitized)  # Preserve paragraph breaks
        
        # Limit length to reasonable size
        if len(sanitized) > 1000:
            sanitized = sanitized[:1000] + "..."
        
        return sanitized.strip()
    
    def _save_config_internal(self, summary_var, front_var, back_var, summary_overrides, front_overrides, back_overrides):
        """Internal method to save scaling configuration without validation or messages"""
        # Save the current values to instance variables
        self.default_summary_scale = float(summary_var.get())
        self.default_front_scale = float(front_var.get())
        self.default_back_scale = float(back_var.get())
        self.summary_overrides = summary_overrides["summary"].copy()
        self.front_overrides = front_overrides["front"].copy()
        self.back_overrides = back_overrides["back"].copy()
        
        # Debug logging to verify values are saved correctly
        self.log_message(f"🔧 Saved scaling config: Summary={self.default_summary_scale}, Front={self.default_front_scale}, Back={self.default_back_scale}", "INFO")
        
        # Save settings to file
        self.save_settings()

    def save_current_config(self, summary_var, front_var, back_var, summary_overrides, front_overrides, back_overrides):
        """Save current scaling configuration without building mod"""
        try:
            # Validate scaling values
            summary_scale = float(summary_var.get())
            front_scale = float(front_var.get())
            back_scale = float(back_var.get())
            
            # Check for reasonable values (no negatives, reasonable upper bounds)
            if any(val < 0 for val in [summary_scale, front_scale, back_scale]):
                messagebox.showerror("Error", "Scaling values cannot be negative.")
                return
            if any(val > 10 for val in [summary_scale, front_scale, back_scale]):
                messagebox.showerror("Error", "Scaling values seem too large. Please use reasonable values (0-10).")
                return
                
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numbers for all scaling values.")
            return
        
        # Save the configuration
        self._save_config_internal(summary_var, front_var, back_var, summary_overrides, front_overrides, back_overrides)
        
        # Show confirmation message
        messagebox.showinfo("Save Complete", "Scaling configuration has been saved successfully!")

    def reset_all_overrides(self, summary_var, front_var, back_var, summary_overrides, front_overrides, back_overrides):
        """Reset all scaling values and overrides to defaults"""
        # Reset default values to defaults
        summary_var.set("2.7")
        front_var.set("1.0")
        back_var.set("1.0")
        
        # Clear all overrides
        summary_overrides["summary"] = {}
        front_overrides["front"] = {}
        back_overrides["back"] = {}
        
        # Update instance variables
        self.default_summary_scale = 2.7
        self.default_front_scale = 1.0
        self.default_back_scale = 1.0
        self.summary_overrides = {}
        self.front_overrides = {}
        self.back_overrides = {}
        
        # Save to file
        self.save_settings()
        
        # Show confirmation message
        messagebox.showinfo("Reset Complete", "All scaling values and overrides have been reset to defaults.")

    def get_build_configuration(self):
        """Show dialog to get build configuration from user"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Build Configuration")
        dialog.geometry("1200x900")
        dialog.configure(bg='#3a3a3a')
        dialog.resizable(False, False)
        
        # Center the dialog
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Main frame (no scrollbar needed)
        main_frame = tk.Frame(dialog, bg='#3a3a3a')
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title
        title_label = tk.Label(main_frame, text="⚙️ Build Configuration", 
                              font=("Segoe UI", 16, "bold"),
                              bg='#3a3a3a', fg='#e0e0e0')
        title_label.pack(pady=(0, 15))
        
        # Description
        desc_label = tk.Label(main_frame, 
                             text="Configure your mod package settings before building.",
                             font=("Segoe UI", 10),
                             bg='#3a3a3a', fg='#95a5a6',
                             justify=tk.CENTER)
        desc_label.pack(pady=(0, 20))
        
        # Main content container with two columns
        main_container = tk.Frame(main_frame, bg='#3a3a3a')
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Left column for main configuration
        left_column = tk.Frame(main_container, bg='#3a3a3a')
        left_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 20))
        
        # Right column for custom scaling configuration
        right_column = tk.Frame(main_container, bg='#3a3a3a')
        right_column.pack(side=tk.RIGHT, fill=tk.Y, padx=(20, 0))
        
        # Variables
        mod_name_var = tk.StringVar()
        mod_version_var = tk.StringVar()
        mod_description_var = tk.StringVar()
        additional_authors = []  # List to store additional authors
        
        # Default values
        mod_name_var.set("BullseyeInjectorMod")
        mod_version_var.set("1.0")
        mod_description_var.set("Built and scaled with Bullseye Injector!")
        
        # Mod Name Section
        name_frame = tk.LabelFrame(left_column, text="📦 Mod Name", 
                                  font=("Segoe UI", 11, "bold"),
                                  bg='#3a3a3a', fg='#e0e0e0',
                                  relief=tk.FLAT, bd=1)
        name_frame.pack(fill=tk.X, pady=(0, 15))
        
        name_entry = tk.Entry(name_frame, textvariable=mod_name_var,
                             font=("Segoe UI", 11),
                             bg='#2c2c2c', fg='#e0e0e0',
                             relief=tk.FLAT, bd=5,
                             insertbackground='#e0e0e0')
        name_entry.pack(fill=tk.X, padx=10, pady=(10, 5))
        
        # Add helpful text about valid characters
        name_help = tk.Label(name_frame, 
                            text="Valid characters: letters, numbers, spaces, hyphens, underscores",
                            font=("Segoe UI", 8),
                            bg='#3a3a3a', fg='#888888',
                            wraplength=400)
        name_help.pack(padx=10, pady=(0, 10))
        
        # Version Section
        version_frame = tk.LabelFrame(left_column, text="🔢 Version", 
                                     font=("Segoe UI", 11, "bold"),
                                     bg='#3a3a3a', fg='#e0e0e0',
                                     relief=tk.FLAT, bd=1)
        version_frame.pack(fill=tk.X, pady=(0, 15))
        
        version_entry = tk.Entry(version_frame, textvariable=mod_version_var,
                                font=("Segoe UI", 11),
                                bg='#2c2c2c', fg='#e0e0e0',
                                relief=tk.FLAT, bd=5,
                                insertbackground='#e0e0e0')
        version_entry.pack(fill=tk.X, padx=10, pady=10)
        
        # Authors Section
        authors_frame = tk.LabelFrame(left_column, text="👥 Authors", 
                                     font=("Segoe UI", 11, "bold"),
                                     bg='#3a3a3a', fg='#e0e0e0',
                                     relief=tk.FLAT, bd=1)
        authors_frame.pack(fill=tk.X, pady=(0, 15))
        
        
        # Additional authors list
        authors_list_frame = tk.Frame(authors_frame, bg='#3a3a3a')
        authors_list_frame.pack(fill=tk.X, padx=10, pady=(10, 10))
        
        authors_listbox = tk.Listbox(authors_list_frame, height=4,
                                    font=("Segoe UI", 10),
                                    bg='#2c2c2c', fg='#e0e0e0',
                                    selectbackground='#8e44ad',
                                    relief=tk.FLAT, bd=5)
        authors_listbox.pack(fill=tk.X, pady=(0, 5))
        
        # Add author controls
        add_author_frame = tk.Frame(authors_frame, bg='#3a3a3a')
        add_author_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        author_entry = tk.Entry(add_author_frame,
                               font=("Segoe UI", 10),
                               bg='#2c2c2c', fg='#e0e0e0',
                               relief=tk.FLAT, bd=5,
                               insertbackground='#e0e0e0')
        author_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        def add_author():
            author = author_entry.get().strip()
            if author and author not in additional_authors:
                additional_authors.append(author)
                authors_listbox.insert(tk.END, author)
                author_entry.delete(0, tk.END)
        
        def remove_author():
            selection = authors_listbox.curselection()
            if selection:
                index = selection[0]
                authors_listbox.delete(index)
                additional_authors.pop(index)
        
        add_btn = tk.Button(add_author_frame, text="Add", command=add_author,
                           font=("Segoe UI", 9),
                           bg='#27ae60', fg='white',
                           relief=tk.FLAT, bd=0,
                           padx=10, pady=5,
                           cursor='hand2')
        add_btn.pack(side=tk.RIGHT, padx=(5, 0))
        
        remove_btn = tk.Button(add_author_frame, text="Remove", command=remove_author,
                              font=("Segoe UI", 9),
                              bg='#e74c3c', fg='white',
                              relief=tk.FLAT, bd=0,
                              padx=10, pady=5,
                              cursor='hand2')
        remove_btn.pack(side=tk.RIGHT)
        
        # Description Section
        desc_frame = tk.LabelFrame(left_column, text="📝 Description", 
                                  font=("Segoe UI", 11, "bold"),
                                  bg='#3a3a3a', fg='#e0e0e0',
                                  relief=tk.FLAT, bd=1)
        desc_frame.pack(fill=tk.X, pady=(0, 15))
        
        desc_text = tk.Text(desc_frame, height=3,
                           font=("Segoe UI", 10),
                           bg='#2c2c2c', fg='#e0e0e0',
                           relief=tk.FLAT, bd=5,
                           insertbackground='#e0e0e0',
                           wrap=tk.WORD)
        desc_text.pack(fill=tk.X, padx=10, pady=(10, 5))
        desc_text.insert(tk.END, mod_description_var.get())
        
        # Add helpful text about description formatting
        desc_help = tk.Label(desc_frame, 
                            text="Special characters will be automatically escaped for XML safety",
                            font=("Segoe UI", 8),
                            bg='#3a3a3a', fg='#888888',
                            wraplength=400)
        desc_help.pack(padx=10, pady=(0, 10))
        
        # Clean Scaling Configuration Section
        scaling_frame = tk.Frame(right_column, bg='#3a3a3a')
        scaling_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Title and description
        title_label = tk.Label(scaling_frame, text="🎯 Sprite Scaling", 
                              font=("Segoe UI", 14, "bold"),
                              bg='#3a3a3a', fg='#ffffff')
        title_label.pack(pady=(0, 10))
        
        # Description
        desc_label = tk.Label(scaling_frame, 
                             text="Configure how Pokemon sprites are scaled in-game. Set default values for all Pokemon,\nthen use override buttons to customize specific ones.",
                             font=("Segoe UI", 9),
                             bg='#2c2c2c', fg='#b0b0b0',
                             justify=tk.LEFT,
                             relief=tk.FLAT,
                             bd=5,
                             padx=10,
                             pady=5)
        desc_label.pack(pady=(0, 10))
        
        # Scale explanations
        explanations_section = tk.Frame(scaling_frame, bg='#3a3a3a')
        explanations_section.pack(fill=tk.X, pady=(0, 10))
        
        # Summary Scale explanation
        summary_desc = tk.Label(explanations_section,
                               text="📊 Summary Scale: Controls sprite size in Pokemon summary menus, Pokedex entries, and team selection screens",
                               font=("Segoe UI", 9),
                               bg='#2c2c2c', fg='#3498db',
                               wraplength=400,
                               justify=tk.LEFT,
                               anchor='w',
                               relief=tk.FLAT,
                               bd=5,
                               padx=10,
                               pady=5)
        summary_desc.pack(fill=tk.X, pady=(0, 3))
        
        # Front Scale explanation
        front_desc = tk.Label(explanations_section,
                             text="⚔️ Front Scale: Controls sprite size during battle scenes when Pokemon faces forward (opponent's Pokemon)",
                             font=("Segoe UI", 9),
                             bg='#2c2c2c', fg='#e67e22',
                             wraplength=400,
                             justify=tk.LEFT,
                             anchor='w',
                             relief=tk.FLAT,
                             bd=5,
                             padx=10,
                             pady=5)
        front_desc.pack(fill=tk.X, pady=(0, 3))
        
        # Back Scale explanation
        back_desc = tk.Label(explanations_section,
                            text="🔄 Back Scale: Controls sprite size during battle scenes when Pokemon faces away (your Pokemon)",
                            font=("Segoe UI", 9),
                            bg='#2c2c2c', fg='#9b59b6',
                            wraplength=400,
                            justify=tk.LEFT,
                            anchor='w',
                            relief=tk.FLAT,
                            bd=5,
                            padx=10,
                            pady=5)
        back_desc.pack(fill=tk.X, pady=(0, 3))
        
        # Default values section - clean layout
        defaults_section = tk.Frame(scaling_frame, bg='#3a3a3a')
        defaults_section.pack(fill=tk.X, pady=(0, 10))
        
        # Section label
        tk.Label(defaults_section, text="⚙️ Default Values", 
                font=("Segoe UI", 11, "bold"), bg='#3a3a3a', fg='#ffffff').pack(pady=(0, 5))
        
        # Usage info with recommendations
        tk.Label(defaults_section, text="Minimum value: 0.0 (invisible) | Recommended range: 1.0 - 3.0 | Higher values = larger sprites",
                font=("Segoe UI", 9), bg='#2c2c2c', fg='#b0b0b0',
                relief=tk.FLAT, bd=5, padx=10, pady=5).pack(pady=(0, 5))
        
        default_summary = str(self.default_summary_scale)
        default_front = str(self.default_front_scale)
        default_back = str(self.default_back_scale)
        
        # Debug logging to verify values are loaded correctly
        self.log_message(f"🔧 Loading scaling config: Summary={default_summary}, Front={default_front}, Back={default_back}", "INFO")
        
        # Summary Scale
        summary_frame = tk.Frame(defaults_section, bg='#3a3a3a')
        summary_frame.pack(fill=tk.X, pady=5)
        tk.Label(summary_frame, text="📊 Summary Scale", 
                font=("Segoe UI", 10), bg='#3a3a3a', fg='#3498db').pack(side=tk.LEFT)
        summary_var = tk.StringVar(value=default_summary)
        summary_entry = tk.Entry(summary_frame, textvariable=summary_var,
                               font=("Segoe UI", 10), width=8,
                               bg='#2c2c2c', fg='#ffffff',
                               relief=tk.FLAT, bd=5,
                               insertbackground='#ffffff')
        summary_entry.pack(side=tk.RIGHT)
        # Ensure the value is properly set
        summary_var.set(default_summary)
        
        # Front Scale
        front_frame = tk.Frame(defaults_section, bg='#3a3a3a')
        front_frame.pack(fill=tk.X, pady=5)
        tk.Label(front_frame, text="⚔️ Front Scale", 
                font=("Segoe UI", 10), bg='#3a3a3a', fg='#e67e22').pack(side=tk.LEFT)
        front_var = tk.StringVar(value=default_front)
        front_entry = tk.Entry(front_frame, textvariable=front_var,
                             font=("Segoe UI", 10), width=8,
                             bg='#2c2c2c', fg='#ffffff',
                             relief=tk.FLAT, bd=5,
                             insertbackground='#ffffff')
        front_entry.pack(side=tk.RIGHT)
        # Ensure the value is properly set
        front_var.set(default_front)
        
        # Back Scale
        back_frame = tk.Frame(defaults_section, bg='#3a3a3a')
        back_frame.pack(fill=tk.X, pady=5)
        tk.Label(back_frame, text="🔄 Back Scale", 
                font=("Segoe UI", 10), bg='#3a3a3a', fg='#9b59b6').pack(side=tk.LEFT)
        back_var = tk.StringVar(value=default_back)
        back_entry = tk.Entry(back_frame, textvariable=back_var,
                            font=("Segoe UI", 10), width=8,
                            bg='#2c2c2c', fg='#ffffff',
                            relief=tk.FLAT, bd=5,
                            insertbackground='#ffffff')
        back_entry.pack(side=tk.RIGHT)
        # Ensure the value is properly set
        back_var.set(default_back)
        
        # Initialize override storage
        summary_overrides = {"summary": self.summary_overrides.copy()}
        front_overrides = {"front": self.front_overrides.copy()}
        back_overrides = {"back": self.back_overrides.copy()}
        
        # Override buttons - clean and simple
        overrides_section = tk.Frame(scaling_frame, bg='#3a3a3a')
        overrides_section.pack(fill=tk.X, pady=(5, 0))
        
        # Section label
        tk.Label(overrides_section, text="🎮 Individual Overrides", 
                font=("Segoe UI", 11, "bold"), bg='#3a3a3a', fg='#ffffff').pack(pady=(0, 3))
        
        # Override explanation
        tk.Label(overrides_section, text="Override default scaling for specific Pokemon. Click buttons to open detailed override dialogs\nwhere you can set custom values. Leave entries empty to use default scaling.",
                font=("Segoe UI", 9), bg='#2c2c2c', fg='#b0b0b0',
                justify=tk.LEFT, relief=tk.FLAT, bd=5, padx=10, pady=5).pack(pady=(0, 5))
        
        # Clean button row - centered
        buttons_row = tk.Frame(overrides_section, bg='#3a3a3a')
        buttons_row.pack(fill=tk.X)
        
        # Create a centered container for the buttons
        center_container = tk.Frame(buttons_row, bg='#3a3a3a')
        center_container.pack(anchor='center')
        
        def open_summary_overrides():
            result = self.show_scale_override_dialog("summary", summary_overrides["summary"])
            if result is not None:
                summary_overrides["summary"] = result
        
        def open_front_overrides():
            result = self.show_scale_override_dialog("front", front_overrides["front"])
            if result is not None:
                front_overrides["front"] = result
        
        def open_back_overrides():
            result = self.show_scale_override_dialog("back", back_overrides["back"])
            if result is not None:
                back_overrides["back"] = result
        
        # Clean, minimal buttons - packed in center container
        summary_btn = tk.Button(center_container, text="Summary", 
                              command=open_summary_overrides,
                              font=("Segoe UI", 10),
                              bg='#3498db', fg='white',
                              relief=tk.FLAT, bd=0,
                              padx=20, pady=8,
                              cursor='hand2')
        summary_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        front_btn = tk.Button(center_container, text="Front", 
                            command=open_front_overrides,
                            font=("Segoe UI", 10),
                            bg='#e67e22', fg='white',
                            relief=tk.FLAT, bd=0,
                            padx=20, pady=8,
                            cursor='hand2')
        front_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        back_btn = tk.Button(center_container, text="Back", 
                           command=open_back_overrides,
                           font=("Segoe UI", 10),
                           bg='#9b59b6', fg='white',
                           relief=tk.FLAT, bd=0,
                           padx=20, pady=8,
                           cursor='hand2')
        back_btn.pack(side=tk.LEFT)
        
        # Save and Reset buttons - side by side below the override buttons
        buttons_container = tk.Frame(overrides_section, bg='#3a3a3a')
        buttons_container.pack(pady=(15, 0))
        
        save_btn = tk.Button(buttons_container, text="SAVE CONFIG", 
                           command=lambda: self.save_current_config(summary_var, front_var, back_var, summary_overrides, front_overrides, back_overrides),
                           font=("Segoe UI", 11, "bold"),
                           bg='#27ae60', fg='white',
                           relief=tk.FLAT, bd=0,
                           padx=25, pady=10,
                           cursor='hand2')
        save_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        reset_btn = tk.Button(buttons_container, text="RESET CONFIG", 
                            command=lambda: self.reset_all_overrides(summary_var, front_var, back_var, summary_overrides, front_overrides, back_overrides),
                            font=("Segoe UI", 11, "bold"),
                            bg='#e74c3c', fg='white',
                            relief=tk.FLAT, bd=0,
                            padx=25, pady=10,
                            cursor='hand2')
        reset_btn.pack(side=tk.LEFT)
        
        # Buttons frame
        buttons_frame = tk.Frame(main_frame, bg='#3a3a3a')
        buttons_frame.pack(fill=tk.X, pady=(20, 0))
        
        result = [None]  # Use list to allow modification in nested function
        
        def on_ok():
            # Get raw inputs
            raw_name = mod_name_var.get().strip()
            raw_description = desc_text.get(1.0, tk.END).strip()
            
            # Sanitize inputs
            name = self._sanitize_mod_name(raw_name)
            version = mod_version_var.get().strip()
            description = self._sanitize_mod_description(raw_description)
            
            # Check if sanitization changed the inputs and inform user
            sanitization_warnings = []
            if raw_name != name:
                sanitization_warnings.append(f"Mod name sanitized: '{raw_name}' -> '{name}'")
            if raw_description != description:
                sanitization_warnings.append("Mod description sanitized for XML safety")
            
            if sanitization_warnings:
                warning_msg = "Input sanitization required:\n\n" + "\n".join(sanitization_warnings)
                warning_msg += "\n\nPlease fix your input to avoid these issues and try again."
                messagebox.showerror("Input Validation Failed", warning_msg)
                return
            
            if not name:
                messagebox.showerror("Error", "Please enter a mod name.")
                return
            if not version:
                messagebox.showerror("Error", "Please enter a version.")
                return
            
            # Validate scaling values
            try:
                summary_scale = float(summary_var.get())
                front_scale = float(front_var.get())
                back_scale = float(back_var.get())
                
                # Debug logging to verify values are collected correctly
                self.log_message(f"🔧 Collected scaling values: Summary={summary_scale}, Front={front_scale}, Back={back_scale}", "INFO")
                
                # Check for reasonable values (no negatives, reasonable upper bounds)
                if any(val < 0 for val in [summary_scale, front_scale, back_scale]):
                    messagebox.showerror("Error", "Scaling values cannot be negative.")
                    return
                if any(val > 10 for val in [summary_scale, front_scale, back_scale]):
                    messagebox.showerror("Error", "Scaling values seem too large. Please use reasonable values (0-10).")
                    return
                    
            except ValueError:
                messagebox.showerror("Error", "Please enter valid numbers for all scaling values.")
                return
            
            # Build authors string (UncleTyrone and Zoruah are always included)
            authors = ["UncleTyrone", "Zoruah"] + additional_authors
            authors_string = ", ".join(authors)
            
            # Save the current configuration (without showing message box)
            self._save_config_internal(summary_var, front_var, back_var, summary_overrides, front_overrides, back_overrides)
            
            result[0] = {
                'name': name,
                'version': version,
                'authors': authors_string,
                'description': description or "Built and scaled with Bullseye Injector!",
                'custom_scaling': {
                    'summary_scale': summary_scale,
                    'front_scale': front_scale,
                    'back_scale': back_scale,
                    'overrides': {
                        'summary': summary_overrides["summary"],
                        'front': front_overrides["front"],
                        'back': back_overrides["back"]
                    }
                }
            }
            dialog.destroy()
        
        def on_cancel():
            dialog.destroy()
        
        # OK button
        ok_button = tk.Button(buttons_frame, text="Build Mod", command=on_ok,
                             font=("Segoe UI", 11, "bold"),
                             bg='#27ae60', fg='white',
                             relief=tk.FLAT, bd=0,
                             padx=25, pady=10,
                             cursor='hand2')
        ok_button.pack(side=tk.RIGHT, padx=(10, 0))
        
        # Cancel button
        cancel_button = tk.Button(buttons_frame, text="Cancel", command=on_cancel,
                                 font=("Segoe UI", 11, "bold"),
                                 bg='#e74c3c', fg='white',
                                 relief=tk.FLAT, bd=0,
                                 padx=25, pady=10,
                                 cursor='hand2')
        cancel_button.pack(side=tk.RIGHT)
        
        # Bind Enter key to add author
        author_entry.bind('<Return>', lambda e: add_author())
        
        # Bind Enter key to OK
        dialog.bind('<Return>', lambda e: on_ok())
        dialog.bind('<Escape>', lambda e: on_cancel())
        
        # Focus on mod name entry
        name_entry.focus()
        
        dialog.wait_window()
        
        return result[0]
    
    def show_scale_override_dialog(self, scale_type, existing_overrides=None):
        """Show dialog for setting custom scaling overrides for specific Pokemon"""
        dialog = tk.Toplevel(self.root)
        dialog.title(f"{scale_type.title()} Scale Overrides")
        dialog.geometry("900x700")
        dialog.configure(bg='#3a3a3a')
        dialog.resizable(False, False)
        
        # Center the dialog
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Use existing overrides if provided
        if existing_overrides is None:
            existing_overrides = {}
        
        # Title
        title_label = tk.Label(dialog, text=f"🎯 {scale_type.title()} Scale Overrides", 
                              font=("Segoe UI", 18, "bold"),
                              bg='#3a3a3a', fg='#e0e0e0')
        title_label.pack(pady=(25, 15))
        
        # Description frame with usage information
        desc_frame = tk.Frame(dialog, bg='#3a3a3a')
        desc_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        # Main description
        main_desc = ""
        if scale_type == "summary":
            main_desc = "Summary Scale controls sprite size in Pokemon summary menus and Pokedex entries."
        elif scale_type == "front":
            main_desc = "Front Scale controls sprite size during battle scenes (Pokemon facing forward)."
        elif scale_type == "back":
            main_desc = "Back Scale controls sprite size during battle scenes (Pokemon facing away)."
        
        desc_label = tk.Label(desc_frame, 
                             text=main_desc,
                             font=("Segoe UI", 11),
                             bg='#3a3a3a', fg='#e0e0e0',
                             justify=tk.CENTER)
        desc_label.pack(pady=(0, 10))
        
        # Usage information
        usage_frame = tk.LabelFrame(desc_frame, text="📋 Usage Information", 
                                   font=("Segoe UI", 10, "bold"),
                                   bg='#3a3a3a', fg='#e0e0e0',
                                   relief=tk.FLAT, bd=1)
        usage_frame.pack(fill=tk.X, pady=(0, 10))
        
        usage_text = tk.Text(usage_frame, height=3,
                           font=("Segoe UI", 9),
                           bg='#2c2c2c', fg='#b0b0b0',
                           relief=tk.FLAT, bd=5,
                           wrap=tk.WORD,
                           state=tk.DISABLED)
        usage_text.pack(fill=tk.X, padx=10, pady=10)
        
        usage_info = ("• Minimum value: 0.0 (invisible)\n"
                     "• Recommended range: 1.0 - 3.0\n"
                     "• Leave entries empty to use default scaling\n"
                     "• Higher values = larger sprites, lower values = smaller sprites")
        
        usage_text.config(state=tk.NORMAL)
        usage_text.insert(tk.END, usage_info)
        usage_text.config(state=tk.DISABLED)
        
        # Create scrollable frame for Pokemon entries
        scroll_frame = tk.Frame(dialog, bg='#3a3a3a')
        scroll_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Create canvas and scrollbar
        canvas = tk.Canvas(scroll_frame, bg='#3a3a3a', highlightthickness=0)
        scrollbar = tk.Scrollbar(scroll_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#3a3a3a')
        
        # Configure scrolling
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Bind mousewheel to canvas
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        # Create Pokemon entries grid
        pokemon_entries = {}
        
        # Create main grid container
        grid_container = tk.Frame(scrollable_frame, bg='#3a3a3a')
        grid_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Configure grid columns (10 columns for maximum space usage)
        num_columns = 10
        for col in range(num_columns):
            grid_container.columnconfigure(col, weight=1)
        
        # Get existing Pokemon from files (if available)
        existing_pokemon = set()
        if hasattr(self, 'current_replacement_files') and self.current_replacement_files:
            for filename in self.current_replacement_files:
                # Extract Pokemon number from filename (e.g., "003-front-n.gif" -> 3)
                try:
                    parts = filename.split('-')
                    if parts and parts[0].isdigit():
                        pokemon_num = int(parts[0])
                        existing_pokemon.add(pokemon_num)
                except (ValueError, IndexError):
                    pass
        
        # If no existing Pokemon found, use default range 1-712
        if not existing_pokemon:
            existing_pokemon = set(range(1, 713))
        
        # Create Pokemon entries in a proper grid (only for existing Pokemon)
        pokemon_list = sorted(existing_pokemon)
        for i, dex_id in enumerate(pokemon_list):
            row = i // num_columns
            col = i % num_columns
            dex_str = str(dex_id).zfill(3)
            
            # Create frame for this Pokemon entry
            pokemon_frame = tk.Frame(grid_container, bg='#3a3a3a')
            pokemon_frame.grid(row=row, column=col, sticky='ew', padx=2, pady=1)
            
            # Pokemon label
            pokemon_label = tk.Label(pokemon_frame, text=f"#{dex_str}:", 
                                   font=("Segoe UI", 8), bg='#3a3a3a', fg='#e0e0e0',
                                   width=4, anchor='w')
            pokemon_label.pack(side=tk.LEFT, padx=(0, 3))
            
            # Scale entry
            scale_var = tk.StringVar()
            # Load existing value if available
            if dex_str in existing_overrides:
                scale_var.set(str(existing_overrides[dex_str]))
            
            scale_entry = tk.Entry(pokemon_frame, textvariable=scale_var,
                                 font=("Segoe UI", 8), width=5,
                                 bg='#2c2c2c', fg='#e0e0e0',
                                 relief=tk.FLAT, bd=3,
                                 insertbackground='#e0e0e0')
            scale_entry.pack(side=tk.LEFT)
            
            pokemon_entries[dex_str] = scale_var
        
        # Buttons frame at bottom
        buttons_frame = tk.Frame(dialog, bg='#3a3a3a')
        buttons_frame.pack(fill=tk.X, pady=(0, 20), padx=20)
        
        result = [None]
        
        def on_ok():
            # Collect overrides (only non-empty values)
            overrides = {}
            for dex_str, scale_var in pokemon_entries.items():
                value = scale_var.get().strip()
                if value:
                    try:
                        scale_value = float(value)
                        if scale_value < 0:
                            messagebox.showerror("Error", f"Pokemon #{dex_str}: Scale value cannot be negative (minimum: 0.0).")
                            return
                        overrides[dex_str] = scale_value
                    except ValueError:
                        messagebox.showerror("Error", f"Pokemon #{dex_str}: Please enter a valid number.")
                        return
            
            result[0] = overrides
            # Unbind mousewheel before destroying
            canvas.unbind_all("<MouseWheel>")
            dialog.destroy()
        
        def on_cancel():
            # Unbind mousewheel before destroying
            canvas.unbind_all("<MouseWheel>")
            dialog.destroy()
        
        # Buttons on bottom right
        ok_button = tk.Button(buttons_frame, text="Save Overrides", command=on_ok,
                             font=("Segoe UI", 11, "bold"),
                             bg='#27ae60', fg='white',
                             relief=tk.FLAT, bd=0,
                             padx=25, pady=10,
                             cursor='hand2')
        ok_button.pack(side=tk.RIGHT, padx=(10, 0))
        
        cancel_button = tk.Button(buttons_frame, text="Cancel", command=on_cancel,
                                 font=("Segoe UI", 11, "bold"),
                                 bg='#e74c3c', fg='white',
                                 relief=tk.FLAT, bd=0,
                                 padx=25, pady=10,
                                 cursor='hand2')
        cancel_button.pack(side=tk.RIGHT)
        
        # Bind Escape key
        dialog.bind('<Escape>', lambda e: on_cancel())
        
        # Clean up mousewheel binding when dialog is destroyed
        def cleanup_on_destroy(event):
            if event.widget == dialog:
                canvas.unbind_all("<MouseWheel>")
        dialog.bind('<Destroy>', cleanup_on_destroy)
        
        dialog.wait_window()
        return result[0]
    
    def start_processing(self):
        """Start the processing in a separate thread"""
        # Check if file detection is complete before starting processing
        if not self.file_detection_complete:
            self.log_message("⚠️ File detection is still in progress. Please wait for analysis to complete.", "WARNING")
            return
        
        errors = self.validate_inputs()
        if errors:
            messagebox.showerror("Validation Error", "\n".join(errors))
            return
        
        if self.processing:
            return
        
        # Clear preview cache for new processing
        self.preview_cache.clear()
        
        # Show build configuration dialog
        config = self.get_build_configuration()
        if not config:
            return  # User cancelled
        
        # Check for existing .mod file and ask for overwrite confirmation
        output_dir = Path(self.output_dir.get())
        # Sanitize mod name for use in file paths (remove invalid characters)
        safe_mod_name = re.sub(r'[<>:"/\\|?*]', '', config['name'])
        mod_file_path = output_dir / f"{safe_mod_name}.mod"
        if mod_file_path.exists():
            response = messagebox.askyesno(
                "Mod File Exists", 
                f"A mod file '{config['name']}.mod' already exists in the output directory.\n\n"
                f"Do you want to overwrite it?\n\n"
                f"Click 'Yes' to overwrite, 'No' to cancel."
            )
            if not response:
                return  # User chose not to overwrite
            
            # User confirmed overwrite - delete the old mod file
            try:
                mod_file_path.unlink()
                self.log_message(f"🗑️ Deleted existing mod file: {safe_mod_name}.mod", "INFO")
            except Exception as e:
                self.log_message(f"⚠️ Failed to delete existing mod file: {e}", "WARNING")
        
        self.processing = True
        self.paused = False
        self.mod_creation_successful = False  # Reset mod creation flag for new processing
        self.start_button.config(state=tk.DISABLED)
        self.pause_button.config(state=tk.NORMAL, text="⏸", bg='#f39c12')
        self.stop_button.config(state=tk.NORMAL)
        self.unfulfilled_button.config(state=tk.DISABLED)
        # Don't start animated progress - let real progress updates from process_sprites work
        # Initialize progress bar to 0% for real progress tracking
        self.root.after(0, lambda: self.update_progress_bar(0))
        self.status_var.set("Starting processing...")
        
        # Clear logs if requested
        if self.show_logs.get():
            # self.log_text.delete(1.0, tk.END)  # Disabled for testing
            pass
        
        # Start processing thread with config
        self.process_thread = threading.Thread(target=self.process_sprites, args=(config,), daemon=True)
        self.process_thread.start()
    
    def stop_processing(self):
        """Stop the processing"""
        if not self.processing:
            return
        
        self.processing = False
        self.status_var.set("Stopping...")
        
        # Stop animated progress if it's running
        self.stop_animated_progress()
        
        # Re-enable buttons (start button only if we have valid analysis)
        if (hasattr(self, 'current_recommendations') and 
            self.current_recommendations and 
            hasattr(self, 'unfulfilled_files') and 
            self.unfulfilled_files):
            self.start_button.config(state=tk.NORMAL)
        else:
            self.start_button.config(state=tk.DISABLED)
        
        self.pause_button.config(state=tk.DISABLED, text="⏸", bg='#f39c12')
        self.stop_button.config(state=tk.DISABLED)
        # Fix issues button was removed - functionality merged into Issues tab
        self.unfulfilled_button.config(state=tk.NORMAL)
        
        # Stop preview cycling
        self.stop_preview_cycling()
        
        # Note: We can't actually stop the processing thread cleanly,
        # but we can prevent new operations
    
    def pause_processing(self):
        """Pause or resume the processing"""
        try:
            if not self.processing:
                self.log_message("⚠️ Cannot pause - no processing in progress", "WARNING")
                return
            
            if not self.paused:
                # Pause processing
                self.paused = True
                self.status_var.set("Paused...")
                self.pause_button.config(text="▶", bg='#27ae60')
                self.log_message("⏸ Processing paused", "INFO")
            else:
                # Resume processing
                self.paused = False
                self.status_var.set("Resuming...")
                self.pause_button.config(text="⏸", bg='#f39c12')
                self.log_message("▶ Processing resumed", "INFO")
        except Exception as e:
            self.log_message(f"⚠️ Error toggling pause state: {str(e)}", "WARNING")
    
    def process_sprites(self, config):
        """Process sprites in a separate thread"""
        try:
            # Prepare arguments
            move_dir = Path(self.move_dir.get())
            sprite_dir = Path(self.sprite_dir.get())
            output_dir = Path(self.output_dir.get())
            
            # Create working directory for sprite processing
            import tempfile
            # Sanitize mod name for use in directory paths (remove invalid characters)
            safe_mod_name = re.sub(r'[<>:"/\\|?*]', '', config['name'])
            working_dir = Path(tempfile.mkdtemp(prefix=f"sprite_processing_{safe_mod_name}_"))
            
            # Use custom log dir if selected, otherwise use default
            if self.use_custom_log_dir.get():
                log_dir = Path(self.log_dir.get())
            else:
                log_dir = Path("logs")  # Default log directory
            
            limit = None
            if not self.process_all.get():
                try:
                    limit = int(self.limit_var.get())
                except ValueError:
                    limit = None
            
            # Count total files for progress
            move_files = list(move_dir.glob("*.gif")) + list(move_dir.glob("*.png"))
            total_files = len(move_files)
            if limit:
                total_files = min(total_files, limit)
            
            self.root.after(0, lambda: self.status_var.set(f"Processing {total_files} sprites..."))
            
            # Create a custom logger that updates the GUI
            from sprite_processor import configure_logging
            
            # Configure logging
            logger = configure_logging(log_dir)
            
            # Add GUI handler
            gui_handler = GUILogHandler(self)
            gui_handler.setLevel(logging.INFO)
            formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
            gui_handler.setFormatter(formatter)
            logger.addHandler(gui_handler)
            
            # Run the pipeline
            results = {}
            sprite_scale_data = {}  # Track scale factors for dynamic scaling tables
            # Only process GIF and PNG files, filter out other file types like .txt
            move_paths = sorted(p for p in move_dir.iterdir() if p.is_file() and p.suffix.lower() in ['.gif', '.png'])
            if limit:
                move_paths = move_paths[:limit]
            
            processed = 0
            
            # First pass: Copy all bullseye sprites to working directory
            logger.info("📋 Copying all bullseye sprites to working directory...")
            for i, move_path in enumerate(move_paths):
                if not self.processing:
                    break
                
                # Copy the bullseye sprite to working directory
                working_gif_path = working_dir / move_path.name
                if not working_gif_path.exists():
                    import shutil
                    shutil.copy2(move_path, working_gif_path)
                    logger.info(f"📋 Copied bullseye sprite: {move_path.name}")
            
            # Second pass: Process sprites that have replacement sprites
            logger.info("🔄 Processing sprites with replacements...")
            for i, move_path in enumerate(move_paths):
                if not self.processing:
                    break
                
                # Check for pause state
                while self.paused and self.processing:
                    time.sleep(0.1)  # Wait while paused
                if not self.processing:
                    break
                
                sprite_path = sprite_dir / move_path.name
                
                # Update progress
                progress = (i / len(move_paths)) * 100
                self.root.after(0, lambda p=progress: self.update_progress_bar(p))
                self.root.after(0, lambda f=move_path.name: self.status_var.set(f"🎯 Processing FRONT: {f}"))
                
                # Check if we have a replacement sprite for this bullseye sprite
                if not sprite_path.exists():
                    # No replacement sprite, keep the original bullseye sprite
                    logger.info(f"📋 No replacement found for {move_path.name}, keeping original")
                    results[move_path.name] = str(working_dir / move_path.name)
                    
                    # Still check for back sprite processing even when keeping original
                    # Handle gender variants exactly like main files
                    back_file_name = move_path.name.replace('-front-', '-back-').replace('-normal-', '-back-')
                    back_sprite_path = sprite_dir / back_file_name
                    
                    # If exact back file doesn't exist, check for gender variants
                    if not back_sprite_path.exists():
                        # Check for male variant (if front file has -m, look for back-m)
                        if '-m.' in move_path.name:
                            file_ext = move_path.suffix
                            back_male = back_file_name.replace(file_ext, f'-m{file_ext}')
                            back_male_path = sprite_dir / back_male
                            if back_male_path.exists():
                                back_file_name = back_male
                                back_sprite_path = back_male_path
                        # Check for female variant (if front file has -f, look for back-f)
                        elif '-f.' in move_path.name:
                            file_ext = move_path.suffix
                            back_female = back_file_name.replace(file_ext, f'-f{file_ext}')
                            back_female_path = sprite_dir / back_female
                            if back_female_path.exists():
                                back_file_name = back_female
                                back_sprite_path = back_female_path
                        else:
                            # Front file has no gender variant, check for any available back variants
                            file_ext = move_path.suffix
                            back_male = back_file_name.replace(file_ext, f'-m{file_ext}')
                            back_female = back_file_name.replace(file_ext, f'-f{file_ext}')
                            
                            back_male_path = sprite_dir / back_male
                            back_female_path = sprite_dir / back_female
                            
                            if back_male_path.exists():
                                back_file_name = back_male
                                back_sprite_path = back_male_path
                            elif back_female_path.exists():
                                back_file_name = back_female
                                back_sprite_path = back_female_path
                    
                    # Copy back sprite if it exists
                    if back_sprite_path.exists():
                        working_back_path = working_dir / back_file_name
                        if not working_back_path.exists():
                            import shutil
                            shutil.copy2(back_sprite_path, working_back_path)
                            logger.info(f"📋 Copied back sprite: {back_file_name}")
                            results[back_file_name] = str(working_back_path)
                    
                    continue
                
                try:
                    from sprite_processor import process_pair
                    result = process_pair(move_path, sprite_path, working_dir, logger)
                    if result:
                        results[move_path.name] = result
                        processed += 1
                        
                        # Collect canvas size data for dynamic scaling tables
                        if 'canvas_size' in result:
                            sprite_scale_data[move_path.name] = result['canvas_size']
                        
                        # Update preview with the processed GIF
                        working_gif_path = working_dir / move_path.name
                        if working_gif_path.exists():
                            self.root.after(0, lambda path=working_gif_path, name=move_path.name: self.update_preview(path, name))
                        
                        # Check if there's a corresponding back file to process
                        # Handle gender variants exactly like main files
                        back_file_name = move_path.name.replace('-front-', '-back-').replace('-normal-', '-back-')
                        back_sprite_path = sprite_dir / back_file_name
                        
                        # If exact back file doesn't exist, check for gender variants
                        if not back_sprite_path.exists():
                            # Check for male variant (if front file has -m, look for back-m)
                            if '-m.gif' in move_path.name:
                                back_male = back_file_name.replace('.gif', '-m.gif')
                                back_male_path = sprite_dir / back_male
                                if back_male_path.exists():
                                    back_file_name = back_male
                                    back_sprite_path = back_male_path
                            # Check for female variant (if front file has -f, look for back-f)
                            elif '-f.gif' in move_path.name:
                                back_female = back_file_name.replace('.gif', '-f.gif')
                                back_female_path = sprite_dir / back_female
                                if back_female_path.exists():
                                    back_file_name = back_female
                                    back_sprite_path = back_female_path
                            else:
                                # Front file has no gender variant, check for any available back variants
                                back_male = back_file_name.replace('.gif', '-m.gif')
                                back_female = back_file_name.replace('.gif', '-f.gif')
                                
                                back_male_path = sprite_dir / back_male
                                back_female_path = sprite_dir / back_female
                                
                                if back_male_path.exists():
                                    back_file_name = back_male
                                    back_sprite_path = back_male_path
                                elif back_female_path.exists():
                                    back_file_name = back_female
                                    back_sprite_path = back_female_path
                        
                        if back_sprite_path.exists():
                            # Process back file with resizing to match front file dimensions
                            self.root.after(0, lambda f=back_file_name: self.status_var.set(f"🔄 Processing BACK: {f}"))
                            logger.info(f"🔄 Processing back file: {back_file_name}")
                            
                            try:
                                from PIL import Image
                                import shutil
                                
                                # Load original bullseye file to get original canvas size (not scaled)
                                with Image.open(move_path) as original_img:
                                    original_canvas_size = original_img.size
                                
                                # Get the bounding box from the main sprite processing result
                                # The bounding box is stored in the result from process_pair
                                if 'main_bbox' in result:
                                    bbox = result['main_bbox']
                                    bbox_width = bbox[2] - bbox[0]
                                    bbox_height = bbox[3] - bbox[1]
                                else:
                                    # Fallback: use the entire canvas size
                                    bbox_width, bbox_height = original_canvas_size
                                
                                # Load and resize back file using the bounding box dimensions
                                from sprite_processor import load_animated_rgba_frames, union_frame_bbox
                                
                                # Load all frames from the back sprite
                                back_frames, back_durations, back_loop, back_disposals = load_animated_rgba_frames(back_sprite_path)
                                
                                # Get the union bounding box of the back sprite
                                back_bbox = union_frame_bbox(back_frames)
                                if back_bbox:
                                    back_content_width = back_bbox[2] - back_bbox[0]
                                    back_content_height = back_bbox[3] - back_bbox[1]
                                    
                                    # Calculate scale so back sprite's largest dimension is larger than front sprite's largest dimension
                                    # This makes back sprites more prominent and appropriately sized
                                    front_max_dimension = max(bbox_width, bbox_height)
                                    back_max_dimension = max(back_content_width, back_content_height)
                                    
                                    # Scale so the back sprite's largest dimension is 1.0x the front sprite's largest dimension
                                    # This ensures back sprites are the same size as front sprites
                                    target_back_size = front_max_dimension * 1.0
                                    scale = target_back_size / back_max_dimension
                                    
                                    # Calculate the actual size after scaling
                                    target_width = max(1, int(back_content_width * scale))
                                    target_height = max(1, int(back_content_height * scale))
                                    
                                    resized_back_frames = []
                                    for frame in back_frames:
                                        frame = frame.convert("RGBA")
                                        
                                        # Crop to the back sprite's bounding box
                                        cropped_frame = frame.crop(back_bbox)
                                        
                                        # Resize maintaining aspect ratio to fit within main sprite's bounding box
                                        resized_frame = cropped_frame.resize((target_width, target_height), Image.Resampling.NEAREST)
                                        
                                        # Create a canvas the same size as the original bullseye canvas (not scaled)
                                        canvas_frame = Image.new('RGBA', original_canvas_size, (0, 0, 0, 0))
                                        
                                        # Position the back sprite at the bottom center of the canvas
                                        # Center horizontally and place with 10px margin from bottom
                                        paste_x = (original_canvas_size[0] - target_width) // 2   # center horizontally
                                        paste_y = original_canvas_size[1] - target_height - 10    # 10px margin from bottom
                                        canvas_frame.paste(resized_frame, (paste_x, paste_y), resized_frame)
                                        
                                        resized_back_frames.append(canvas_frame)
                                    
                                    current_size = back_frames[0].size
                                    new_size = resized_back_frames[0].size
                                    back_output_path = working_dir / back_file_name
                                    
                                    if len(resized_back_frames) > 1:
                                        resized_back_frames[0].save(back_output_path, format='GIF', save_all=True,
                                                                   append_images=resized_back_frames[1:],
                                                                   duration=back_durations, loop=back_loop,
                                                                   disposal=back_disposals)
                                    else:
                                        resized_back_frames[0].save(back_output_path, format='GIF')
                                        
                                    logger.info(f"🔄 Resized back file {back_file_name}: {current_size[0]}x{current_size[1]} -> {new_size[0]}x{new_size[1]} (scale: {scale:.2f}, max_dim is 1.0x front_max: {front_max_dimension})")
                                        
                                    # Update preview with the resized back GIF
                                    self.root.after(0, lambda path=back_output_path, name=back_file_name: self.update_preview(path, name))
                                        
                                    results[back_file_name] = str(back_output_path)
                                    processed += 1
                                    logger.info(f"✅ Successfully processed back file: {back_file_name}")
                                else:
                                    logger.warning(f"⚠️ No content found in back file: {back_file_name}")
                                        
                            except Exception as back_exc:
                                logger.exception(f"❌ Failed to process back file {back_file_name}: {back_exc}")
                        
                except Exception as exc:
                    logger.exception("%s: failed to process pair due to %s", move_path.name, exc)
            
            # No orphaned sprite processing - extra files are simply ignored
            
            # Save results
            summary_path = log_dir / "bounding_boxes.json"
            with summary_path.open("w", encoding="utf-8") as fh:
                json.dump(results, fh, indent=2)
            
            # Update final status
            self.root.after(0, lambda: self.stop_animated_progress())
            self.root.after(0, lambda: self.status_var.set(f"Completed! Processed {processed} sprites successfully"))
            
            # Count different types of processed sprites for detailed summary
            bullseye_names = [p.name for p in move_paths]
            
            # Count sprites by type
            custom_replacements = len([f for f in results.keys() if f in bullseye_names])
            back_sprites = len([f for f in results.keys() if '-back-' in f])
            remaining_bullseye = len(bullseye_names) - custom_replacements
            
            # Build summary parts
            summary_parts = []
            if custom_replacements > 0:
                summary_parts.append(f"{custom_replacements} custom replacements")
            if remaining_bullseye > 0:
                summary_parts.append(f"{remaining_bullseye} remaining bullseye")
            if back_sprites > 0:
                summary_parts.append(f"{back_sprites} back sprites")
            
            total_in_mod = custom_replacements + remaining_bullseye + back_sprites
            detailed_summary = f"🎉 SUCCESS: Processing completed! {processed} sprites processed -> {total_in_mod} sprites in mod ({', '.join(summary_parts)})"
            self.root.after(0, lambda: self.log_message(detailed_summary, "SUCCESS"))
            
            # Stop preview cycling to prevent errors after cleanup
            self.root.after(0, lambda: self.stop_preview_cycling())
            
            # Automatically create mod package
            self.root.after(0, lambda: self.log_message("📦 Creating mod package...", "INFO"))
            try:
                # Create mod packager instance
                mod_packager = ModPackager(logger)
                
                # Use the mod name provided by the user
                
                # Create the mod package
                mod_file = mod_packager.create_mod_package(
                    source_dir=working_dir,
                    output_dir=Path(self.output_dir.get()),
                    mod_name=config['name'],
                    mod_version=config['version'],
                    mod_author=config['authors'],
                    mod_description=config['description'],
                    target_game="PokeMMO",
                    sprite_scale_data=sprite_scale_data,
                    custom_scaling=config.get('custom_scaling')
                )
                
                # Log success
                self.root.after(0, lambda: self.log_message(f"✅ Mod package created: {mod_file.name}", "SUCCESS"))
                self.root.after(0, lambda: self.log_message(f"📁 Mod location: {mod_file.parent}", "INFO"))
                
                # Update status to show mod creation
                self.root.after(0, lambda: self.status_var.set(f"✅ Mod created: {mod_file.name}"))
                
                # Re-enable start button after successful mod creation
                self.root.after(0, lambda: self.start_button.config(state=tk.NORMAL))
                
                # Set flag to indicate successful mod creation
                self.mod_creation_successful = True
                
            except Exception as mod_error:
                self.root.after(0, lambda: self.log_message(f"⚠️ Failed to create mod package: {mod_error}", "WARNING"))
                self.root.after(0, lambda: self.log_message("📁 Sprites are still available in the output directory", "INFO"))
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            
            # Log user-friendly error information
            error_type = type(e).__name__
            error_msg = str(e)
            
            # Provide user-friendly error messages based on error type
            if "PermissionError" in error_type:
                user_msg = "Permission denied. Please check that you have write access to the output directory and that no files are currently in use."
            elif "FileNotFoundError" in error_type:
                user_msg = "Required file or directory not found. Please check that all directories exist and contain the expected files."
            elif "MemoryError" in error_type:
                user_msg = "Insufficient memory. Try processing fewer sprites at once or close other applications."
            elif "OSError" in error_type:
                user_msg = "File system error. Please check that all paths are valid and accessible."
            else:
                user_msg = f"Unexpected error: {error_msg}"
            
            self.root.after(0, lambda: self.log_message(f"❌ ERROR: {user_msg}", "ERROR"))
            self.root.after(0, lambda: self.log_message(f"❌ Technical details: {error_type}: {error_msg}", "ERROR"))
            
            # Update status with user-friendly message
            self.root.after(0, lambda: self.status_var.set("Processing failed - see log for details"))
        finally:
            # Clean up working directory
            try:
                if 'working_dir' in locals() and working_dir.exists():
                    import shutil
                    shutil.rmtree(working_dir)
                    logger.info(f"🧹 Cleaned up working directory: {working_dir}")
            except Exception as cleanup_error:
                logger.warning(f"⚠️ Failed to clean up working directory: {cleanup_error}")
            
            self.processing = False
            self.paused = False
            
            # Set progress to 100% when processing completes
            self.root.after(0, lambda: self.update_progress_bar(100))
            
            # Re-enable start button if we have valid analysis results OR if mod creation was successful
            if ((hasattr(self, 'current_recommendations') and 
                self.current_recommendations and 
                hasattr(self, 'unfulfilled_files') and 
                self.unfulfilled_files) or
                getattr(self, 'mod_creation_successful', False)):
                self.root.after(0, lambda: self.start_button.config(state=tk.NORMAL))
            else:
                self.root.after(0, lambda: self.start_button.config(state=tk.DISABLED))
            
            self.root.after(0, lambda: self.pause_button.config(state=tk.DISABLED, text="⏸", bg='#f39c12'))
            self.root.after(0, lambda: self.stop_button.config(state=tk.DISABLED))
            # Fix issues button was removed - functionality merged into Issues tab
            self.root.after(0, lambda: self.unfulfilled_button.config(state=tk.NORMAL))
    
    def log_message(self, message, level="INFO"):
        """Add a message to the log display"""
        if self.show_logs.get():
            # Add timestamp and level
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_message = f"[{timestamp}] {level}: {message}"
            
            # Temporarily enable the widget to add text
            self.log_text.config(state=tk.NORMAL)
            
            # Color coding based on level
            self.log_text.insert(tk.END, formatted_message + "\n")
            
            # Apply color tags
            if level == "ERROR":
                self.log_text.tag_add("error", f"end-{len(formatted_message)+1}c", "end-1c")
                self.log_text.tag_config("error", foreground="#e74c3c")
            elif level == "WARNING":
                self.log_text.tag_add("warning", f"end-{len(formatted_message)+1}c", "end-1c")
                self.log_text.tag_config("warning", foreground="#f39c12")
            elif level == "SUCCESS":
                self.log_text.tag_add("success", f"end-{len(formatted_message)+1}c", "end-1c")
                self.log_text.tag_config("success", foreground="#27ae60")
            elif level == "INFO":
                self.log_text.tag_add("info", f"end-{len(formatted_message)+1}c", "end-1c")
                self.log_text.tag_config("info", foreground="#3498db")
            
            # Disable the widget again to prevent editing
            self.log_text.config(state=tk.DISABLED)
            
            # Only auto-scroll if we're already near the bottom
            # This prevents scrolling past important warnings
            current_position = self.log_text.yview()[1]
            if current_position > 0.8:  # Only scroll if we're in the bottom 20%
                self.log_text.see(tk.END)
    
    def clear_preview(self):
        """Clear the preview area"""
        # Stop any running preview cycle
        if self.preview_cycle_timer:
            self.root.after_cancel(self.preview_cycle_timer)
            self.preview_cycle_timer = None
        
        # Clear the queue and reset state
        self.preview_queue.clear()
        self.current_preview_index = 0
        
        # Clear the preview label
        if self.preview_label:
            self.preview_label.configure(image="", text="No sprites\nprocessed yet")
            self.preview_label.image = None
    
    def update_preview(self, gif_path, filename):
        """Add a new processed GIF to the preview queue"""
        try:
            if self.preview_label is None:
                return
            
            # Add to preview queue (limit to 10 sprites to avoid memory issues)
            if len(self.preview_queue) >= 10:
                self.preview_queue.pop(0)  # Remove oldest
            
            self.preview_queue.append((gif_path, filename))
            
            # Start cycling if this is the first sprite
            if len(self.preview_queue) == 1:
                self.start_preview_cycling()
            
        except Exception as e:
            # If preview fails, just log it but don't crash
            self.log_message(f"Preview update failed for {filename}: {str(e)}", "WARNING")
    
    def start_preview_cycling(self):
        """Start cycling through the preview queue"""
        if not self.preview_queue:
            return
        
        self.cycle_to_next_preview()
    
    def cycle_to_next_preview(self):
        """Cycle to the next preview in the queue"""
        if not self.preview_queue:
            return
        
        # Get current sprite
        gif_path, filename = self.preview_queue[self.current_preview_index]
        
        try:
            # Check cache first for faster loading
            cache_key = str(gif_path)
            if cache_key in self.preview_cache:
                photo = self.preview_cache[cache_key]
                # Move to end of LRU list (most recently used)
                if cache_key in self.preview_cache_order:
                    self.preview_cache_order.remove(cache_key)
                self.preview_cache_order.append(cache_key)
            else:
                # Limit cache size to prevent memory growth
                if len(self.preview_cache) >= self.preview_cache_max_size:
                    # Remove least recently used entry
                    if self.preview_cache_order:
                        oldest_key = self.preview_cache_order.pop(0)
                        if oldest_key in self.preview_cache:
                            del self.preview_cache[oldest_key]
            
                # Load only the first frame for faster preview
                from PIL import Image, ImageTk
                
                try:
                    img = Image.open(gif_path)
                    
                    # For animated GIFs, get the first frame
                    if hasattr(img, 'n_frames') and img.n_frames > 1:
                        img.seek(0)  # Go to first frame
                    
                    # Use a reasonable container size to minimize scaling and pixelation
                    max_size = 180  # Reasonable size that prevents overflow
                    scale_x = max_size / img.width
                    scale_y = max_size / img.height
                    
                    # Only scale down if absolutely necessary, never scale up
                    base_scale = min(scale_x, scale_y, 1.0)  # Never scale up beyond original size
                    
                    new_width = int(img.width * base_scale)
                    new_height = int(img.height * base_scale)
                    
                    # Always use LANCZOS for best quality in preview
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    
                    # Convert to PhotoImage for tkinter
                    photo = ImageTk.PhotoImage(img)
                    
                    # Cache the processed image
                    self.preview_cache[cache_key] = photo
                    self.preview_cache_order.append(cache_key)
                    
                    # Update the preview label with centered image
                    self.preview_label.configure(image=photo, text="", compound=tk.CENTER)
                    self.preview_label.image = photo  # Keep a reference
                    
                except (IOError, OSError, Image.UnidentifiedImageError) as e:
                    self.log_message(f"Preview update failed for {filename}: Invalid or corrupted image file", "WARNING")
                    return
                except Exception as e:
                    self.log_message(f"Preview update failed for {filename}: {str(e)}", "WARNING")
                    return
            
            # Move to next sprite in queue
            self.current_preview_index = (self.current_preview_index + 1) % len(self.preview_queue)
            
            # Schedule next cycle
            self.preview_cycle_timer = self.root.after(self.preview_display_duration, self.cycle_to_next_preview)
            
        except Exception as e:
            # If preview fails, just log it but don't crash
            self.log_message(f"Preview cycling failed for {filename}: {str(e)}", "WARNING")
            # Stop cycling if files are missing (likely due to cleanup)
            if "No such file or directory" in str(e):
                self.stop_preview_cycling()
                return
            # Still schedule next cycle for other errors
            self.current_preview_index = (self.current_preview_index + 1) % len(self.preview_queue)
            self.preview_cycle_timer = self.root.after(self.preview_display_duration, self.cycle_to_next_preview)
    
    def stop_preview_cycling(self):
        """Stop the preview cycling"""
        if hasattr(self, 'preview_cycle_timer') and self.preview_cycle_timer:
            self.root.after_cancel(self.preview_cycle_timer)
            self.preview_cycle_timer = None
        
        # Clear the preview queue
        self.preview_queue.clear()
        self.current_preview_index = 0
        
        # Show a completion message in the preview
        if self.preview_label:
            self.preview_label.configure(image="", text="✅ Processing Complete")
            self.preview_label.image = None
    
    def multi_step_resize(self, image, target_size):
        """Resize image using multiple steps for better quality on large scale factors"""
        from PIL import Image
        
        current = image
        current_size = current.size
        target_width, target_height = target_size
        
        # Calculate scale factor
        scale_factor = max(target_width / current_size[0], target_height / current_size[1])
        
        # For small scale factors, use smart resampling
        if scale_factor <= 1.5:
            # Use smart resampling: NEAREST for integer scaling, LANCZOS for non-integer
            scale_x = target_size[0] / current.width
            scale_y = target_size[1] / current.height
            if scale_x == int(scale_x) and scale_y == int(scale_y) and scale_x >= 1.0 and scale_y >= 1.0:
                return current.resize(target_size, Image.Resampling.NEAREST)
            else:
                return current.resize(target_size, Image.Resampling.LANCZOS)
        
        # For large scale factors, use multiple steps with LANCZOS for smoother results
        steps = []
        if scale_factor > 4:
            steps = [2.0, 2.0]  # Two steps of 2x each
        elif scale_factor > 2:
            steps = [2.0]  # One step of 2x
        else:
            steps = [scale_factor]  # Single step
        
        # Apply scaling steps with smart resampling
        for step_scale in steps:
            new_width = int(current_size[0] * step_scale)
            new_height = int(current_size[1] * step_scale)
            # Use smart resampling: NEAREST for integer scaling, LANCZOS for non-integer
            scale_x = new_width / current_size[0]
            scale_y = new_height / current_size[1]
            if scale_x == int(scale_x) and scale_y == int(scale_y) and scale_x >= 1.0 and scale_y >= 1.0:
                current = current.resize((new_width, new_height), Image.Resampling.NEAREST)
            else:
                current = current.resize((new_width, new_height), Image.Resampling.LANCZOS)
            current_size = current.size
        
        return current
    
    def clear_logs(self):
        """Clear the log display"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    # show_file_recommendations method removed - functionality merged into Issues tab
    
    def copy_issue_to_clipboard(self, issue):
        """Copy a single issue to clipboard"""
        import tkinter as tk
        
        display_name, _ = self._get_action_display_info(issue['action'])
        issue_text = f"{display_name}: {issue['from']} - {issue['reason']}"
        if 'to' in issue:
            issue_text += f" -> {issue['to']}"
        
        self.root.clipboard_clear()
        self.root.clipboard_append(issue_text)
        self.root.update()  # Required for clipboard to work
        
        # Show brief confirmation
        messagebox.showinfo("Copied", f"Issue copied to clipboard:\n{issue_text}")
    
    def copy_all_issues_to_clipboard(self, issues):
        """Copy all issues to clipboard in a formatted list"""
        import tkinter as tk
        
        issue_list = []
        for issue in issues:
            display_name, _ = self._get_action_display_info(issue['action'])
            issue_text = f"{display_name}: {issue['from']} - {issue['reason']}"
            if 'to' in issue:
                issue_text += f" -> {issue['to']}"
            issue_list.append(issue_text)
        
        all_issues_text = "\n".join(issue_list)
        
        self.root.clipboard_clear()
        self.root.clipboard_append(all_issues_text)
        self.root.update()  # Required for clipboard to work
        
        # Show brief confirmation
        messagebox.showinfo("Copied", f"All {len(issues)} issues copied to clipboard!")
    
    def apply_recommendations(self, popup):
        """
        Apply the selected file operation recommendations with proper ordering.
        
        This method executes file operations based on user-selected recommendations.
        It handles various operation types including rename, clone, replacement, and removal
        operations with comprehensive error handling and progress tracking.
        
        Args:
            popup: The popup window containing the recommendations interface
            
        Each recommendation dictionary contains:
        - action (str): Type of operation ('rename', 'clone', 'create_gender_variant', etc.)
        - from (str or list): Source file(s) for the operation
        - to (str or list): Target file(s) for the operation
        - reason (str): Human-readable description of why the operation is needed
        
        The method includes:
        - Comprehensive error handling for file operations
        - Progress tracking and user feedback
        - Retry mechanisms for permission errors
        - Verification of successful operations
        - Detailed logging of all operations
        
        Returns:
            int: Number of successfully applied operations
        """
        import shutil
        
        sprite_dir = Path(self.sprite_dir.get())
        if not sprite_dir.exists():
            messagebox.showerror("Error", "Replacement sprite directory not found!")
            return
        
        applied_count = 0
        failed_count = 0
        
        # Define operation priority to prevent dependency issues
        operation_priority = {
            'clone': 1,                           # Create files first
            'create_gender_variant': 2,           # Create gender variants from base files
            'create_gender_variant_from_other': 2, # Create gender variants from other gender
            'create_base_from_male': 2,           # Create base files from male variants
            'create_base_from_female': 2,         # Create base files from female variants
            'replacement': 3,                     # Create variants from base files
            'rename': 4,                          # Fix naming issues
            'retain_extra': 5,                    # Keep extra files
            'remove_base': 6,                     # Remove conflicting base files
            'remove': 7,                          # Remove files last
            'cleanup': 8                          # Final cleanup operations
        }
        
        # Get selected recommendations and sort by priority
        selected_recommendations = []
        for i, (rec, var) in enumerate(zip(self.current_recommendations, self.recommendation_vars)):
            if var.get():  # If checkbox is selected
                selected_recommendations.append(rec)
        
        # Sort by operation priority to prevent cascading failures
        selected_recommendations.sort(key=lambda x: operation_priority.get(x['action'], 999))
        
        # Apply operations in priority order
        # Starting to apply selected recommendations
        for i, rec in enumerate(selected_recommendations):
            # Processing recommendation
            try:
                # Handle both single operations and comprehensive operations
                if isinstance(rec['from'], list):
                    # For comprehensive operations, check if any source exists
                    source_exists = any((sprite_dir / source_file).exists() for source_file in rec['from'])
                    if not source_exists and rec['action'] not in ['retain_extra']:
                        continue
                else:
                    # For single operations
                    source_path = sprite_dir / rec['from']
                    if not source_path.exists() and rec['action'] not in ['retain_extra']:
                        continue
                    
                if rec['action'] == 'rename':
                    source_path = sprite_dir / rec['from']
                    target_path = sprite_dir / rec['to']
                    # Processing rename operation
                    
                    # Check actual filenames in directory to handle case sensitivity properly
                    actual_files = [f.name for f in sprite_dir.iterdir() if f.is_file()]
                    source_exists = rec['from'] in actual_files
                    target_exists = rec['to'] in actual_files
                    
                    # Checking source and target existence
                    
                    if source_exists and not target_exists:
                        # Additional debugging for file system issues
                        # Checking source file attributes
                        
                        # Try a different approach - use os.rename instead of shutil.copy2
                        try:
                            # Attempting direct rename using os.rename
                            import os
                            os.rename(str(source_path), str(target_path))
                            # Successfully renamed using os.rename
                            applied_count += 1
                        except Exception as e:
                            self.log_message(f"ERROR: os.rename failed: {e}", "ERROR")
                            # Fallback to copy + delete with retry mechanism
                            max_retries = 3
                            for attempt in range(max_retries):
                                try:
                                    # Use copy + delete instead of rename to be safer
                                    # Starting copy+delete operation
                                    shutil.copy2(source_path, target_path)
                                    # Copy completed, checking target
                                    # Verify the copy was successful before deleting original
                                    if target_path.exists():
                                        # Target file exists after copy, deleting source
                                        source_path.unlink()  # Delete the original file
                                        # Successfully renamed
                                        applied_count += 1
                                        break  # Success, exit retry loop
                                    else:
                                        self.log_message(f"ERROR: Copy failed - target file {rec['to']} does not exist after copy", "ERROR")
                                        break  # Exit retry loop
                                except PermissionError as e:
                                    if attempt < max_retries - 1:
                                        self.log_message(f"WARNING: Permission error (attempt {attempt + 1}/{max_retries}): {e}", "WARNING")
                                        self.log_message(f"INFO: Retrying in 1 second...", "INFO")
                                        import time
                                        time.sleep(1)
                                    else:
                                        self.log_message(f"ERROR: Failed to rename {rec['from']} to {rec['to']} after {max_retries} attempts: {e}", "ERROR")
                                        self.log_message(f"INFO: File may be in use by another program (Windows Explorer, image viewer, etc.)", "INFO")
                                except Exception as e:
                                    self.log_message(f"ERROR: Failed to rename {rec['from']} to {rec['to']}: {e}", "ERROR")
                                    import traceback
                                    traceback.print_exc()
                                    break  # Exit retry loop for non-permission errors
                    elif not source_exists:
                        # Source file already processed or doesn't exist - skip silently
                        # Source file does not exist - skipping
                        pass
                    elif target_exists:
                        # Target already exists - this could be an extension fix or case sensitivity fix
                        # Target exists, checking reason
                        # Check if this is an extension fix by comparing the source and target
                        if ('..gif' in rec['from'] or '..png' in rec['from'] or 
                            rec['from'].endswith('.gif.gif') or rec['from'].endswith('.png.png')):
                            # This is an extension fix - remove the source file since target exists
                            # Extension fix - removing duplicate source file
                            source_path.unlink()
                            applied_count += 1
                        elif 'case sensitivity' in rec['reason']:
                            # Case sensitivity fix - target already exists, skip operation (correct file already exists)
                            # Case sensitivity fix - skipping (target already exists)
                            applied_count += 1
                        elif 'normal to front' in rec['reason']:
                            # This is a normal to front fix - target already exists, skip operation (correct file already exists)
                            # Normal to front fix - skipping (target already exists)
                            applied_count += 1
                        elif 'malformed filename' in rec['reason']:
                            # This is a malformed filename fix - remove the source file since target exists
                            source_path.unlink()
                            applied_count += 1
                        else:
                            # This is a real conflict - fail the operation
                            failed_count += 1
                            self.log_message(f"FAILED: Rename operation - target already exists: {rec['from']} -> {rec['to']}", "ERROR")
                
                    elif rec['action'] == 'clone':
                        source_path = sprite_dir / rec['from']
                        target_path = sprite_dir / rec['to']
                        if source_path.exists() and not target_path.exists():
                            # Copy the file with the new name (keep original)
                            shutil.copy2(source_path, target_path)
                            applied_count += 1
                        elif not source_path.exists():
                            # Source file already processed or doesn't exist - skip silently
                            pass
                        else:
                            # Target already exists - this is a conflict
                            failed_count += 1
                            self.log_message(f"FAILED: Clone operation - target already exists: {rec['from']} -> {rec['to']}", "ERROR")
                
                elif rec['action'] in ['create_gender_variant', 'create_gender_variant_from_other', 'create_base_from_male', 'create_base_from_female']:
                    # Handle operations with multiple sources and targets (comprehensive operations)
                    if isinstance(rec['from'], list) and isinstance(rec['to'], list):
                        # Comprehensive operation with multiple sources and targets
                        success_count = 0
                        for source_file, target_file in zip(rec['from'], rec['to']):
                            source_path = sprite_dir / source_file
                            target_path = sprite_dir / target_file
                            
                            if source_path.exists() and not target_path.exists():
                                shutil.copy2(source_path, target_path)
                                success_count += 1
                                print(f"CREATE: {source_file} -> {target_file}")
                        
                        if success_count > 0:
                            applied_count += 1
                        else:
                            failed_count += 1
                            self.log_message(f"FAILED: Create operation - no files created: {rec['from']} -> {rec['to']}", "ERROR")
                    else:
                        # Single operation
                        source_path = sprite_dir / rec['from']
                        target_path = sprite_dir / rec['to']
                        if source_path.exists() and not target_path.exists():
                            # Copy the file with the new name (keep original)
                            shutil.copy2(source_path, target_path)
                            applied_count += 1
                        elif not source_path.exists():
                            # Source file already processed or doesn't exist - skip silently
                            pass
                        else:
                            # Target already exists - this is a conflict
                            failed_count += 1
                            self.log_message(f"FAILED: Create operation - target already exists: {rec['from']} -> {rec['to']}", "ERROR")
                
                elif rec['action'] == 'replacement':
                    source_path = sprite_dir / rec['from']
                    if source_path.exists():
                        # Copy to all target files in the group
                        success_count = 0
                        for target_file in rec['to']:
                            target_path = sprite_dir / target_file
                            if not target_path.exists():
                                # Ensure parent directory exists
                                target_path.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(source_path, target_path)
                                success_count += 1
                        
                        # Only delete source file if at least one target was created
                        if success_count > 0:
                            source_path.unlink()
                            applied_count += 1
                elif rec['action'] == 'comprehensive_replacement':
                    source_path = sprite_dir / rec['from']
                    if source_path.exists():
                        # Copy to all target files in the group (comprehensive operation)
                        success_count = 0
                        for target_file in rec['to']:
                            target_path = sprite_dir / target_file
                            if not target_path.exists():
                                # Ensure parent directory exists
                                target_path.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(source_path, target_path)
                                success_count += 1
                        
                        # Remove additional files if specified
                        if rec.get('files_to_remove'):
                            for file_to_remove in rec['files_to_remove']:
                                remove_path = sprite_dir / file_to_remove
                                if remove_path.exists():
                                    remove_path.unlink()
                        
                        # Only delete source file if at least one target was created
                        if success_count > 0:
                            source_path.unlink()
                            applied_count += 1
                elif rec['action'] == 'remove_base':
                    source_path = sprite_dir / rec['from']
                    if source_path.exists():
                        # Simply delete the conflicting base file
                        source_path.unlink()
                        applied_count += 1
                    else:
                        # File already removed or doesn't exist - skip silently
                        pass
                elif rec['action'] == 'remove':
                    source_path = sprite_dir / rec['from']
                    if source_path.exists():
                        # Delete the file
                        source_path.unlink()
                        applied_count += 1
                    else:
                        # File already removed or doesn't exist - skip silently
                        pass
                elif rec['action'] == 'cleanup':
                    # Handle consolidated cleanup operation
                    cleanup_files = rec.get('cleanup_files', [rec['from']])
                    files_removed = 0
                    for cleanup_file in cleanup_files:
                        cleanup_path = sprite_dir / cleanup_file
                        if cleanup_path.exists():
                            cleanup_path.unlink()
                            files_removed += 1
                    if files_removed > 0:
                        applied_count += 1
                        self.log_message(f"Cleaned up {files_removed} files", "INFO")
                elif rec['action'] == 'retain_extra':
                    # No action needed - just retain the file as is
                    applied_count += 1
                    
            except Exception as e:
                failed_count += 1
                self.log_message(f"Failed to {rec['action']} {rec['from']}: {str(e)}", "ERROR")
                if isinstance(rec['from'], list):
                    self.log_message(f"   Source files: {rec['from']}", "ERROR")
                else:
                    self.log_message(f"   Source path: {sprite_dir / rec['from']}", "ERROR")
                    if rec['action'] == 'replacement':
                        self.log_message(f"   Target files: {rec['to']}", "ERROR")
                # Log the specific error for debugging
                import traceback
                self.log_message(f"   Traceback: {traceback.format_exc()}", "ERROR")
        
        # Close popup
        popup.destroy()
        
        # Show results
        if applied_count > 0:
            self.log_message(f"✅ Applied {applied_count} file operations successfully", "SUCCESS")
            if failed_count > 0:
                self.log_message(f"⚠️ {failed_count} operations failed", "WARNING")
            
            # Clear cached recommendations so next "Fix Issues" shows fresh data
            if hasattr(self, 'current_recommendations'):
                self.current_recommendations = []
            
            # Re-run file detection to show updated results with background threading
            self.root.after(500, self.refresh_analysis)
        else:
            messagebox.showinfo("No Operations", "No file operations were applied.")
    
    def show_unfulfilled_files(self):
        """Show comprehensive issues popup with three tabs: Front Issues, Back Issues, and Fixes"""
        # Immediately reset button state to prevent white background lag
        self.root.after_idle(lambda: self.unfulfilled_button.config(state='normal', bg='#e74c3c'))
        
        # Check if analysis is still running
        current_status = self.status_var.get()
        if "Analyzing" in current_status or "🔍" in current_status:
            self.log_message("Analysis is still running. Please wait for completion.", "WARNING")
            return
        
        # Create popup window
        popup = tk.Toplevel(self.root)
        popup.title("Issues & Fixes")
        popup.geometry("1200x800")
        popup.configure(bg='#2a2a2a')
        popup.resizable(True, True)
        
        # Make popup modal
        popup.transient(self.root)
        popup.grab_set()
        
        # Ensure button returns to normal state after popup is created
        self.root.after_idle(lambda: self.unfulfilled_button.config(state='normal', bg='#e74c3c'))
        
        # Reset button state when popup is closed
        def on_closing():
            self.unfulfilled_button.config(state='normal', bg='#e74c3c')
            popup.destroy()
        
        popup.protocol("WM_DELETE_WINDOW", on_closing)
        
        # Center the popup
        popup.update_idletasks()
        x = (popup.winfo_screenwidth() // 2) - (1200 // 2)
        y = (popup.winfo_screenheight() // 2) - (800 // 2)
        popup.geometry(f"1200x800+{x}+{y}")
        
        # Header
        header_frame = tk.Frame(popup, bg='#2a2a2a')
        header_frame.pack(fill=tk.X, padx=20, pady=20)
        
        # Calculate counts
        total_issues = len(self.unfulfilled_files) if hasattr(self, 'unfulfilled_files') and self.unfulfilled_files else 0
        total_fixes = len(self.current_recommendations) if hasattr(self, 'current_recommendations') and self.current_recommendations else 0
        
        # Calculate fixable vs unfixable issues
        fixable_issues = 0
        unfixable_issues = 0
        if hasattr(self, 'unfulfilled_files') and self.unfulfilled_files:
            fixable_issues = sum(1 for is_fixable in self.unfulfilled_files.values() if is_fixable)
            unfixable_issues = total_issues - fixable_issues
        
        title_label = tk.Label(header_frame, text="🔧 Issues & Fixes", 
                              font=("Segoe UI", 16, "bold"), 
                              bg='#2a2a2a', fg='#e0e0e0')
        title_label.pack()
        
        # Add counts below the title
        counts_text = f"📊 {total_issues} Total Issues • ✅ {fixable_issues} Fixable • ❌ {unfixable_issues} Unfixable • 🔧 {total_fixes} Available Fixes"
        counts_label = tk.Label(header_frame, text=counts_text, 
                              font=("Segoe UI", 12), 
                              bg='#2a2a2a', fg='#b0b0b0')
        counts_label.pack(pady=(5, 0))
        
        # Create notebook for tabs
        notebook = tk.ttk.Notebook(popup)
        notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # Configure notebook style
        style = tk.ttk.Style()
        style.theme_use('clam')
        style.configure('TNotebook', background='#2a2a2a', borderwidth=0)
        style.configure('TNotebook.Tab', 
                       background='#3a3a3a', 
                       foreground='#e0e0e0', 
                       padding=[20, 10],
                       focuscolor='none',  # Remove focus outline
                       borderwidth=0)
        # Make selected tab larger and more prominent
        style.configure('TNotebook.Tab', 
                       padding=[20, 10])  # Default padding
        style.map('TNotebook.Tab', 
                 background=[('selected', '#4a4a4a'), ('active', '#4a4a4a')],
                 focuscolor=[('!focus', 'none')],  # Remove focus outline
                 padding=[('selected', [25, 15]), ('active', [22, 12])])  # Larger padding for selected/active tabs
        
        # Create three tabs with lazy loading
        front_tab = tk.Frame(notebook, bg='#3a3a3a')
        back_tab = tk.Frame(notebook, bg='#3a3a3a')
        fixes_tab = tk.Frame(notebook, bg='#3a3a3a')
        
        notebook.add(front_tab, text="🎯 Front Issues")
        notebook.add(back_tab, text="🔄 Back Issues")
        notebook.add(fixes_tab, text="🔧 Fixes")
        
        # Store tab references for lazy loading
        self.issues_tabs = {
            'front': front_tab,
            'back': back_tab,
            'fixes': fixes_tab
        }
        self.tabs_populated = {
            'front': False,
            'back': False,
            'fixes': False
        }
        
        # Bind tab change event for lazy loading
        notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        
        # Show a simple loading message initially for all tabs
        for tab_key, tab in self.issues_tabs.items():
            loading_label = tk.Label(tab, 
                                   text="🔄 Loading...", 
                                   font=("Segoe UI", 14), 
                                   bg='#3a3a3a', fg='#e0e0e0')
            loading_label.pack(pady=50)
        
        # Populate the first tab in background to avoid blocking window creation
        def load_first_tab():
            self.root.after(0, lambda: self._populate_front_issues_tab(front_tab))
            self.tabs_populated['front'] = True
        
        threading.Thread(target=load_first_tab, daemon=True).start()
    
    def on_tab_changed(self, event):
        """Handle tab change events for lazy loading"""
        notebook = event.widget
        selected_tab = notebook.select()
        tab_text = notebook.tab(selected_tab, "text")
        
        # Map tab text to our internal keys (with emojis)
        tab_mapping = {
            "🎯 Front Issues": "front", 
            "🔄 Back Issues": "back", 
            "🔧 Fixes": "fixes"
        }
        
        tab_key = tab_mapping.get(tab_text)
        if tab_key and not self.tabs_populated.get(tab_key, False):
            # Clear any existing content first
            for widget in self.issues_tabs[tab_key].winfo_children():
                widget.destroy()
            
            # Show loading indicator
            loading_label = tk.Label(self.issues_tabs[tab_key], 
                                   text="🔄 Loading...", 
                                   font=("Segoe UI", 14), 
                                   bg='#3a3a3a', fg='#e0e0e0')
            loading_label.pack(pady=50)
            self.root.update()
            
            # Populate the tab in a separate thread to avoid blocking UI
            def populate_tab():
                # Populate the tab
                if tab_key == "back":
                    self.root.after(0, lambda: self._populate_back_issues_tab(self.issues_tabs[tab_key]))
                elif tab_key == "fixes":
                    self.root.after(0, lambda: self._populate_fixes_tab(self.issues_tabs[tab_key]))
                
                # Mark as populated
                self.tabs_populated[tab_key] = True
            
            # Run population in background thread
            threading.Thread(target=populate_tab, daemon=True).start()
    
    def preload_issues_tabs(self):
        """Preload all issues tab content in background to avoid lag on first access"""
        if not hasattr(self, 'issues_tabs') or not hasattr(self, 'tabs_populated'):
            return  # Issues dialog not open yet
        
        def preload_in_background():
            # Small delay to let the UI settle
            time.sleep(0.5)
            
            # Preload back issues tab
            if not self.tabs_populated.get('back', False):
                self.root.after(0, lambda: self._populate_back_issues_tab(self.issues_tabs['back']))
                self.tabs_populated['back'] = True
            
            # Longer delay before preloading fixes tab (it's usually the heaviest)
            time.sleep(0.3)
            
            # Preload fixes tab
            if not self.tabs_populated.get('fixes', False):
                self.root.after(0, lambda: self._populate_fixes_tab(self.issues_tabs['fixes']))
                self.tabs_populated['fixes'] = True
        
        # Run preloading in background thread
        threading.Thread(target=preload_in_background, daemon=True).start()
    
    def _expand_cleanup_files(self, cleanup_files, expand_frame):
        """Expand the cleanup files list to show all files"""
        # Clear the expand button
        for widget in expand_frame.winfo_children():
            widget.destroy()
        
        # Show all remaining files (skip first 4 since they're already shown)
        remaining_files = cleanup_files[4:]
        files_per_line = 2
        
        for i in range(0, len(remaining_files), files_per_line):
            line_files = remaining_files[i:i + files_per_line]
            cleanup_text = " • ".join(line_files)
            cleanup_label = tk.Label(expand_frame, text=cleanup_text, 
                                   font=("Consolas", 8), 
                                   bg='#2a2a2a', fg='#e74c3c')
            cleanup_label.pack(anchor=tk.W, pady=0)
            
            # Bind mousewheel events to the labels for scrolling
            if hasattr(self, '_fixes_canvas') and self._fixes_canvas:
                cleanup_label.bind("<MouseWheel>", lambda e: self._fixes_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
                cleanup_label.bind("<Button-4>", lambda e: self._fixes_canvas.yview_scroll(int(-1*(120/120)), "units"))
                cleanup_label.bind("<Button-5>", lambda e: self._fixes_canvas.yview_scroll(int(-1*(-120/120)), "units"))
        
        # Add collapse button
        collapse_button = tk.Button(expand_frame, 
                                  text="Show less...", 
                                  command=lambda: self._collapse_cleanup_files(cleanup_files, expand_frame),
                                  font=("Consolas", 7), 
                                  bg='#e74c3c', fg='white',
                                  relief='flat', bd=0,
                                  padx=5, pady=2)
        collapse_button.pack(anchor=tk.W, pady=2)
        
        # Bind mousewheel events to the collapse button for scrolling
        if hasattr(self, '_fixes_canvas') and self._fixes_canvas:
            collapse_button.bind("<MouseWheel>", lambda e: self._fixes_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
            collapse_button.bind("<Button-4>", lambda e: self._fixes_canvas.yview_scroll(int(-1*(120/120)), "units"))
            collapse_button.bind("<Button-5>", lambda e: self._fixes_canvas.yview_scroll(int(-1*(-120/120)), "units"))
    
    def _collapse_cleanup_files(self, cleanup_files, expand_frame):
        """Collapse the cleanup files list back to showing only 4 files"""
        # Clear all widgets in the expand frame
        for widget in expand_frame.winfo_children():
            widget.destroy()
        
        # Re-add the expand button
        expand_button = tk.Button(expand_frame, 
                                text="Show all files", 
                                command=lambda f=cleanup_files, ef=expand_frame: self._expand_cleanup_files(f, ef),
                                font=("Consolas", 7), 
                                bg='#e74c3c', fg='white',
                                relief='flat', bd=0,
                                padx=5, pady=2)
        expand_button.pack(side=tk.LEFT)
        
        # Bind mousewheel events to the expand button for scrolling
        if hasattr(self, '_fixes_canvas') and self._fixes_canvas:
            expand_button.bind("<MouseWheel>", lambda e: self._fixes_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
            expand_button.bind("<Button-4>", lambda e: self._fixes_canvas.yview_scroll(int(-1*(120/120)), "units"))
            expand_button.bind("<Button-5>", lambda e: self._fixes_canvas.yview_scroll(int(-1*(-120/120)), "units"))

    def _get_action_display_info(self, action):
        """Get display name and color for an action type"""
        action_mapping = {
            'rename': ('RENAME', '#f39c12'),
            'remove': ('REMOVE', '#e74c3c'),
            'cleanup': ('CLEANUP', '#e74c3c'),
            'create_gender_variant': ('CREATE GENDER VARIANT', '#3498db'),
            'create_gender_variant_from_other': ('CREATE GENDER VARIANT', '#3498db'),
            'create_base_from_male': ('CREATE BASE', '#9b59b6'),
            'create_base_from_female': ('CREATE BASE', '#9b59b6'),
            'clone': ('CLONE', '#2ecc71'),
            'replacement': ('REPLACEMENT', '#1abc9c'),
            'retain_extra': ('RETAIN EXTRA', '#34495e'),
            'remove_base': ('REMOVE BASE', '#e67e22')
        }
        
        display_name, color = action_mapping.get(action, (action.replace('_', ' ').upper(), '#95a5a6'))
        return display_name, color
    
    def _get_issue_description(self, filename, is_fixable):
        """Get a detailed description of what the issue is for a given filename"""
        # Parse filename components
        parts = filename.split('-')
        if len(parts) < 3:
            return "Malformed filename", "⚠️"
        
        dex_num = parts[0]
        sprite_type = parts[1]
        variant = parts[2].replace('.gif', '')
        gender = parts[3].replace('.gif', '') if len(parts) > 3 else ""
        
        # Check if this file is completely missing (not fixable)
        if not is_fixable:
            if gender:
                # Missing gender variant - no source file available
                return f"File completely missing - no source file available to create this variant", "❌"
            else:
                # Missing base file - no source file available
                return f"File completely missing - no source file available to create this file", "❌"
        
        # For fixable files, check if this is a simple rename operation
        # Look for the source file in the recommendations
        if hasattr(self, 'current_recommendations'):
            for rec in self.current_recommendations:
                if rec.get('to') == filename and rec.get('action') == 'rename':
                    return f"File needs to be renamed from {rec.get('from', 'unknown')}", "📝"
        
        # For other fixable files, determine the specific conversion needed
        if sprite_type == "front":
            if gender:
                # This is a gender variant that needs to be converted to base
                if variant == "n":
                    return f"Gender variant needs base file (Bullseye requires base file, not gender variants)", "🔄"
                else:
                    return f"Gender variant needs base file (Bullseye requires base file, not gender variants)", "🔄"
            else:
                # This is a base file that might need gender variants
                if variant == "n":
                    return f"Base file needs gender variants (Bullseye requires male/female variants)", "👥"
                else:
                    return f"Base file needs gender variants (Bullseye requires male/female variants)", "👥"
        else:  # back
            if gender:
                # This is a gender variant that needs to be converted to base
                if variant == "n":
                    return f"Gender variant needs base file (Bullseye requires base file, not gender variants)", "🔄"
                else:
                    return f"Gender variant needs base file (Bullseye requires base file, not gender variants)", "🔄"
            else:
                # This is a base file that might need gender variants
                if variant == "n":
                    return f"Base file needs gender variants (Bullseye requires male/female variants)", "👥"
                else:
                    return f"Base file needs gender variants (Bullseye requires male/female variants)", "👥"

    def _populate_front_issues_tab(self, parent):
        """Populate the Front Issues tab with ALL unfulfilled front files in grid format"""
        # Clear any existing content first
        for widget in parent.winfo_children():
            widget.destroy()
        
        # Get all unfulfilled files from the analysis
        if not hasattr(self, 'unfulfilled_files') or not self.unfulfilled_files:
            no_issues_label = tk.Label(parent, text="✅ No front file issues found!", 
                                     font=("Segoe UI", 14), 
                                     bg='#3a3a3a', fg='#27ae60')
            no_issues_label.pack(pady=50)
            return
        
        # Create scrollable list structure ONLY when there are issues
        canvas = tk.Canvas(parent, bg='#3a3a3a', highlightthickness=0)
        scrollbar = tk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#3a3a3a')
        
        def update_scroll_region(event=None):
            # Get the bounding box of all items
            bbox = canvas.bbox("all")
            if bbox:
                # Ensure we have a minimum height to prevent scrolling above content
                min_height = max(bbox[3] - bbox[1], canvas.winfo_height())
                canvas.configure(scrollregion=(0, 0, bbox[2], min_height))
            else:
                # If no content, set scroll region to canvas size
                canvas.configure(scrollregion=(0, 0, canvas.winfo_width(), canvas.winfo_height()))
        
        scrollable_frame.bind("<Configure>", update_scroll_region)
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Bind mousewheel to canvas for better scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        canvas.bind("<MouseWheel>", _on_mousewheel)
        canvas.bind("<Button-4>", lambda e: _on_mousewheel(type('Event', (), {'delta': 120})()))
        canvas.bind("<Button-5>", lambda e: _on_mousewheel(type('Event', (), {'delta': -120})()))
        
        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True, padx=(20, 0), pady=20)
        scrollbar.pack(side="right", fill="y", padx=(0, 20), pady=20)
        
        # Store current canvas for issue items to bind mousewheel events
        self._front_issues_canvas = canvas
        
        # Collect all front files from unfulfilled_files
        front_files = []
        for filename, is_fixable in self.unfulfilled_files.items():
            if '-front-' in filename:
                front_files.append((filename, is_fixable))
                if '403-front-s.gif' in filename:
                    pass  # Added to front_files list
        
        # Sort by dex number (lowest first)
        def extract_dex_num(filename):
            parts = filename.split('-')
            try:
                return int(parts[0])
            except (ValueError, IndexError):
                return 9999
        
        front_files.sort(key=lambda x: extract_dex_num(x[0]))
        
        # Debug message removed - not needed for normal operation
        
        if not front_files:
            no_issues_label = tk.Label(scrollable_frame, text="✅ No front file issues found!", 
                                     font=("Segoe UI", 14), 
                                     bg='#3a3a3a', fg='#27ae60')
            no_issues_label.pack(pady=50)
        else:
            # Create grid layout (2 columns)
            grid_frame = tk.Frame(scrollable_frame, bg='#3a3a3a')
            grid_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
            
            # Configure grid weights for equal column width BEFORE placing items
            grid_frame.grid_columnconfigure(0, weight=1)
            grid_frame.grid_columnconfigure(1, weight=1)
            
            # Bind mousewheel to grid frame
            grid_frame.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
            grid_frame.bind("<Button-4>", lambda e: canvas.yview_scroll(int(-1*(120/120)), "units"))
            grid_frame.bind("<Button-5>", lambda e: canvas.yview_scroll(int(-1*(-120/120)), "units"))
            
            # Add unfulfilled files in grid format - show all items
            for i, (filename, is_fixable) in enumerate(front_files):
                self._create_simple_issue_item(grid_frame, filename, is_fixable, i, canvas)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def _create_simple_issue_item(self, grid_frame, filename, is_fixable, index, canvas=None):
        """Create a simple, lightweight issue item for better performance"""
        # Determine colors and icons based on fixability
        if is_fixable:
            emoji = '🔧'
            status_text = 'FIXABLE'
            status_color = '#27ae60'
            bg_color = '#2a2a2a'
            icon_color = '#2ecc71'
        else:
            emoji = '❌'
            status_text = 'NOT FIXABLE'
            status_color = '#e74c3c'
            bg_color = '#2a2a2a'
            icon_color = '#e67e22'
        
        # Parse filename for better display
        parts = filename.split('-')
        dex_num = parts[0] if len(parts) > 0 else "000"
        sprite_type = parts[1] if len(parts) > 1 else "unknown"
        variant = parts[2].replace('.gif', '') if len(parts) > 2 else "unknown"
        gender = parts[3].replace('.gif', '') if len(parts) > 3 else ""
        
        # Get specific issue description
        issue_desc, issue_emoji = self._get_issue_description(filename, is_fixable)
        
        # Create main file frame with minimal styling
        file_frame = tk.Frame(grid_frame, bg=bg_color, relief=tk.RAISED, bd=1)
        row = index // 2
        col = index % 2
        file_frame.grid(row=row, column=col, padx=8, pady=6, sticky="ew")
        
        # Top-left layout - everything in one compact area
        content_frame = tk.Frame(file_frame, bg=bg_color)
        content_frame.pack(fill=tk.X, padx=10, pady=8, anchor=tk.W)
        
        # Left side: Filename with badges
        left_frame = tk.Frame(content_frame, bg=bg_color)
        left_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Filename with bolded Pokemon number
        filename_label = tk.Label(left_frame, text=filename, 
                                font=("Consolas", 13, "bold"), 
                                bg=bg_color, fg='#f8f9fa')
        filename_label.pack(side=tk.LEFT, padx=(0, 5))
        
        # Small badges right next to filename
        tags_frame = tk.Frame(left_frame, bg=bg_color)
        tags_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        # Sprite type tag (smaller)
        type_colors = {'front': '#3498db', 'back': '#e74c3c'}
        type_text = sprite_type.upper()
        type_tag = tk.Label(tags_frame, text=type_text, 
                           font=("Segoe UI", 6, "bold"), 
                           bg=type_colors.get(sprite_type.lower(), '#95a5a6'), 
                           fg='#ffffff', padx=2, pady=1, width=6)
        type_tag.pack(side=tk.LEFT, padx=(0, 2))
        
        # Variant tag (smaller)
        variant_colors = {'n': '#27ae60', 's': '#f39c12'}
        variant_text = 'NORMAL' if variant.lower() == 'n' else 'SHINY'
        variant_tag = tk.Label(tags_frame, text=variant_text, 
                              font=("Segoe UI", 6, "bold"), 
                              bg=variant_colors.get(variant.lower(), '#95a5a6'), 
                              fg='#ffffff', padx=2, pady=1, width=6)
        variant_tag.pack(side=tk.LEFT, padx=(0, 2))
        
        # Gender tag (if present, smaller)
        if gender:
            gender_colors = {'m': '#9b59b6', 'f': '#e91e63'}
            gender_text = 'MALE' if gender.lower() == 'm' else 'FEMALE'
            gender_tag = tk.Label(tags_frame, text=gender_text, 
                                 font=("Segoe UI", 6, "bold"), 
                                 bg=gender_colors.get(gender.lower(), '#95a5a6'), 
                                 fg='#ffffff', padx=2, pady=1, width=6)
            gender_tag.pack(side=tk.LEFT, padx=(0, 2))
        
        # Right side: Status badge pushed to far right
        status_label = tk.Label(content_frame, text=f"{emoji} {status_text}", 
                              font=("Segoe UI", 10, "bold"), 
                              bg=status_color, fg='#ffffff')
        status_label.pack(side=tk.RIGHT, anchor=tk.E)
        
        # Issue description on second line
        desc_label = tk.Label(file_frame, text=f"{issue_emoji} {issue_desc}", 
                            font=("Segoe UI", 10), 
                            bg=bg_color, fg=icon_color, wraplength=350)
        desc_label.pack(fill=tk.X, padx=10, pady=(0, 8), anchor=tk.W)
        
        # Bind mousewheel to this widget and all its children for scrolling
        def bind_mousewheel_recursive(widget):
            """Recursively bind mousewheel to widget and all its children"""
            target_canvas = canvas or getattr(self, '_front_issues_canvas', None)
            if target_canvas:
                def _on_mousewheel(event):
                    target_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
                widget.bind("<MouseWheel>", _on_mousewheel)
                widget.bind("<Button-4>", lambda e: _on_mousewheel(type('Event', (), {'delta': 120})()))
                widget.bind("<Button-5>", lambda e: _on_mousewheel(type('Event', (), {'delta': -120})()))
                for child in widget.winfo_children():
                    bind_mousewheel_recursive(child)
        
        bind_mousewheel_recursive(file_frame)
    
    def _populate_back_issues_tab(self, parent):
        """Populate the Back Issues tab with ALL unfulfilled back files in grid format"""
        # Clear any existing content first
        for widget in parent.winfo_children():
            widget.destroy()
        
        # Get all unfulfilled files from the analysis
        if not hasattr(self, 'unfulfilled_files') or not self.unfulfilled_files:
            no_issues_label = tk.Label(parent, text="✅ No back file issues found!", 
                                     font=("Segoe UI", 14), 
                                     bg='#3a3a3a', fg='#27ae60')
            no_issues_label.pack(pady=50)
            return
        
        # Create scrollable list structure ONLY when there are issues
        canvas = tk.Canvas(parent, bg='#3a3a3a', highlightthickness=0)
        scrollbar = tk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#3a3a3a')
        
        def update_scroll_region(event=None):
            # Get the bounding box of all items
            bbox = canvas.bbox("all")
            if bbox:
                # Ensure we have a minimum height to prevent scrolling above content
                min_height = max(bbox[3] - bbox[1], canvas.winfo_height())
                canvas.configure(scrollregion=(0, 0, bbox[2], min_height))
            else:
                # If no content, set scroll region to canvas size
                canvas.configure(scrollregion=(0, 0, canvas.winfo_width(), canvas.winfo_height()))
        
        scrollable_frame.bind("<Configure>", update_scroll_region)
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Bind mousewheel to canvas for better scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        canvas.bind("<MouseWheel>", _on_mousewheel)
        canvas.bind("<Button-4>", lambda e: _on_mousewheel(type('Event', (), {'delta': 120})()))
        canvas.bind("<Button-5>", lambda e: _on_mousewheel(type('Event', (), {'delta': -120})()))
        
        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True, padx=(20, 0), pady=20)
        scrollbar.pack(side="right", fill="y", padx=(0, 20), pady=20)
        
        # Store current canvas for issue items to bind mousewheel events
        self._back_issues_canvas = canvas
        
        # Collect all back files from unfulfilled_files
        back_files = []
        for filename, is_fixable in self.unfulfilled_files.items():
            if '-back-' in filename:
                back_files.append((filename, is_fixable))
        
        # Sort by dex number (lowest first)
        def extract_dex_num(filename):
            parts = filename.split('-')
            try:
                return int(parts[0])
            except (ValueError, IndexError):
                return 9999
        
        back_files.sort(key=lambda x: extract_dex_num(x[0]))
        
        if not back_files:
            no_issues_label = tk.Label(scrollable_frame, text="✅ No back file issues found!", 
                                     font=("Segoe UI", 14), 
                                     bg='#3a3a3a', fg='#27ae60')
            no_issues_label.pack(pady=50)
        else:
            # Create grid layout (2 columns)
            grid_frame = tk.Frame(scrollable_frame, bg='#3a3a3a')
            grid_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
            
            # Configure grid weights for equal column width BEFORE placing items
            grid_frame.grid_columnconfigure(0, weight=1)
            grid_frame.grid_columnconfigure(1, weight=1)
            
            # Bind mousewheel to grid frame
            grid_frame.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
            grid_frame.bind("<Button-4>", lambda e: canvas.yview_scroll(int(-1*(120/120)), "units"))
            grid_frame.bind("<Button-5>", lambda e: canvas.yview_scroll(int(-1*(-120/120)), "units"))
            
            # Add unfulfilled files using lightweight items
            for i, (filename, is_fixable) in enumerate(back_files):
                self._create_simple_issue_item(grid_frame, filename, is_fixable, i, canvas)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def _populate_fixes_tab(self, parent):
        """Populate the Fixes tab with lightweight, fast-loading recommendations"""
        # Clear any existing content first
        for widget in parent.winfo_children():
            widget.destroy()
        
        # Check if we have recommendations available
        if not hasattr(self, 'current_recommendations') or not self.current_recommendations:
            no_fixes_label = tk.Label(parent, text="✅ No fixes needed!", 
                                    font=("Segoe UI", 14), 
                                    bg='#3a3a3a', fg='#27ae60')
            no_fixes_label.pack(pady=50)
            return
        
        # Create a simple scrollable list
        canvas = tk.Canvas(parent, bg='#3a3a3a', highlightthickness=0)
        scrollbar = tk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#3a3a3a')
        
        def update_scroll_region(event=None):
            # Get the bounding box of all items
            bbox = canvas.bbox("all")
            if bbox:
                # Ensure we have a minimum height to prevent scrolling above content
                min_height = max(bbox[3] - bbox[1], canvas.winfo_height())
                canvas.configure(scrollregion=(0, 0, bbox[2], min_height))
            else:
                # If no content, set scroll region to canvas size
                canvas.configure(scrollregion=(0, 0, canvas.winfo_width(), canvas.winfo_height()))
        
        scrollable_frame.bind("<Configure>", update_scroll_region)
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Bind mousewheel to canvas for better scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def bind_mousewheel_to_widget(widget):
            """Bind mousewheel to widget and all its children"""
            widget.bind("<MouseWheel>", _on_mousewheel)
            widget.bind("<Button-4>", lambda e: _on_mousewheel(type('Event', (), {'delta': 120})()))
            widget.bind("<Button-5>", lambda e: _on_mousewheel(type('Event', (), {'delta': -120})()))
            for child in widget.winfo_children():
                bind_mousewheel_to_widget(child)
        
        # Bind mousewheel to canvas and all its children
        bind_mousewheel_to_widget(canvas)
        bind_mousewheel_to_widget(scrollable_frame)
        
        # Also bind to the entire scrollable frame to catch events in empty spaces
        scrollable_frame.bind("<MouseWheel>", _on_mousewheel)
        scrollable_frame.bind("<Button-4>", lambda e: _on_mousewheel(type('Event', (), {'delta': 120})()))
        scrollable_frame.bind("<Button-5>", lambda e: _on_mousewheel(type('Event', (), {'delta': -120})()))
        
        # Bind mousewheel to the scrollable frame's children recursively
        def bind_mousewheel_to_children(parent):
            """Recursively bind mousewheel to all children of a parent widget"""
            for child in parent.winfo_children():
                child.bind("<MouseWheel>", _on_mousewheel)
                child.bind("<Button-4>", lambda e: _on_mousewheel(type('Event', (), {'delta': 120})()))
                child.bind("<Button-5>", lambda e: _on_mousewheel(type('Event', (), {'delta': -120})()))
                bind_mousewheel_to_children(child)
        
        bind_mousewheel_to_children(scrollable_frame)
        
        # Also bind to the parent frame to catch events in empty spaces
        parent.bind("<MouseWheel>", _on_mousewheel)
        parent.bind("<Button-4>", lambda e: _on_mousewheel(type('Event', (), {'delta': 120})()))
        parent.bind("<Button-5>", lambda e: _on_mousewheel(type('Event', (), {'delta': -120})()))
        
        # Make scrollable frame focusable and bind mousewheel events
        scrollable_frame.bind("<Enter>", lambda e: scrollable_frame.focus_set())
        scrollable_frame.focus_set()
        
        # Ensure scrollable frame can handle mousewheel events
        scrollable_frame.configure(takefocus=True)
        
        # Ensure canvas can handle mousewheel events
        canvas.configure(takefocus=True)
        canvas.focus_set()
        
        # Store current canvas for recommendation cards to bind mousewheel events
        self._fixes_canvas = canvas
        
        # Group recommendations by operation type (normalized for grouping)
        def normalize_operation_type_for_grouping(action):
            """Normalize action types for grouping - group similar actions together"""
            if action in ['create_gender_variant', 'create_gender_variant_from_other']:
                return 'create_gender_variant'
            elif action in ['create_base_from_male', 'create_base_from_female']:
                return 'create_base'
            elif action == 'remove':
                return 'remove'  # Keep remove operations separate
            elif action == 'cleanup':
                return 'cleanup'  # Keep cleanup operations separate
            else:
                return action
        
        operation_groups = {}
        for rec in self.current_recommendations:
            operation_type = normalize_operation_type_for_grouping(rec['action'])
            if operation_type not in operation_groups:
                operation_groups[operation_type] = []
            operation_groups[operation_type].append(rec)
        
        # Simple header
        header_frame = tk.Frame(parent, bg='#3a3a3a')
        header_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Search bar
        search_frame = tk.Frame(header_frame, bg='#3a3a3a')
        search_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        search_label = tk.Label(search_frame, text="🔍 Search:", 
                                font=("Segoe UI", 9),
                               bg='#3a3a3a', fg='#e0e0e0')
        search_label.pack(side=tk.LEFT, padx=(0, 5))
        
        search_entry = tk.Entry(search_frame, font=("Segoe UI", 9), 
                               bg='#2a2a2a', fg='#e0e0e0', 
                               insertbackground='#e0e0e0')
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        search_entry.insert(0, "Search fixes...")
        search_entry.config(fg='#95a5a6')  # Gray placeholder color
        
        # Store search entry for filtering
        self.fixes_search_entry = search_entry
        
        # Bind search functionality
        search_entry.bind('<KeyRelease>', self.filter_fixes)
        search_entry.bind('<Button-1>', self.clear_search_placeholder)
        search_entry.bind('<FocusIn>', self.clear_search_placeholder)
        search_entry.bind('<FocusOut>', self.restore_search_placeholder)
        
        # Copy all issues button
        copy_btn = tk.Button(header_frame, text="📋 Copy All Fixes", 
                           command=lambda: self.copy_all_issues_to_clipboard(self.current_recommendations),
                           bg='#27ae60', fg='white', font=("Segoe UI", 9))
        copy_btn.pack(side=tk.RIGHT)
        
        # Add recommendations grouped by operation type
        self.recommendation_vars = []
        self.all_rec_frames = []
        self.all_section_frames = []
        self.all_grid_containers = []
        
        # Sort operation types by count (least issues first)
        sorted_operations = sorted(operation_groups.keys(), key=lambda x: len(operation_groups[x]))
        for operation_type in sorted_operations:
            recommendations = operation_groups[operation_type]
            
            # Determine section colors based on operation type (dark theme)
            section_colors = {
                'replacement': {'color': '#27ae60', 'icon': '🔄'},
                'rename': {'color': '#3498db', 'icon': '📝'},
                'remove': {'color': '#e74c3c', 'icon': '🗑️'},
                'cleanup': {'color': '#e74c3c', 'icon': '🧹'},
                'remove_base': {'color': '#e74c3c', 'icon': '🗑️'},
                'create_gender_variant': {'color': '#3498db', 'icon': '👥'},
                'create_base': {'color': '#9b59b6', 'icon': '📄'},
                'clone': {'color': '#9b59b6', 'icon': '📋'},
                'comprehensive_replacement': {'color': '#f39c12', 'icon': '🔧'},
                'retain_extra': {'color': '#34495e', 'icon': '💾'}
            }
            
            section_info = section_colors.get(operation_type, {'color': '#95a5a6', 'icon': '⚙️'})
            section_color = section_info['color']
            section_icon = section_info['icon']
            
            # Create collapsible section header with dark theme
            section_frame = tk.Frame(scrollable_frame, bg='#2a2a2a', relief=tk.RAISED, bd=1)
            section_frame._operation_section_header = operation_type
            self.all_section_frames.append(section_frame)
            section_frame.pack(fill=tk.X, padx=10, pady=(10, 3))
            
            # Bind mousewheel to section frame and all its children
            def bind_mousewheel_to_section(widget):
                """Bind mousewheel to section widget and all its children"""
                if hasattr(self, '_fixes_canvas') and self._fixes_canvas:
                    def _on_mousewheel(event):
                        self._fixes_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
                        return "break"  # Prevent event from propagating further
                    widget.bind("<MouseWheel>", _on_mousewheel)
                    widget.bind("<Button-4>", lambda e: _on_mousewheel(type('Event', (), {'delta': 120})()))
                    widget.bind("<Button-5>", lambda e: _on_mousewheel(type('Event', (), {'delta': -120})()))
                    for child in widget.winfo_children():
                        bind_mousewheel_to_section(child)
            
            bind_mousewheel_to_section(section_frame)
            
            # Section header with expand/collapse button
            header_frame = tk.Frame(section_frame, bg='#2a2a2a')
            header_frame.pack(fill=tk.X, padx=10, pady=8)
            
            # Bind mousewheel to header frame as well
            def bind_mousewheel_to_header(widget):
                """Bind mousewheel to header widget and all its children"""
                if hasattr(self, '_fixes_canvas') and self._fixes_canvas:
                    def _on_mousewheel(event):
                        self._fixes_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
                        return "break"  # Prevent event from propagating further
                    widget.bind("<MouseWheel>", _on_mousewheel)
                    widget.bind("<Button-4>", lambda e: _on_mousewheel(type('Event', (), {'delta': 120})()))
                    widget.bind("<Button-5>", lambda e: _on_mousewheel(type('Event', (), {'delta': -120})()))
                    for child in widget.winfo_children():
                        bind_mousewheel_to_header(child)
            
            bind_mousewheel_to_header(header_frame)
            
            
            # Operation type and count with dark theme
            operation_display_name = operation_type.replace('_', ' ').upper()
            count_text = f"{section_icon} {operation_display_name} ({len(recommendations)} operations)"
            count_label = tk.Label(header_frame, 
                                 text=count_text,
                                 font=("Segoe UI", 12, "bold"), 
                                 bg='#2a2a2a', fg='#ffffff')
            count_label.pack(side=tk.LEFT)
            
            # Bind mousewheel to count label as well
            if hasattr(self, '_fixes_canvas') and self._fixes_canvas:
                def _on_mousewheel(event):
                    self._fixes_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
                    return "break"  # Prevent event from propagating further
                count_label.bind("<MouseWheel>", _on_mousewheel)
                count_label.bind("<Button-4>", lambda e: _on_mousewheel(type('Event', (), {'delta': 120})()))
                count_label.bind("<Button-5>", lambda e: _on_mousewheel(type('Event', (), {'delta': -120})()))
            
            # Select all for this operation type
            def select_operation_all(op_type):
                for rec_var, rec in zip(self.recommendation_vars, self.current_recommendations):
                    normalized_type = normalize_operation_type_for_grouping(rec['action'])
                    if normalized_type == op_type:
                        rec_var.set(True)
            
            select_operation_btn = tk.Button(header_frame, text="✓ Select All", 
                                     command=lambda op=operation_type: select_operation_all(op),
                                     bg=section_color, fg='white', font=("Segoe UI", 10, "bold"),
                                     width=12, height=1, relief=tk.RAISED, bd=2)
            select_operation_btn.pack(side=tk.RIGHT)
            
            # Bind mousewheel to Select All button as well
            if hasattr(self, '_fixes_canvas') and self._fixes_canvas:
                def _on_mousewheel(event):
                    self._fixes_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
                    return "break"  # Prevent event from propagating further
                select_operation_btn.bind("<MouseWheel>", _on_mousewheel)
                select_operation_btn.bind("<Button-4>", lambda e: _on_mousewheel(type('Event', (), {'delta': 120})()))
                select_operation_btn.bind("<Button-5>", lambda e: _on_mousewheel(type('Event', (), {'delta': -120})()))
            
            # Create a grid container for compact cards
            grid_container = tk.Frame(scrollable_frame, bg='#3a3a3a')
            grid_container.pack(fill=tk.X, padx=10, pady=5)
            grid_container._operation_type = operation_type
            grid_container._section_frame = section_frame
            self.all_grid_containers.append(grid_container)
            
            # Bind mousewheel to grid container
            grid_container.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
            grid_container.bind("<Button-4>", lambda e: canvas.yview_scroll(int(-1*(120/120)), "units"))
            grid_container.bind("<Button-5>", lambda e: canvas.yview_scroll(int(-1*(-120/120)), "units"))
            
            # Sort recommendations by dex number (lowest first)
            def extract_dex_from_rec(rec):
                from_field = rec.get('from')
                if not from_field:
                    return 9999  # Put items with no 'from' at the end
                if isinstance(from_field, list):
                    # For comprehensive operations, use the first file in the list
                    filename = from_field[0] if from_field else ''
                else:
                    filename = from_field
                match = re.match(r'^(\d{3,4})', filename)
                return int(match.group(1)) if match else 9999
            
            recommendations.sort(key=extract_dex_from_rec)
            
            # Add individual recommendations in compact grid format
            for i, rec in enumerate(recommendations):
                # Extract dex number for display
                from_field = rec.get('from')
                if not from_field:
                    dex_num = "000"  # Default for items with no 'from'
                elif isinstance(from_field, list):
                    # For comprehensive operations, use the first file in the list
                    filename = from_field[0] if from_field else ''
                    match = re.match(r'^(\d{3,4})', filename)
                    dex_num = match.group(1) if match else "000"
                else:
                    match = re.match(r'^(\d{3,4})', from_field)
                    dex_num = match.group(1) if match else "000"
                
                # Get action display info using the new mapping function
                action_display_name, action_color = self._get_action_display_info(rec['action'])
                
                # Get action icon
                action_icons = {
                    'replacement': '🔄',
                    'rename': '📝',
                    'remove': '🗑️',
                    'cleanup': '🧹',
                    'remove_base': '🗑️',
                    'create_gender_variant': '👥',
                    'create_gender_variant_from_other': '👥',
                    'create_gender_variant_with_cleanup': '👥🧹',
                    'create_base_from_male': '📄',
                    'create_base_from_female': '📄',
                    'create_base_with_cleanup': '📄🧹',
                    'clone': '📋',
                    'comprehensive_replacement': '🔧',
                    'retain_extra': '💾'
                }
                action_icon = action_icons.get(rec['action'], '⚙️')
                
                # Create compact card frame
                card_frame = tk.Frame(grid_container, bg='#2a2a2a', relief=tk.RAISED, bd=1)
                card_frame._operation_type = operation_type
                card_frame._rec_data = rec
                card_frame._section_header = section_frame
                self.all_rec_frames.append(card_frame)
                
                # Grid positioning (2 columns)
                # Calculate grid position to ensure top-to-bottom, left-to-right visual order
                row = i // 2
                col = i % 2
                card_frame.grid(row=row, column=col, padx=5, pady=3, sticky='ew')
                
                # Configure grid weights for equal columns
                grid_container.grid_columnconfigure(0, weight=1)
                grid_container.grid_columnconfigure(1, weight=1)
                
                # Checkbox
                var = tk.BooleanVar(value=True)
                self.recommendation_vars.append(var)
                checkbox = tk.Checkbutton(card_frame, variable=var, bg='#2a2a2a', 
                                        activebackground='#2a2a2a', selectcolor='#555555')
                checkbox.pack(side=tk.LEFT, padx=5, pady=5)
                
                # Main content frame
                content_frame = tk.Frame(card_frame, bg='#2a2a2a')
                content_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
                
                # Header: Pokemon number + action type
                header_frame = tk.Frame(content_frame, bg='#2a2a2a')
                header_frame.pack(fill=tk.X)
                
                dex_label = tk.Label(header_frame, text=f"#{dex_num}", 
                                   font=("Segoe UI", 10, "bold"), 
                                   bg='#2a2a2a', fg='#ffffff')
                dex_label.pack(side=tk.LEFT, padx=(0, 8))
                
                action_type_text = f"{action_icon} {action_display_name}"
                action_type_label = tk.Label(header_frame, text=action_type_text, 
                                           font=("Segoe UI", 9, "bold"), 
                                           bg='#2a2a2a', fg=action_color)
                action_type_label.pack(side=tk.LEFT)
                
                # Add "FROM X OPERATIONS" text for cleanup operations
                if rec.get('action') == 'cleanup' and rec.get('source_operation_count'):
                    from_ops_text = f"FROM {rec['source_operation_count']} OPERATIONS"
                    from_ops_label = tk.Label(header_frame, text=from_ops_text, 
                                            font=("Segoe UI", 9, "bold"), 
                                            bg='#2a2a2a', fg='#ffffff')
                    from_ops_label.pack(side=tk.LEFT, padx=(8, 0))
                
                # Source file (compact) - skip for cleanup operations
                if rec.get('action') != 'cleanup':
                    if isinstance(rec['from'], list):
                        source_text = f"FROM: {' + '.join(rec['from'])}"
                    else:
                        source_text = f"FROM: {rec['from']}"
                    
                    source_label = tk.Label(content_frame, text=source_text, 
                                          font=("Consolas", 8), 
                                          bg='#2a2a2a', fg='#e74c3c')
                    source_label.pack(anchor=tk.W, pady=1)
                
                # Target files (compact)
                if 'to' in rec and rec['to']:
                    if isinstance(rec['to'], list):
                        targets = ', '.join(rec['to'][:2])  # Show first 2, truncate if more
                        if len(rec['to']) > 2:
                            targets += f" (+{len(rec['to'])-2} more)"
                        target_text = f"TO: {targets}"
                    else:
                        target_text = f"TO: {rec['to']}"
                    
                    target_label = tk.Label(content_frame, text=target_text, 
                                          font=("Consolas", 8), 
                                          bg='#2a2a2a', fg='#27ae60')
                    target_label.pack(anchor=tk.W, pady=1)
                
                # Cleanup files (for cleanup operations) - show first 4 files with expand button
                if rec.get('action') == 'cleanup' and rec.get('cleanup_files'):
                    cleanup_files = rec['cleanup_files']
                    if isinstance(cleanup_files, list):
                        # Show first 4 files initially
                        files_to_show = cleanup_files[:4]
                        files_per_line = 2
                        
                        # Display the first 4 files
                        for i in range(0, len(files_to_show), files_per_line):
                            line_files = files_to_show[i:i + files_per_line]
                            cleanup_text = " • ".join(line_files)
                            cleanup_label = tk.Label(content_frame, text=cleanup_text, 
                                                   font=("Consolas", 8), 
                                                   bg='#2a2a2a', fg='#e74c3c')
                            cleanup_label.pack(anchor=tk.W, pady=0)
                        
                        # Add expand button if there are more than 4 files
                        if len(cleanup_files) > 4:
                            expand_frame = tk.Frame(content_frame, bg='#2a2a2a')
                            expand_frame.pack(anchor=tk.W, pady=2)
                            
                            expand_button = tk.Button(expand_frame, 
                                                    text="Show all files", 
                                                    command=lambda f=cleanup_files, ef=expand_frame: self._expand_cleanup_files(f, ef),
                                                    font=("Consolas", 7), 
                                                    bg='#e74c3c', fg='white',
                                                    relief='flat', bd=0,
                                                    padx=5, pady=2)
                            expand_button.pack(side=tk.LEFT)
                            
                            # Bind mousewheel events to the expand button for scrolling
                            if hasattr(self, '_fixes_canvas') and self._fixes_canvas:
                                expand_button.bind("<MouseWheel>", lambda e: self._fixes_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
                                expand_button.bind("<Button-4>", lambda e: self._fixes_canvas.yview_scroll(int(-1*(120/120)), "units"))
                                expand_button.bind("<Button-5>", lambda e: self._fixes_canvas.yview_scroll(int(-1*(-120/120)), "units"))
                
                # Files to remove (compact) - skip for cleanup operations since they have their own display
                if rec.get('files_to_remove') and rec.get('action') != 'cleanup':
                    if isinstance(rec['files_to_remove'], list):
                        removes = ', '.join(rec['files_to_remove'][:2])  # Show first 2
                        if len(rec['files_to_remove']) > 2:
                            removes += f" (+{len(rec['files_to_remove'])-2} more)"
                        remove_text = f"REMOVE: {removes}"
                    else:
                        remove_text = f"REMOVE: {rec['files_to_remove']}"
                    
                    remove_label = tk.Label(content_frame, text=remove_text, 
                                          font=("Consolas", 8), 
                                          bg='#2a2a2a', fg='#e67e22')
                    remove_label.pack(anchor=tk.W, pady=1)
                
                # Copy button
                copy_btn = tk.Button(card_frame, text="📋", 
                                   command=lambda r=rec: self.copy_issue_to_clipboard(r),
                                   bg=action_color, fg='white', font=("Segoe UI", 8),
                                   width=2, height=1)
                copy_btn.pack(side=tk.RIGHT, padx=5, pady=5)
                
                # Bind mousewheel to this card and all its children for scrolling
                def bind_mousewheel_recursive(widget):
                    """Recursively bind mousewheel to widget and all its children"""
                    if hasattr(self, '_fixes_canvas') and self._fixes_canvas:
                        def _on_mousewheel(event):
                            self._fixes_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
                        widget.bind("<MouseWheel>", _on_mousewheel)
                        widget.bind("<Button-4>", lambda e: _on_mousewheel(type('Event', (), {'delta': 120})()))
                        widget.bind("<Button-5>", lambda e: _on_mousewheel(type('Event', (), {'delta': -120})()))
                        for child in widget.winfo_children():
                            bind_mousewheel_recursive(child)
                
                bind_mousewheel_recursive(card_frame)
        
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Buttons
        button_frame = tk.Frame(parent, bg='#3a3a3a')
        button_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        select_all_btn = tk.Button(button_frame, text="Select All", 
                                  command=lambda: [var.set(True) for var in self.recommendation_vars],
                                  bg='#3498db', fg='white', font=("Segoe UI", 9))
        select_all_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        select_none_btn = tk.Button(button_frame, text="Select None", 
                                   command=lambda: [var.set(False) for var in self.recommendation_vars],
                                   bg='#95a5a6', fg='white', font=("Segoe UI", 9))
        select_none_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        apply_btn = tk.Button(button_frame, text="Apply Selected", 
                             command=lambda: self.apply_recommendations(parent.winfo_toplevel()),
                             bg='#27ae60', fg='white', font=("Segoe UI", 9, "bold"))
        apply_btn.pack(side=tk.RIGHT, padx=(5, 0))
        
        cancel_btn = tk.Button(button_frame, text="Cancel", 
                              command=parent.winfo_toplevel().destroy,
                              bg='#e74c3c', fg='white', font=("Segoe UI", 9))
        cancel_btn.pack(side=tk.RIGHT, padx=(5, 0))
    
    def filter_fixes(self, event=None):
        """Filter fixes based on search text"""
        if not hasattr(self, 'fixes_search_entry'):
            return
        
        search_text = self.fixes_search_entry.get().lower()
        
        # Don't filter if it's just the placeholder text
        if search_text == "search fixes...":
            self._restore_all_fixes()
            return
        
        # Hide all cards first
        for frame in self.all_rec_frames:
            frame.grid_remove()
        
        # Track which categories have visible items
        visible_categories = set()
        
        # Filter all recommendation frames and track visible categories
        visible_frames_by_category = {}
        
        for frame in self.all_rec_frames:
            if hasattr(frame, '_rec_data') and hasattr(frame, '_operation_type'):
                rec = frame._rec_data
                operation_type = frame._operation_type
                
                # Search in filename, action type, target files, and cleanup files
                searchable_text = f"{rec['from']} {rec['action']}"
                if 'to' in rec:
                    if isinstance(rec['to'], list):
                        searchable_text += " " + " ".join(rec['to'])
                    else:
                        searchable_text += " " + str(rec['to'])
                if rec.get('action') == 'cleanup' and rec.get('cleanup_files'):
                    searchable_text += " " + " ".join(rec['cleanup_files'])
                
                if search_text in searchable_text.lower():
                    if operation_type not in visible_frames_by_category:
                        visible_frames_by_category[operation_type] = []
                    visible_frames_by_category[operation_type].append(frame)
                    visible_categories.add(operation_type)
        
        # Sort frames within each category by dex number and show them
        for operation_type, frames in visible_frames_by_category.items():
            # Sort frames by dex number (lowest first)
            def get_dex_number(frame):
                if hasattr(frame, '_rec_data'):
                    filename = frame._rec_data.get('from')
                    if not filename:
                        return 9999
                    # Handle both single files and lists of files
                    if isinstance(filename, list):
                        filename = filename[0]  # Use first file for sorting
                    match = re.match(r'^(\d{3,4})', filename)
                    return int(match.group(1)) if match else 9999
                return 9999
            
            frames.sort(key=get_dex_number)
            
            # Show frames in proper order
            for frame in frames:
                frame.grid()
        
        # Group sections and grid containers by operation type
        section_groups = {}
        grid_groups = {}
        
        for section_frame in self.all_section_frames:
            if hasattr(section_frame, '_operation_section_header'):
                op_type = section_frame._operation_section_header
                section_groups[op_type] = section_frame
        
        for grid_container in self.all_grid_containers:
            if hasattr(grid_container, '_operation_type'):
                op_type = grid_container._operation_type
                grid_groups[op_type] = grid_container
        
        # Sort visible categories by count (least issues first) - same logic as original creation
        def get_operation_count(op_type):
            # Count how many recommendations this operation type has
            count = 0
            for frame in self.all_rec_frames:
                if hasattr(frame, '_operation_type') and frame._operation_type == op_type:
                    count += 1
            return count
        
        # Only sort the visible categories, but maintain the count-based ordering
        visible_sorted_categories = sorted(visible_categories, key=get_operation_count)
        
        # Hide all sections and grid containers first
        for section_frame in self.all_section_frames:
            section_frame.pack_forget()
        for grid_container in self.all_grid_containers:
            grid_container.pack_forget()
        
        # Show visible categories in proper order (least to most operations)
        for operation_type in visible_sorted_categories:
            if operation_type in section_groups:
                section_groups[operation_type].pack(fill=tk.X, padx=10, pady=(10, 3))
            if operation_type in grid_groups:
                grid_groups[operation_type].pack(fill=tk.X, padx=10, pady=5)
    
    def _restore_all_fixes(self):
        """Restore all fixes to their original state"""
        # Group sections by operation type to maintain sorted order
        section_groups = {}
        grid_groups = {}
        
        for section_frame in self.all_section_frames:
            if hasattr(section_frame, '_operation_section_header'):
                op_type = section_frame._operation_section_header
                section_groups[op_type] = section_frame
        
        for grid_container in self.all_grid_containers:
            if hasattr(grid_container, '_operation_type'):
                op_type = grid_container._operation_type
                grid_groups[op_type] = grid_container
        
        # Sort operation types by count (least issues first) - same logic as original creation
        def get_operation_count(op_type):
            # Count how many recommendations this operation type has
            count = 0
            for frame in self.all_rec_frames:
                if hasattr(frame, '_operation_type') and frame._operation_type == op_type:
                    count += 1
            return count
        
        sorted_operations = sorted(section_groups.keys(), key=get_operation_count)
        
        # Show sections and grid containers in proper order
        for operation_type in sorted_operations:
            if operation_type in section_groups:
                section_groups[operation_type].pack(fill=tk.X, padx=10, pady=(10, 3))
            if operation_type in grid_groups:
                grid_groups[operation_type].pack(fill=tk.X, padx=10, pady=5)
        
        # Group and sort recommendation frames by category and dex number
        frames_by_category = {}
        
        for frame in self.all_rec_frames:
            if hasattr(frame, '_operation_type'):
                operation_type = frame._operation_type
                if operation_type not in frames_by_category:
                    frames_by_category[operation_type] = []
                frames_by_category[operation_type].append(frame)
        
        # Sort frames within each category by dex number and show them
        for operation_type, frames in frames_by_category.items():
            # Sort frames by dex number (lowest first)
            def get_dex_number(frame):
                if hasattr(frame, '_rec_data'):
                    filename = frame._rec_data['from']
                    match = re.match(r'^(\d{3,4})', filename)
                    return int(match.group(1)) if match else 9999
                return 9999
            
            frames.sort(key=get_dex_number)
            
            # Show frames in proper order
            for frame in frames:
                frame.grid()
    
    
    def clear_search_placeholder(self, event=None):
        """Clear search placeholder when clicked"""
        if hasattr(self, 'fixes_search_entry'):
            if self.fixes_search_entry.get() == "Search fixes...":
                self.fixes_search_entry.delete(0, tk.END)
                self.fixes_search_entry.config(fg='#e0e0e0')
    
    def restore_search_placeholder(self, event=None):
        """Restore search placeholder when focus is lost"""
        if hasattr(self, 'fixes_search_entry'):
            if not self.fixes_search_entry.get():
                self.fixes_search_entry.insert(0, "Search fixes...")
                self.fixes_search_entry.config(fg='#95a5a6')
    
    def save_settings(self):
        """Save current settings"""
        settings = {
            "move_dir": self.move_dir.get(),
            "sprite_dir": self.sprite_dir.get(),
            "output_dir": self.output_dir.get(),
            "log_dir": self.log_dir.get(),
            "use_custom_log_dir": self.use_custom_log_dir.get(),
            "process_all": self.process_all.get(),
            "show_logs": self.show_logs.get(),
            "limit": self.limit_var.get(),
            # Save scaling configuration
            "default_summary_scale": getattr(self, 'default_summary_scale', 2.7),
            "default_front_scale": getattr(self, 'default_front_scale', 1.0),
            "default_back_scale": getattr(self, 'default_back_scale', 1.0),
            "detection_threshold": getattr(self, 'detection_threshold', 1.10),
            "summary_overrides": getattr(self, 'summary_overrides', {}),
            "front_overrides": getattr(self, 'front_overrides', {}),
            "back_overrides": getattr(self, 'back_overrides', {})
        }
        
        settings_file = Path("sprite_converter_settings.json")
        with settings_file.open("w") as f:
            json.dump(settings, f, indent=2)
    
    def load_settings(self):
        """Load saved settings"""
        settings_file = Path("sprite_converter_settings.json")
        if settings_file.exists():
            try:
                with settings_file.open("r") as f:
                    settings = json.load(f)
                
                self.move_dir.set(settings.get("move_dir", ""))
                self.sprite_dir.set(settings.get("sprite_dir", ""))
                self.output_dir.set(settings.get("output_dir", ""))
                self.log_dir.set(settings.get("log_dir", "logs"))
                self.use_custom_log_dir.set(settings.get("use_custom_log_dir", False))
                self.process_all.set(settings.get("process_all", True))
                self.show_logs.set(settings.get("show_logs", True))
                self.limit_var.set(settings.get("limit", ""))
                
                # Load scaling configuration
                self.default_summary_scale = settings.get("default_summary_scale", 2.7)
                self.default_front_scale = settings.get("default_front_scale", 1.0)
                self.default_back_scale = settings.get("default_back_scale", 1.0)
                self.detection_threshold = settings.get("detection_threshold", 1.10)
                self.summary_overrides = settings.get("summary_overrides", {})
                self.front_overrides = settings.get("front_overrides", {})
                self.back_overrides = settings.get("back_overrides", {})
                
                # Apply the log directory toggle state
                self.toggle_log_dir()
                
                # Check directories after loading settings with background threading
                self.root.after(200, self.refresh_analysis)
            except Exception:
                pass  # Use defaults if loading fails
    
    def cleanup_timers(self):
        """Cancel all pending timers to prevent errors on window close"""
        # Cancel preview cycle timer
        if hasattr(self, 'preview_cycle_timer') and self.preview_cycle_timer:
            try:
                self.root.after_cancel(self.preview_cycle_timer)
            except:
                pass
            self.preview_cycle_timer = None
        
        # Cancel search debounce timer
        if hasattr(self, '_search_job'):
            try:
                self.root.after_cancel(self._search_job)
            except:
                pass
            self._search_job = None
        
        # Cancel detect files timer
        if hasattr(self, '_detect_job'):
            try:
                self.root.after_cancel(self._detect_job)
            except:
                pass
            self._detect_job = None
    
    def on_closing(self):
        """Handle window closing gracefully"""
        # Check if processing is running
        if self.processing and self.process_thread and self.process_thread.is_alive():
            response = messagebox.askokcancel(
                "Processing in Progress", 
                "Sprite processing is still running. Closing now may leave temporary files.\n\nDo you want to force quit?"
            )
            if not response:
                return  # User cancelled, don't close
        
        # Clean up timers
        self.cleanup_timers()
        
        # Save settings
        self.save_settings()
        
        # Close window
        self.root.destroy()
    
    def simple_resize_back_frames(self, frames, max_size):
        """Resize back sprite frames using conservative scaling to minimize artifacts."""
        from PIL import Image, ImageFilter
        if not frames:
            return frames
        max_width, max_height = max_size
        resized = []
        for frame in frames:
            frame = frame.convert("RGBA")
            frame_width, frame_height = frame.size
            scale = min(max_width / frame_width, max_height / frame_height)
            new_width = max(1, int(frame_width * scale))
            new_height = max(1, int(frame_height * scale))
            
            # Use smart resampling: NEAREST for integer scaling, LANCZOS for non-integer
            scale_x = new_width / frame_width
            scale_y = new_height / frame_height
            if scale_x == int(scale_x) and scale_y == int(scale_y) and scale_x >= 1.0 and scale_y >= 1.0:
                # Integer upscaling - use NEAREST for crisp pixel art
                resized.append(frame.resize((new_width, new_height), Image.Resampling.NEAREST))
            else:
                # Non-integer scaling - use LANCZOS for smoother results
                resized.append(frame.resize((new_width, new_height), Image.Resampling.LANCZOS))
        return resized


class GUILogHandler(logging.Handler):
    """Custom log handler that sends messages to the GUI"""
    
    def __init__(self, gui):
        super().__init__()
        self.gui = gui
    
    def emit(self, record):
        try:
            msg = self.format(record)
            self.gui.root.after(0, lambda: self.gui.log_message(msg))
        except Exception:
            pass



def main():
    """Main function"""
    root = tk.Tk()
    
    # Set style
    style = ttk.Style()
    style.theme_use('clam')
    
    # Create and run the application
    app = SpriteConverterGUI(root)
    
    # Handle window closing
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    # Start the GUI
    root.mainloop()


if __name__ == "__main__":
    main()
