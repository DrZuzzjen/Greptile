"""
Modern Tkinter GUI for speech-to-text application.
Provides interface for viewing, searching, editing, and exporting transcriptions.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import threading
import queue
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Callable
import json
import logging

from database import TranscriptionDatabase
from speech_to_text import WhisperTranscriber
from audio_recorder import AudioRecorder
from keyboard_handler import GlobalKeyboardHandler

logger = logging.getLogger(__name__)


class ModernStyle:
    """Modern styling constants for the GUI."""
    
    # Colors
    PRIMARY = "#2E86AB"
    SECONDARY = "#A23B72"
    SUCCESS = "#4CAF50"
    WARNING = "#FF9800"
    ERROR = "#F44336"
    BACKGROUND = "#F5F5F5"
    SURFACE = "#FFFFFF"
    TEXT_PRIMARY = "#212121"
    TEXT_SECONDARY = "#757575"
    
    # Fonts
    FONT_FAMILY = "Helvetica"
    FONT_SIZE_LARGE = 14
    FONT_SIZE_MEDIUM = 12
    FONT_SIZE_SMALL = 10


class TranscriptionListFrame(ttk.Frame):
    """Frame for displaying and managing transcription list."""
    
    def __init__(self, parent, database: TranscriptionDatabase, **kwargs):
        super().__init__(parent, **kwargs)
        self.database = database
        self.selected_transcription = None
        self.on_selection_change: Optional[Callable[[Optional[Dict]], None]] = None
        
        self.setup_ui()
        self.refresh_list()
    
    def setup_ui(self):
        """Setup the transcription list UI."""
        # Search frame
        search_frame = ttk.Frame(self)
        search_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Label(search_frame, text="Search:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.on_search_change)
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
        search_entry.pack(side="left", padx=(5, 0), fill="x", expand=True)
        
        ttk.Button(search_frame, text="Clear", command=self.clear_search).pack(side="right", padx=(5, 0))
        
        # Filter frame
        filter_frame = ttk.Frame(self)
        filter_frame.pack(fill="x", padx=5, pady=(0, 5))
        
        ttk.Label(filter_frame, text="Date Range:").pack(side="left")
        self.date_filter_var = tk.StringVar(value="all")
        date_combo = ttk.Combobox(filter_frame, textvariable=self.date_filter_var,
                                 values=["all", "today", "this_week", "this_month"], state="readonly")
        date_combo.pack(side="left", padx=(5, 0))
        date_combo.bind("<<ComboboxSelected>>", self.on_filter_change)
        
        ttk.Button(filter_frame, text="Refresh", command=self.refresh_list).pack(side="right")
        
        # Treeview for transcriptions
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Scrollbars
        v_scroll = ttk.Scrollbar(tree_frame, orient="vertical")
        h_scroll = ttk.Scrollbar(tree_frame, orient="horizontal")
        
        # Treeview
        self.tree = ttk.Treeview(tree_frame, yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        v_scroll.config(command=self.tree.yview)
        h_scroll.config(command=self.tree.xview)
        
        # Configure columns
        self.tree["columns"] = ("timestamp", "duration", "confidence", "preview")
        self.tree["show"] = "tree headings"
        
        self.tree.heading("#0", text="ID")
        self.tree.heading("timestamp", text="Date/Time")
        self.tree.heading("duration", text="Duration")
        self.tree.heading("confidence", text="Confidence")
        self.tree.heading("preview", text="Preview")
        
        self.tree.column("#0", width=60, minwidth=50)
        self.tree.column("timestamp", width=150, minwidth=120)
        self.tree.column("duration", width=80, minwidth=60)
        self.tree.column("confidence", width=80, minwidth=60)
        self.tree.column("preview", width=300, minwidth=200)
        
        # Bind events
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        
        # Pack scrollbars and tree
        v_scroll.pack(side="right", fill="y")
        h_scroll.pack(side="bottom", fill="x")
        self.tree.pack(fill="both", expand=True)
        
        # Context menu
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Edit", command=self.edit_selected)
        self.context_menu.add_command(label="Delete", command=self.delete_selected)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Export", command=self.export_selected)
        
        self.tree.bind("<Button-2>", self.show_context_menu)  # Right-click on macOS
        self.tree.bind("<Button-3>", self.show_context_menu)  # Right-click on Windows/Linux
    
    def on_search_change(self, *args):
        """Handle search text change."""
        # Debounce search to avoid too frequent updates
        if hasattr(self, 'search_timer'):
            self.after_cancel(self.search_timer)
        self.search_timer = self.after(300, self.refresh_list)
    
    def on_filter_change(self, event=None):
        """Handle date filter change."""
        self.refresh_list()
    
    def clear_search(self):
        """Clear search text."""
        self.search_var.set("")
    
    def refresh_list(self):
        """Refresh the transcription list."""
        # Clear current items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        try:
            # Get search parameters
            search_query = self.search_var.get().strip()
            date_filter = self.date_filter_var.get()
            
            # Calculate date range
            start_date = None
            if date_filter == "today":
                start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            elif date_filter == "this_week":
                today = datetime.now()
                start_date = today - timedelta(days=today.weekday())
                start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            elif date_filter == "this_month":
                today = datetime.now()
                start_date = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            # Search transcriptions
            transcriptions = self.database.search_transcriptions(
                query=search_query,
                start_date=start_date,
                limit=1000
            )
            
            # Populate tree
            for trans in transcriptions:
                # Format data for display
                timestamp_str = self.format_timestamp(trans.get('timestamp'))
                duration_str = self.format_duration(trans.get('duration'))
                confidence_str = self.format_confidence(trans.get('confidence'))
                preview = self.format_preview(trans.get('text', ''))
                
                self.tree.insert("", "end", text=str(trans['id']),
                               values=(timestamp_str, duration_str, confidence_str, preview),
                               tags=("transcription",))
            
            # Update status
            status_text = f"Found {len(transcriptions)} transcriptions"
            if search_query:
                status_text += f" matching '{search_query}'"
            if date_filter != "all":
                status_text += f" from {date_filter.replace('_', ' ')}"
            
            # You can add a status label if needed
            
        except Exception as e:
            logger.error(f"Error refreshing transcription list: {e}")
            messagebox.showerror("Error", f"Failed to load transcriptions: {e}")
    
    def format_timestamp(self, timestamp) -> str:
        """Format timestamp for display."""
        if not timestamp:
            return ""
        
        try:
            if isinstance(timestamp, str):
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            else:
                dt = timestamp
            
            return dt.strftime("%m/%d/%Y %H:%M")
        except:
            return str(timestamp)
    
    def format_duration(self, duration) -> str:
        """Format duration for display."""
        if not duration:
            return ""
        
        try:
            seconds = float(duration)
            if seconds < 60:
                return f"{seconds:.1f}s"
            else:
                minutes = int(seconds // 60)
                remaining_seconds = seconds % 60
                return f"{minutes}m {remaining_seconds:.0f}s"
        except:
            return str(duration)
    
    def format_confidence(self, confidence) -> str:
        """Format confidence score for display."""
        if confidence is None:
            return ""
        
        try:
            score = float(confidence)
            return f"{score:.1%}"
        except:
            return str(confidence)
    
    def format_preview(self, text: str, max_length: int = 50) -> str:
        """Format text preview for display."""
        if not text:
            return ""
        
        text = text.strip()
        if len(text) <= max_length:
            return text
        
        return text[:max_length-3] + "..."
    
    def on_tree_select(self, event):
        """Handle tree selection change."""
        selection = self.tree.selection()
        if selection:
            item = self.tree.item(selection[0])
            transcription_id = int(item['text'])
            
            # Get full transcription data
            self.selected_transcription = self.database.get_transcription(transcription_id)
            
            if self.on_selection_change:
                self.on_selection_change(self.selected_transcription)
        else:
            self.selected_transcription = None
            if self.on_selection_change:
                self.on_selection_change(None)
    
    def on_tree_double_click(self, event):
        """Handle double-click on tree item."""
        self.edit_selected()
    
    def show_context_menu(self, event):
        """Show context menu."""
        # Select item under cursor
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)
    
    def edit_selected(self):
        """Edit selected transcription."""
        if self.selected_transcription:
            # Open edit dialog
            EditTranscriptionDialog(self, self.selected_transcription, self.database)
            self.refresh_list()
    
    def delete_selected(self):
        """Delete selected transcription."""
        if not self.selected_transcription:
            return
        
        if messagebox.askyesno("Confirm Delete", 
                              f"Are you sure you want to delete transcription ID {self.selected_transcription['id']}?"):
            try:
                self.database.delete_transcription(self.selected_transcription['id'])
                self.refresh_list()
                messagebox.showinfo("Success", "Transcription deleted successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete transcription: {e}")
    
    def export_selected(self):
        """Export selected transcription."""
        if not self.selected_transcription:
            return
        
        filename = filedialog.asksaveasfilename(
            title="Export Transcription",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                if filename.endswith('.json'):
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(self.selected_transcription, f, indent=2, default=str)
                else:
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(self.selected_transcription['text'])
                
                messagebox.showinfo("Success", f"Transcription exported to {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export transcription: {e}")


class TranscriptionDetailFrame(ttk.Frame):
    """Frame for displaying and editing transcription details."""
    
    def __init__(self, parent, database: TranscriptionDatabase, **kwargs):
        super().__init__(parent, **kwargs)
        self.database = database
        self.current_transcription = None
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the detail view UI."""
        # Header
        header_frame = ttk.Frame(self)
        header_frame.pack(fill="x", padx=5, pady=5)
        
        self.header_label = ttk.Label(header_frame, text="Select a transcription to view details",
                                     font=(ModernStyle.FONT_FAMILY, ModernStyle.FONT_SIZE_LARGE, "bold"))
        self.header_label.pack(side="left")
        
        # Buttons
        button_frame = ttk.Frame(header_frame)
        button_frame.pack(side="right")
        
        self.edit_button = ttk.Button(button_frame, text="Edit", command=self.edit_transcription, state="disabled")
        self.edit_button.pack(side="left", padx=2)
        
        self.save_button = ttk.Button(button_frame, text="Save", command=self.save_changes, state="disabled")
        self.save_button.pack(side="left", padx=2)
        
        self.cancel_button = ttk.Button(button_frame, text="Cancel", command=self.cancel_edit, state="disabled")
        self.cancel_button.pack(side="left", padx=2)
        
        # Content frame with scrollbar
        content_frame = ttk.Frame(self)
        content_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Scrollable text widget
        text_frame = ttk.Frame(content_frame)
        text_frame.pack(fill="both", expand=True)
        
        self.text_widget = tk.Text(text_frame, wrap="word", state="disabled",
                                  font=(ModernStyle.FONT_FAMILY, ModernStyle.FONT_SIZE_MEDIUM))
        text_scroll = ttk.Scrollbar(text_frame, orient="vertical", command=self.text_widget.yview)
        self.text_widget.configure(yscrollcommand=text_scroll.set)
        
        self.text_widget.pack(side="left", fill="both", expand=True)
        text_scroll.pack(side="right", fill="y")
        
        # Metadata frame
        meta_frame = ttk.LabelFrame(content_frame, text="Metadata", padding=10)
        meta_frame.pack(fill="x", pady=(10, 0))
        
        # Create metadata labels
        self.meta_labels = {}
        meta_fields = [
            ("ID", "id"),
            ("Timestamp", "timestamp"),
            ("Duration", "duration"),
            ("Confidence", "confidence"),
            ("Audio File", "audio_file_path"),
            ("Tags", "tags"),
            ("Notes", "notes")
        ]
        
        for i, (label_text, field) in enumerate(meta_fields):
            ttk.Label(meta_frame, text=f"{label_text}:").grid(row=i, column=0, sticky="w", padx=(0, 10))
            self.meta_labels[field] = ttk.Label(meta_frame, text="")
            self.meta_labels[field].grid(row=i, column=1, sticky="w")
        
        self.is_editing = False
    
    def show_transcription(self, transcription: Optional[Dict]):
        """Display transcription details."""
        self.current_transcription = transcription
        
        if transcription is None:
            self.clear_display()
            return
        
        try:
            # Update header
            self.header_label.config(text=f"Transcription ID: {transcription['id']}")
            
            # Update text content
            self.text_widget.config(state="normal")
            self.text_widget.delete(1.0, tk.END)
            self.text_widget.insert(1.0, transcription.get('text', ''))
            self.text_widget.config(state="disabled")
            
            # Update metadata
            self.meta_labels['id'].config(text=str(transcription['id']))
            self.meta_labels['timestamp'].config(text=self.format_timestamp(transcription.get('timestamp')))
            self.meta_labels['duration'].config(text=self.format_duration(transcription.get('duration')))
            self.meta_labels['confidence'].config(text=self.format_confidence(transcription.get('confidence')))
            self.meta_labels['audio_file_path'].config(text=transcription.get('audio_file_path', 'N/A'))
            self.meta_labels['tags'].config(text=self.format_tags(transcription.get('tags')))
            self.meta_labels['notes'].config(text=transcription.get('notes', 'N/A'))
            
            # Enable edit button
            self.edit_button.config(state="normal")
            
        except Exception as e:
            logger.error(f"Error displaying transcription: {e}")
            messagebox.showerror("Error", f"Failed to display transcription: {e}")
    
    def clear_display(self):
        """Clear the display."""
        self.header_label.config(text="Select a transcription to view details")
        
        self.text_widget.config(state="normal")
        self.text_widget.delete(1.0, tk.END)
        self.text_widget.config(state="disabled")
        
        for label in self.meta_labels.values():
            label.config(text="")
        
        self.edit_button.config(state="disabled")
        self.save_button.config(state="disabled")
        self.cancel_button.config(state="disabled")
        
        self.is_editing = False
    
    def edit_transcription(self):
        """Enable editing mode."""
        if not self.current_transcription:
            return
        
        self.is_editing = True
        self.text_widget.config(state="normal")
        self.edit_button.config(state="disabled")
        self.save_button.config(state="normal")
        self.cancel_button.config(state="normal")
    
    def save_changes(self):
        """Save changes to the transcription."""
        if not self.current_transcription or not self.is_editing:
            return
        
        try:
            # Get updated text
            new_text = self.text_widget.get(1.0, tk.END).strip()
            
            # Update in database
            success = self.database.update_transcription(
                self.current_transcription['id'],
                text=new_text
            )
            
            if success:
                self.current_transcription['text'] = new_text
                self.cancel_edit()
                messagebox.showinfo("Success", "Transcription updated successfully")
            else:
                messagebox.showerror("Error", "Failed to update transcription")
                
        except Exception as e:
            logger.error(f"Error saving transcription: {e}")
            messagebox.showerror("Error", f"Failed to save changes: {e}")
    
    def cancel_edit(self):
        """Cancel editing and restore original content."""
        if not self.current_transcription:
            return
        
        self.is_editing = False
        self.text_widget.config(state="normal")
        self.text_widget.delete(1.0, tk.END)
        self.text_widget.insert(1.0, self.current_transcription.get('text', ''))
        self.text_widget.config(state="disabled")
        
        self.edit_button.config(state="normal")
        self.save_button.config(state="disabled")
        self.cancel_button.config(state="disabled")
    
    def format_timestamp(self, timestamp) -> str:
        """Format timestamp for display."""
        if not timestamp:
            return "N/A"
        
        try:
            if isinstance(timestamp, str):
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            else:
                dt = timestamp
            
            return dt.strftime("%B %d, %Y at %H:%M:%S")
        except:
            return str(timestamp)
    
    def format_duration(self, duration) -> str:
        """Format duration for display."""
        if not duration:
            return "N/A"
        
        try:
            seconds = float(duration)
            if seconds < 60:
                return f"{seconds:.2f} seconds"
            else:
                minutes = int(seconds // 60)
                remaining_seconds = seconds % 60
                return f"{minutes} minutes, {remaining_seconds:.1f} seconds"
        except:
            return str(duration)
    
    def format_confidence(self, confidence) -> str:
        """Format confidence score for display."""
        if confidence is None:
            return "N/A"
        
        try:
            score = float(confidence)
            return f"{score:.1%}"
        except:
            return str(confidence)
    
    def format_tags(self, tags) -> str:
        """Format tags for display."""
        if not tags:
            return "N/A"
        
        if isinstance(tags, list):
            return ", ".join(tags)
        
        return str(tags)


class RecordingControlFrame(ttk.Frame):
    """Frame for recording controls and status."""
    
    def __init__(self, parent, recorder: AudioRecorder, transcriber: WhisperTranscriber,
                 database: TranscriptionDatabase, **kwargs):
        super().__init__(parent, **kwargs)
        self.recorder = recorder
        self.transcriber = transcriber
        self.database = database
        
        self.is_recording = False
        self.current_audio = None
        self.transcription_queue = queue.Queue()
        
        # Callbacks
        self.on_transcription_complete: Optional[Callable] = None
        
        self.setup_ui()
        self.start_status_update()
    
    def setup_ui(self):
        """Setup the recording control UI."""
        # Main control frame
        control_frame = ttk.Frame(self)
        control_frame.pack(fill="x", padx=10, pady=10)
        
        # Recording button
        self.record_button = ttk.Button(control_frame, text="🎤 Start Recording",
                                       command=self.toggle_recording, style="Accent.TButton")
        self.record_button.pack(side="left", padx=(0, 10))
        
        # Status label
        self.status_label = ttk.Label(control_frame, text="Ready to record",
                                     font=(ModernStyle.FONT_FAMILY, ModernStyle.FONT_SIZE_MEDIUM))
        self.status_label.pack(side="left", padx=(0, 10))
        
        # Audio level indicator (simple progress bar)
        self.level_var = tk.DoubleVar()
        self.level_bar = ttk.Progressbar(control_frame, variable=self.level_var,
                                        maximum=100, length=100)
        self.level_bar.pack(side="left", padx=(0, 10))
        
        # Settings button
        ttk.Button(control_frame, text="Settings", command=self.show_settings).pack(side="right")
        
        # Progress frame for transcription
        progress_frame = ttk.Frame(self)
        progress_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        self.progress_label = ttk.Label(progress_frame, text="")
        self.progress_label.pack(anchor="w")
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var,
                                           mode="indeterminate")
    
    def toggle_recording(self):
        """Toggle recording on/off."""
        if self.is_recording:
            self.stop_recording()
        else:
            self.start_recording()
    
    def start_recording(self):
        """Start audio recording."""
        try:
            if self.recorder.start_recording():
                self.is_recording = True
                self.record_button.config(text="⏹️ Stop Recording", style="Accent.TButton")
                self.status_label.config(text="Recording...")
                self.progress_label.config(text="")
                
                # Setup audio level callback
                self.recorder.on_audio_chunk = self.update_audio_level
                
                logger.info("Recording started from UI")
            else:
                messagebox.showerror("Error", "Failed to start recording")
                
        except Exception as e:
            logger.error(f"Error starting recording: {e}")
            messagebox.showerror("Error", f"Failed to start recording: {e}")
    
    def stop_recording(self):
        """Stop audio recording and start transcription."""
        try:
            self.current_audio = self.recorder.stop_recording()
            self.is_recording = False
            self.record_button.config(text="🎤 Start Recording")
            self.level_var.set(0)
            
            if self.current_audio is not None:
                self.status_label.config(text="Processing...")
                self.progress_label.config(text="Transcribing audio...")
                self.progress_bar.pack(fill="x", pady=(5, 0))
                self.progress_bar.start()
                
                # Start transcription in background
                threading.Thread(target=self.process_transcription, daemon=True).start()
            else:
                self.status_label.config(text="No audio recorded")
                
        except Exception as e:
            logger.error(f"Error stopping recording: {e}")
            messagebox.showerror("Error", f"Failed to stop recording: {e}")
    
    def process_transcription(self):
        """Process audio transcription in background thread."""
        try:
            # Transcribe audio
            result = self.transcriber.transcribe_array(
                self.current_audio,
                sample_rate=self.recorder.sample_rate
            )
            
            if 'error' in result:
                self.transcription_queue.put(('error', result['error']))
                return
            
            # Calculate duration
            duration = len(self.current_audio) / self.recorder.sample_rate
            
            # Save to database
            transcription_id = self.database.add_transcription(
                text=result['text'],
                duration=duration,
                confidence=result.get('confidence'),
                notes=f"Model: {result.get('model_name', 'unknown')}"
            )
            
            self.transcription_queue.put(('success', {
                'id': transcription_id,
                'text': result['text'],
                'duration': duration,
                'confidence': result.get('confidence')
            }))
            
        except Exception as e:
            logger.error(f"Error processing transcription: {e}")
            self.transcription_queue.put(('error', str(e)))
    
    def update_audio_level(self, audio_chunk):
        """Update audio level indicator."""
        if self.is_recording:
            level = self.recorder.get_audio_level(audio_chunk)
            self.level_var.set(level * 100)
    
    def start_status_update(self):
        """Start periodic status updates."""
        self.check_transcription_queue()
        self.after(100, self.start_status_update)
    
    def check_transcription_queue(self):
        """Check for completed transcriptions."""
        try:
            while True:
                status, data = self.transcription_queue.get_nowait()
                
                if status == 'success':
                    self.progress_bar.stop()
                    self.progress_bar.pack_forget()
                    self.status_label.config(text=f"Transcription complete (ID: {data['id']})")
                    self.progress_label.config(text=f"Text: {data['text'][:50]}...")
                    
                    if self.on_transcription_complete:
                        self.on_transcription_complete()
                        
                elif status == 'error':
                    self.progress_bar.stop()
                    self.progress_bar.pack_forget()
                    self.status_label.config(text="Transcription failed")
                    self.progress_label.config(text="")
                    messagebox.showerror("Transcription Error", f"Failed to transcribe audio: {data}")
                
        except queue.Empty:
            pass
    
    def show_settings(self):
        """Show settings dialog."""
        SettingsDialog(self, self.recorder, self.transcriber)


