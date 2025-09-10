#!/usr/bin/env python3
"""
Main entry point for the Speech-to-Text Transcriber application.
Provides both GUI and headless command-line interfaces.
"""

import argparse
import sys
import os
import logging
import signal
import json
import time
from pathlib import Path
from typing import Optional

# Add current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from speech_recorder import SpeechRecorder, SpeechRecorderConfig
from database import TranscriptionDatabase
from audio_recorder import AudioRecorder
from speech_to_text import WhisperTranscriber

# Try to import GUI components (may fail if tkinter not available)
try:
    import tkinter as tk
    from ui import SpeechToTextGUI
    GUI_AVAILABLE = True
except ImportError as e:
    GUI_AVAILABLE = False
    GUI_IMPORT_ERROR = str(e)

logger = logging.getLogger(__name__)


def setup_logging(level: str = "INFO", log_file: Optional[str] = None):
    """Setup logging configuration."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Setup console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)
    
    # Setup file handler if specified
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
            logger.info(f"Logging to file: {log_file}")
        except Exception as e:
            logger.warning(f"Failed to setup file logging: {e}")


class HeadlessRecorder:
    """Headless speech recorder for command-line usage."""
    
    def __init__(self, config: SpeechRecorderConfig):
        """Initialize headless recorder."""
        self.config = config
        self.recorder = SpeechRecorder(config)
        self.running = False
        self.session_count = 0
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Setup callbacks
        self.recorder.on_recording_start = self._on_recording_start
        self.recorder.on_recording_stop = self._on_recording_stop
        self.recorder.on_transcription_complete = self._on_transcription_complete
        self.recorder.on_transcription_error = self._on_transcription_error
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
    
    def _on_recording_start(self, session):
        """Handle recording start."""
        print(f"🎤 Recording started (Session: {session.session_id})")
        if self.config.vad_enabled:
            print("   Speak now... (will auto-stop after silence)")
        else:
            print("   Press Ctrl+R again to stop recording")
    
    def _on_recording_stop(self, session):
        """Handle recording stop."""
        print(f"⏹️  Recording stopped (Duration: {session.duration:.2f}s)")
        print("   Processing transcription...")
    
    def _on_transcription_complete(self, session):
        """Handle transcription completion."""
        self.session_count += 1
        result = session.transcription_result
        
        print(f"✅ Transcription #{self.session_count} complete:")
        print(f"   Text: {result['text']}")
        
        if result.get('confidence'):
            print(f"   Confidence: {result['confidence']:.1%}")
        
        if session.transcription_id:
            print(f"   Database ID: {session.transcription_id}")
        
        if session.audio_file_path:
            print(f"   Audio saved: {session.audio_file_path}")
        
        print()
    
    def _on_transcription_error(self, session, error):
        """Handle transcription error."""
        print(f"❌ Transcription failed for {session.session_id}: {error}")
        print()
    
    def run(self):
        """Run the headless recorder."""
        print("Speech-to-Text Transcriber (Headless Mode)")
        print("=" * 50)
        
        # Initialize
        if not self.recorder.initialize():
            print("❌ Failed to initialize recorder")
            return 1
        
        # Test components
        print("Testing components...")
        test_results = self.recorder.test_components()
        
        failed_components = [name for name, result in test_results.items() if not result]
        if failed_components:
            print(f"⚠️  Warning: Some components failed tests: {failed_components}")
        else:
            print("✅ All components tested successfully")
        
        # Show configuration
        print(f"\nConfiguration:")
        print(f"  Whisper Model: {self.config.whisper_model}")
        print(f"  Sample Rate: {self.config.sample_rate}Hz")
        print(f"  Auto-stop: {'Enabled' if self.config.auto_stop_enabled else 'Disabled'}")
        print(f"  Voice Activity Detection: {'Enabled' if self.config.vad_enabled else 'Disabled'}")
        print(f"  Save Audio Files: {'Enabled' if self.config.save_audio_files else 'Disabled'}")
        print(f"  Global Shortcuts: {'Enabled' if self.config.enable_global_shortcuts else 'Disabled'}")
        
        if self.config.enable_global_shortcuts:
            shortcuts = self.recorder.keyboard_handler.get_hotkeys_info()
            print(f"  Recording Hotkey: {list(shortcuts.values())[0]['keys']}")
        
        print(f"\nDatabase: {self.config.database_path}")
        
        # Get database statistics
        try:
            stats = self.recorder.database.get_statistics()
            print(f"  Total transcriptions: {stats['total_transcriptions']}")
            print(f"  Total duration: {stats['total_duration_seconds']:.1f}s")
        except Exception as e:
            print(f"  Error getting statistics: {e}")
        
        print("\n" + "=" * 50)
        
        if self.config.enable_global_shortcuts:
            print("Ready for recording! Use global hotkeys to start/stop recording.")
            print("Press 'q' + Enter to quit, 's' + Enter for status")
        else:
            print("Ready for recording! Press Enter to start/stop recording.")
            print("Press 'q' + Enter to quit, 's' + Enter for status")
        
        self.running = True
        
        try:
            # Main loop
            while self.running:
                try:
                    user_input = input().strip().lower()
                    
                    if user_input == 'q':
                        break
                    elif user_input == 's':
                        self._show_status()
                    elif user_input == '' and not self.config.enable_global_shortcuts:
                        # Manual recording toggle
                        self.recorder.toggle_recording()
                    elif user_input == 'help' or user_input == 'h':
                        self._show_help()
                    else:
                        if user_input:
                            print(f"Unknown command: {user_input}")
                        print("Type 'help' for available commands")
                
                except EOFError:
                    break
                except KeyboardInterrupt:
                    break
        
        finally:
            self.stop()
        
        return 0
    
    def _show_status(self):
        """Show current status."""
        status = self.recorder.get_status()
        
        print("\nCurrent Status:")
        print(f"  Initialized: {status['is_initialized']}")
        print(f"  Recording: {status['is_recording']}")
        
        if status.get('current_session'):
            session = status['current_session']
            print(f"  Current Session: {session['id']}")
            print(f"    Status: {session['status']}")
            print(f"    Elapsed: {session['elapsed_time']:.1f}s")
            print(f"    Voice Activity: {session['voice_activity_detected']}")
            if session['silence_duration'] > 0:
                print(f"    Silence Duration: {session['silence_duration']:.1f}s")
        
        print(f"  Sessions Completed: {self.session_count}")
        print()
    
    def _show_help(self):
        """Show help information."""
        print("\nAvailable Commands:")
        print("  q          - Quit application")
        print("  s          - Show status")
        print("  help, h    - Show this help")
        
        if not self.config.enable_global_shortcuts:
            print("  Enter      - Start/stop recording")
        
        print("\nGlobal Shortcuts:")
        if self.config.enable_global_shortcuts:
            shortcuts = self.recorder.keyboard_handler.get_hotkeys_info()
            for name, info in shortcuts.items():
                print(f"  {info['keys']} - {info['description']}")
        else:
            print("  Global shortcuts are disabled")
        
        print()
    
    def stop(self):
        """Stop the headless recorder."""
        self.running = False
        print("\nShutting down...")
        self.recorder.shutdown()
        print("Goodbye!")


def cmd_record(args):
    """Record audio and transcribe (one-time operation)."""
    try:
        # Create configuration
        config = SpeechRecorderConfig()
        if args.config:
            config = SpeechRecorderConfig.from_file(args.config)
        
        # Override config with command line arguments
        if args.model:
            config.whisper_model = args.model
        if args.device is not None:
            config.audio_device = args.device
        if args.language:
            config.language = args.language
        
        config.save_audio_files = args.save_audio
        config.enable_global_shortcuts = False  # Disable for one-time recording
        config.auto_stop_enabled = not args.manual_stop
        
        if args.duration:
            config.max_recording_duration = args.duration
        
        # Initialize recorder
        recorder = SpeechRecorder(config)
        if not recorder.initialize():
            print("❌ Failed to initialize recorder")
            return 1
        
        print("Starting recording...")
        print(f"Duration: {args.duration}s" if args.duration else "Manual stop")
        print("Speak now...")
        
        # Start recording
        session = recorder.start_recording()
        if not session:
            print("❌ Failed to start recording")
            return 1
        
        if args.duration:
            # Timed recording
            time.sleep(args.duration)
            recorder.stop_recording()
        else:
            # Manual recording
            if args.manual_stop:
                input("Press Enter to stop recording...")
            else:
                # Wait for auto-stop
                while recorder.is_recording:
                    time.sleep(0.1)
        
        # Wait for transcription
        print("Processing transcription...")
        while session.status == "processing":
            time.sleep(0.1)
        
        if session.status == "completed":
            result = session.transcription_result
            print(f"\n✅ Transcription: {result['text']}")
            
            if result.get('confidence'):
                print(f"Confidence: {result['confidence']:.1%}")
            
            if args.output:
                # Save to file
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(result['text'])
                print(f"Saved to: {args.output}")
        
        else:
            print(f"❌ Transcription failed: {session.error_message}")
            return 1
        
        recorder.shutdown()
        return 0
        
    except Exception as e:
        logger.error(f"Error in record command: {e}")
        return 1


def cmd_list(args):
    """List transcriptions in database."""
    try:
        database = TranscriptionDatabase(args.database)
        
        # Search transcriptions
        transcriptions = database.search_transcriptions(
            query=args.query or "",
            limit=args.limit
        )
        
        if not transcriptions:
            print("No transcriptions found")
            return 0
        
        print(f"Found {len(transcriptions)} transcriptions:")
        print()
        
        for trans in transcriptions:
            timestamp = trans.get('timestamp', 'Unknown')
            if isinstance(timestamp, str):
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    timestamp = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    pass
            
            duration = trans.get('duration', 0)
            if duration:
                duration_str = f"{duration:.1f}s"
            else:
                duration_str = "Unknown"
            
            confidence = trans.get('confidence')
            if confidence:
                confidence_str = f"{confidence:.1%}"
            else:
                confidence_str = "Unknown"
            
            text_preview = trans.get('text', '')[:100]
            if len(trans.get('text', '')) > 100:
                text_preview += "..."
            
            print(f"ID: {trans['id']}")
            print(f"  Date: {timestamp}")
            print(f"  Duration: {duration_str}")
            print(f"  Confidence: {confidence_str}")
            print(f"  Text: {text_preview}")
            print()
        
        return 0
        
    except Exception as e:
        logger.error(f"Error listing transcriptions: {e}")
        return 1


def cmd_export(args):
    """Export transcriptions."""
    try:
        database = TranscriptionDatabase(args.database)
        
        if args.format == 'csv':
            success = database.export_to_csv(args.output)
        elif args.format == 'json':
            success = database.export_to_json(args.output)
        else:
            print(f"❌ Unsupported format: {args.format}")
            return 1
        
        if success:
            print(f"✅ Exported transcriptions to {args.output}")
            return 0
        else:
            print(f"❌ Failed to export transcriptions")
            return 1
        
    except Exception as e:
        logger.error(f"Error exporting transcriptions: {e}")
        return 1


def cmd_test(args):
    """Test system components."""
    try:
        print("Testing Speech-to-Text System Components")
        print("=" * 50)
        
        # Test audio recorder
        print("Testing audio recorder...")
        try:
            recorder = AudioRecorder()
            devices = recorder.get_available_devices()
            print(f"✅ Found {len(devices)} audio input devices")
            
            if args.test_audio:
                print("Testing audio input (2 seconds)...")
                result = recorder.test_audio_input(duration=2.0)
                
                if result['success']:
                    print(f"✅ Audio test successful:")
                    print(f"   Max level: {result['max_level']:.3f}")
                    print(f"   Avg level: {result['avg_level']:.3f}")
                else:
                    print(f"❌ Audio test failed: {result['error']}")
            
        except Exception as e:
            print(f"❌ Audio recorder test failed: {e}")
        
        # Test transcriber
        print("\nTesting Whisper transcriber...")
        try:
            transcriber = WhisperTranscriber(model_name=args.model or "base")
            
            if transcriber.wait_for_model(timeout=30):
                print(f"✅ Whisper model '{transcriber.model_name}' loaded successfully")
                print(f"   Device: {transcriber.device}")
                print(f"   Available models: {transcriber.get_available_models()}")
            else:
                print(f"❌ Failed to load Whisper model")
        
        except Exception as e:
            print(f"❌ Transcriber test failed: {e}")
        
        # Test database
        print("\nTesting database...")
        try:
            database = TranscriptionDatabase(args.database)
            stats = database.get_statistics()
            print(f"✅ Database connected successfully")
            print(f"   Total transcriptions: {stats['total_transcriptions']}")
            print(f"   Database file: {args.database}")
        
        except Exception as e:
            print(f"❌ Database test failed: {e}")
        
        # Test keyboard handler (if enabled)
        if not args.no_keyboard:
            print("\nTesting keyboard handler...")
            try:
                from keyboard_handler import GlobalKeyboardHandler
                handler = GlobalKeyboardHandler()
                
                if handler.start_listening():
                    print("✅ Global keyboard handler started")
                    print("   Testing hotkey detection for 5 seconds...")
                    print("   Press Cmd+R (macOS) or Ctrl+R (other) to test")
                    
                    triggered = handler.test_hotkeys(duration=5.0)
                    handler.stop_listening()
                    
                    if triggered:
                        print(f"✅ Detected {len(triggered)} hotkey presses")
                    else:
                        print("ℹ️  No hotkeys detected (this is normal if you didn't press any)")
                else:
                    print("❌ Failed to start keyboard handler")
            
            except Exception as e:
                print(f"❌ Keyboard handler test failed: {e}")
        
        print("\n" + "=" * 50)
        print("System test completed")
        return 0
        
    except Exception as e:
        logger.error(f"Error in test command: {e}")
        return 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Speech-to-Text Transcriber",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s gui                          # Launch GUI interface
  %(prog)s headless                     # Run in headless mode
  %(prog)s record -d 10                 # Record for 10 seconds
  %(prog)s record --manual-stop         # Record until Enter pressed
  %(prog)s list --query "meeting"       # List transcriptions containing "meeting"
  %(prog)s export output.csv            # Export all transcriptions to CSV
  %(prog)s test --test-audio            # Test all components including audio
        """
    )
    
    # Global arguments
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], 
                       default="INFO", help="Logging level")
    parser.add_argument("--log-file", help="Log file path")
    parser.add_argument("--database", default="transcriptions.db", 
                       help="Database file path")
    
    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # GUI command
    gui_parser = subparsers.add_parser("gui", help="Launch GUI interface")
    
    # Headless command
    headless_parser = subparsers.add_parser("headless", help="Run in headless mode")
    
    # Record command
    record_parser = subparsers.add_parser("record", help="Record and transcribe audio")
    record_parser.add_argument("-d", "--duration", type=float, 
                              help="Recording duration in seconds")
    record_parser.add_argument("-o", "--output", help="Output file for transcription")
    record_parser.add_argument("--model", help="Whisper model to use")
    record_parser.add_argument("--language", help="Language for transcription")
    record_parser.add_argument("--device", type=int, help="Audio device ID")
    record_parser.add_argument("--save-audio", action="store_true", 
                              help="Save audio file")
    record_parser.add_argument("--manual-stop", action="store_true", 
                              help="Require manual stop (disable auto-stop)")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List transcriptions")
    list_parser.add_argument("--query", help="Search query")
    list_parser.add_argument("--limit", type=int, default=50, 
                            help="Maximum number of results")
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export transcriptions")
    export_parser.add_argument("output", help="Output file path")
    export_parser.add_argument("--format", choices=["csv", "json"], 
                              default="csv", help="Export format")
    
    # Test command
    test_parser = subparsers.add_parser("test", help="Test system components")
    test_parser.add_argument("--test-audio", action="store_true", 
                            help="Test audio input")
    test_parser.add_argument("--model", help="Whisper model to test")
    test_parser.add_argument("--no-keyboard", action="store_true", 
                            help="Skip keyboard handler test")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level, args.log_file)
    
    # Default to GUI if no command specified and GUI is available
    if not args.command:
        if GUI_AVAILABLE:
            args.command = "gui"
        else:
            print("❌ GUI not available, defaulting to headless mode")
            print(f"GUI import error: {GUI_IMPORT_ERROR}")
            args.command = "headless"
    
    # Execute command
    try:
        if args.command == "gui":
            if not GUI_AVAILABLE:
                print(f"❌ GUI not available: {GUI_IMPORT_ERROR}")
                print("Try installing tkinter: python -m pip install tk")
                return 1
            
            logger.info("Starting GUI application")
            app = SpeechToTextGUI()
            app.run()
            return 0
        
        elif args.command == "headless":
            config = SpeechRecorderConfig()
            if args.config:
                config = SpeechRecorderConfig.from_file(args.config)
            
            config.database_path = args.database
            
            headless = HeadlessRecorder(config)
            return headless.run()
        
        elif args.command == "record":
            return cmd_record(args)
        
        elif args.command == "list":
            return cmd_list(args)
        
        elif args.command == "export":
            return cmd_export(args)
        
        elif args.command == "test":
            return cmd_test(args)
        
        else:
            parser.print_help()
            return 1
    
    except KeyboardInterrupt:
        print("\n⏹️  Interrupted by user")
        return 0
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if args.log_level == "DEBUG":
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())