class EditTranscriptionDialog:
    """Dialog for editing transcription details."""
    
    def __init__(self, parent, transcription: Dict, database: TranscriptionDatabase):
        self.transcription = transcription
        self.database = database
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Edit Transcription ID: {transcription['id']}")
        self.dialog.geometry("600x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.setup_ui()
        self.load_data()
    
    def setup_ui(self):
        """Setup the edit dialog UI."""
        # Text frame
        text_frame = ttk.LabelFrame(self.dialog, text="Transcription Text", padding=10)
        text_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.text_widget = tk.Text(text_frame, wrap="word", height=10,
                                  font=(ModernStyle.FONT_FAMILY, ModernStyle.FONT_SIZE_MEDIUM))
        text_scroll = ttk.Scrollbar(text_frame, orient="vertical", command=self.text_widget.yview)
        self.text_widget.configure(yscrollcommand=text_scroll.set)
        
        self.text_widget.pack(side="left", fill="both", expand=True)
        text_scroll.pack(side="right", fill="y")
        
        # Metadata frame
        meta_frame = ttk.LabelFrame(self.dialog, text="Metadata", padding=10)
        meta_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        # Tags
        ttk.Label(meta_frame, text="Tags:").grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.tags_var = tk.StringVar()
        ttk.Entry(meta_frame, textvariable=self.tags_var, width=50).grid(row=0, column=1, sticky="ew")
        
        # Notes
        ttk.Label(meta_frame, text="Notes:").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=(5, 0))
        self.notes_var = tk.StringVar()
        ttk.Entry(meta_frame, textvariable=self.notes_var, width=50).grid(row=1, column=1, sticky="ew", pady=(5, 0))
        
        meta_frame.columnconfigure(1, weight=1)
        
        # Button frame
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Button(button_frame, text="Save", command=self.save_changes).pack(side="right", padx=(5, 0))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side="right")
    
    def load_data(self):
        """Load transcription data into the dialog."""
        self.text_widget.insert(1.0, self.transcription.get('text', ''))
        
        # Format tags
        tags = self.transcription.get('tags', [])
        if isinstance(tags, list):
            self.tags_var.set(', '.join(tags))
        else:
            self.tags_var.set(str(tags) if tags else '')
        
        self.notes_var.set(self.transcription.get('notes', ''))
    
    def save_changes(self):
        """Save changes to the database."""
        try:
            # Get updated data
            new_text = self.text_widget.get(1.0, tk.END).strip()
            new_tags_str = self.tags_var.get().strip()
            new_notes = self.notes_var.get().strip()
            
            # Parse tags
            new_tags = [tag.strip() for tag in new_tags_str.split(',') if tag.strip()] if new_tags_str else []
            
            # Update in database
            success = self.database.update_transcription(
                self.transcription['id'],
                text=new_text,
                tags=new_tags,
                notes=new_notes if new_notes else None
            )
            
            if success:
                messagebox.showinfo("Success", "Transcription updated successfully")
                self.dialog.destroy()
            else:
                messagebox.showerror("Error", "Failed to update transcription")
                
        except Exception as e:
            logger.error(f"Error saving transcription changes: {e}")
            messagebox.showerror("Error", f"Failed to save changes: {e}")


class SettingsDialog:
    """Settings dialog for configuration."""
    
    def __init__(self, parent, recorder: AudioRecorder, transcriber: WhisperTranscriber):
        self.recorder = recorder
        self.transcriber = transcriber
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Settings")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.setup_ui()
        self.load_settings()
    
    def setup_ui(self):
        """Setup the settings dialog UI."""
        notebook = ttk.Notebook(self.dialog)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Audio settings tab
        audio_frame = ttk.Frame(notebook)
        notebook.add(audio_frame, text="Audio")
        
        # Device selection
        ttk.Label(audio_frame, text="Input Device:").grid(row=0, column=0, sticky="w", padx=10, pady=10)
        self.device_var = tk.StringVar()
        device_combo = ttk.Combobox(audio_frame, textvariable=self.device_var, state="readonly")
        device_combo.grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=10)
        
        # Sample rate
        ttk.Label(audio_frame, text="Sample Rate:").grid(row=1, column=0, sticky="w", padx=10, pady=(0, 10))
        self.sample_rate_var = tk.StringVar()
        sample_rate_combo = ttk.Combobox(audio_frame, textvariable=self.sample_rate_var,
                                        values=["16000", "22050", "44100", "48000"], state="readonly")
        sample_rate_combo.grid(row=1, column=1, sticky="ew", padx=(0, 10), pady=(0, 10))
        
        # Test audio button
        ttk.Button(audio_frame, text="Test Audio", command=self.test_audio).grid(row=2, column=0, columnspan=2, pady=10)
        
        audio_frame.columnconfigure(1, weight=1)
        
        # Transcription settings tab
        transcription_frame = ttk.Frame(notebook)
        notebook.add(transcription_frame, text="Transcription")
        
        # Model selection
        ttk.Label(transcription_frame, text="Whisper Model:").grid(row=0, column=0, sticky="w", padx=10, pady=10)
        self.model_var = tk.StringVar()
        model_combo = ttk.Combobox(transcription_frame, textvariable=self.model_var,
                                  values=self.transcriber.get_available_models(), state="readonly")
        model_combo.grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=10)
        
        # Language selection
        ttk.Label(transcription_frame, text="Language:").grid(row=1, column=0, sticky="w", padx=10, pady=(0, 10))
        self.language_var = tk.StringVar()
        language_combo = ttk.Combobox(transcription_frame, textvariable=self.language_var,
                                     values=["auto"] + self.transcriber.get_supported_languages()[:20])
        language_combo.grid(row=1, column=1, sticky="ew", padx=(0, 10), pady=(0, 10))
        
        transcription_frame.columnconfigure(1, weight=1)
        
        # Button frame
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Button(button_frame, text="Apply", command=self.apply_settings).pack(side="right", padx=(5, 0))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side="right")
        
        # Load device list
        self.load_devices(device_combo)
    
    def load_devices(self, combo):
        """Load available audio devices."""
        try:
            devices = self.recorder.get_available_devices()
            device_names = ["Default"] + [f"{dev['id']}: {dev['name']}" for dev in devices]
            combo['values'] = device_names
        except Exception as e:
            logger.error(f"Error loading devices: {e}")
    
    def load_settings(self):
        """Load current settings."""
        self.device_var.set("Default")
        self.sample_rate_var.set(str(self.recorder.sample_rate))
        self.model_var.set(self.transcriber.model_name)
        self.language_var.set(self.transcriber.language or "auto")
    
    def apply_settings(self):
        """Apply settings changes."""
        try:
            # Apply audio settings
            device_text = self.device_var.get()
            if device_text != "Default":
                device_id = int(device_text.split(":")[0])
                self.recorder.set_device(device_id)
            
            # Apply transcription settings
            new_model = self.model_var.get()
            if new_model != self.transcriber.model_name:
                self.transcriber.set_model(new_model)
            
            new_language = self.language_var.get()
            if new_language == "auto":
                new_language = None
            self.transcriber.language = new_language
            
            messagebox.showinfo("Success", "Settings applied successfully")
            self.dialog.destroy()
            
        except Exception as e:
            logger.error(f"Error applying settings: {e}")
            messagebox.showerror("Error", f"Failed to apply settings: {e}")
    
    def test_audio(self):
        """Test audio input."""
        try:
            result = self.recorder.test_audio_input(duration=2.0)
            
            if result['success']:
                message = f"Audio test successful!\n\n"
                message += f"Duration: {result['duration']:.2f}s\n"
                message += f"Max Level: {result['max_level']:.3f}\n"
                message += f"Avg Level: {result['avg_level']:.3f}\n"
                message += f"Sample Rate: {result['sample_rate']}Hz"
                messagebox.showinfo("Audio Test", message)
            else:
                messagebox.showerror("Audio Test", f"Audio test failed: {result['error']}")
                
        except Exception as e:
            messagebox.showerror("Audio Test", f"Audio test error: {e}")


class SpeechToTextGUI:
    """Main GUI application for speech-to-text."""
    
    def __init__(self):
        """Initialize the GUI application."""
        self.root = tk.Tk()
        self.root.title("Speech-to-Text Transcriber")
        self.root.geometry("1200x800")
        
        # Initialize components
        self.database = TranscriptionDatabase()
        self.recorder = AudioRecorder()
        self.transcriber = WhisperTranscriber()
        self.keyboard_handler = GlobalKeyboardHandler()
        
        # Setup keyboard handler callbacks
        self.keyboard_handler.on_recording_start = self.on_global_recording_start
        self.keyboard_handler.on_recording_stop = self.on_global_recording_stop
        
        self.setup_ui()
        self.setup_styles()
        
        # Start keyboard listener
        self.keyboard_handler.start_listening()
        
        # Bind window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def setup_styles(self):
        """Setup custom styles."""
        style = ttk.Style()
        
        # Configure accent button style
        style.configure("Accent.TButton",
                       background=ModernStyle.PRIMARY,
                       foreground="white",
                       borderwidth=0,
                       focuscolor='none')
        style.map("Accent.TButton",
                 background=[('active', ModernStyle.SECONDARY)])
    
    def setup_ui(self):
        """Setup the main UI."""
        # Main paned window
        main_paned = ttk.PanedWindow(self.root, orient="horizontal")
        main_paned.pack(fill="both", expand=True)
        
        # Left panel for transcription list
        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=1)
        
        self.transcription_list = TranscriptionListFrame(left_frame, self.database)
        self.transcription_list.pack(fill="both", expand=True)
        self.transcription_list.on_selection_change = self.on_transcription_select
        
        # Right panel
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=2)
        
        # Recording controls at top
        self.recording_control = RecordingControlFrame(right_frame, self.recorder,
                                                      self.transcriber, self.database)
        self.recording_control.pack(fill="x")
        self.recording_control.on_transcription_complete = self.on_transcription_complete
        
        # Transcription detail below
        self.transcription_detail = TranscriptionDetailFrame(right_frame, self.database)
        self.transcription_detail.pack(fill="both", expand=True)
        
        # Menu bar
        self.setup_menu()
        
        # Status bar
        self.status_bar = ttk.Label(self.root, text="Ready", relief="sunken")
        self.status_bar.pack(side="bottom", fill="x")
    
    def setup_menu(self):
        """Setup menu bar."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Export All...", command=self.export_all)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Settings", command=self.show_settings)
        tools_menu.add_command(label="Database Statistics", command=self.show_statistics)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Keyboard Shortcuts", command=self.show_shortcuts)
        help_menu.add_command(label="About", command=self.show_about)
    
    def on_transcription_select(self, transcription: Optional[Dict]):
        """Handle transcription selection."""
        self.transcription_detail.show_transcription(transcription)
    
    def on_transcription_complete(self):
        """Handle completed transcription."""
        self.transcription_list.refresh_list()
        self.status_bar.config(text="New transcription added")
    
    def on_global_recording_start(self):
        """Handle global recording start."""
        if not self.recording_control.is_recording:
            self.recording_control.start_recording()
    
    def on_global_recording_stop(self):
        """Handle global recording stop."""
        if self.recording_control.is_recording:
            self.recording_control.stop_recording()
    
    def export_all(self):
        """Export all transcriptions."""
        filename = filedialog.asksaveasfilename(
            title="Export All Transcriptions",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("JSON files", "*.json")]
        )
        
        if filename:
            try:
                if filename.endswith('.json'):
                    success = self.database.export_to_json(filename)
                else:
                    success = self.database.export_to_csv(filename)
                
                if success:
                    messagebox.showinfo("Success", f"Transcriptions exported to {filename}")
                else:
                    messagebox.showerror("Error", "Failed to export transcriptions")
                    
            except Exception as e:
                messagebox.showerror("Error", f"Export failed: {e}")
    
    def show_settings(self):
        """Show settings dialog."""
        SettingsDialog(self.root, self.recorder, self.transcriber)
    
    def show_statistics(self):
        """Show database statistics."""
        try:
            stats = self.database.get_statistics()
            
            message = "Database Statistics:\n\n"
            message += f"Total Transcriptions: {stats['total_transcriptions']}\n"
            message += f"Total Duration: {stats['total_duration_seconds']:.1f} seconds\n"
            message += f"Average Duration: {stats['average_duration_seconds']:.1f} seconds\n"
            message += f"Recent (7 days): {stats['recent_transcriptions']}\n\n"
            
            if stats['most_common_tags']:
                message += "Most Common Tags:\n"
                for tag, count in stats['most_common_tags'][:5]:
                    message += f"  {tag}: {count}\n"
            
            messagebox.showinfo("Database Statistics", message)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to get statistics: {e}")
    
    def show_shortcuts(self):
        """Show keyboard shortcuts help."""
        shortcuts = self.keyboard_handler.get_hotkeys_info()
        
        message = "Keyboard Shortcuts:\n\n"
        for name, info in shortcuts.items():
            message += f"{info['keys']}: {info['description']}\n"
        
        message += "\nAdditional shortcuts:\n"
        message += "ESC: Stop recording\n"
        message += "Double-click: Edit transcription\n"
        message += "Right-click: Context menu\n"
        
        messagebox.showinfo("Keyboard Shortcuts", message)
    
    def show_about(self):
        """Show about dialog."""
        message = "Speech-to-Text Transcriber\n\n"
        message += "A modern application for recording and transcribing speech\n"
        message += "using OpenAI Whisper for offline processing.\n\n"
        message += "Features:\n"
        message += "• Global keyboard shortcuts\n"
        message += "• Offline speech recognition\n"
        message += "• SQLite database storage\n"
        message += "• Modern GUI interface\n"
        message += "• Export capabilities\n"
        
        messagebox.showinfo("About", message)
    
    def on_closing(self):
        """Handle application closing."""
        try:
            self.keyboard_handler.stop_listening()
            self.root.destroy()
        except Exception as e:
            logger.error(f"Error during application shutdown: {e}")
            self.root.destroy()
    
    def run(self):
        """Run the GUI application."""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.on_closing()


def main():
    """Main entry point for the GUI."""
    # Setup logging
    logging.basicConfig(level=logging.INFO,
                       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    try:
        app = SpeechToTextGUI()
        app.run()
    except Exception as e:
        logger.error(f"Failed to start GUI application: {e}")
        messagebox.showerror("Startup Error", f"Failed to start application: {e}")


if __name__ == "__main__":
    main()