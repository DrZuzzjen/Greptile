"""
Core coordinator for the speech-to-text application.
Integrates audio recording, speech-to-text, database, and keyboard handling.
"""

import logging
import threading
import time
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from datetime import datetime
import queue
import json

from audio_recorder import AudioRecorder, VoiceActivityDetector
from speech_to_text import WhisperTranscriber, TranscriptionQueue
from database import TranscriptionDatabase
from keyboard_handler import GlobalKeyboardHandler

logger = logging.getLogger(__name__)


class SpeechRecorderConfig:
    """Configuration class for SpeechRecorder."""
    
    def __init__(self):
        """Initialize with default configuration."""
        # Audio settings
        self.sample_rate = 16000
        self.channels = 1
        self.audio_device = None
        self.chunk_size = 1024
        
        # Recording settings
        self.min_recording_duration = 0.5  # Minimum seconds to record
        self.max_recording_duration = 300  # Maximum seconds to record
        self.silence_timeout = 2.0  # Seconds of silence before auto-stop
        self.auto_stop_enabled = True
        
        # Voice activity detection
        self.vad_enabled = True
        self.vad_threshold = 0.02
        self.vad_min_duration = 0.1
        
        # Transcription settings
        self.whisper_model = "base"
        self.whisper_device = None
        self.language = None  # Auto-detect
        self.transcription_queue_enabled = True
        self.max_transcription_workers = 1
        
        # Database settings
        self.database_path = "transcriptions.db"
        self.auto_save = True
        self.backup_enabled = False
        self.backup_interval = 3600  # seconds
        
        # Audio file settings
        self.save_audio_files = False
        self.audio_files_directory = "audio_recordings"
        
        # Keyboard shortcuts
        self.enable_global_shortcuts = True
        self.recording_hotkey = None  # Will use default
        
        # Debug settings
        self.debug_mode = False
        self.log_level = logging.INFO
    
    @classmethod
    def from_file(cls, config_path: str) -> 'SpeechRecorderConfig':
        """Load configuration from JSON file."""
        config = cls()
        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
            
            for key, value in data.items():
                if hasattr(config, key):
                    setattr(config, key, value)
            
            logger.info(f"Configuration loaded from {config_path}")
        except Exception as e:
            logger.warning(f"Failed to load config from {config_path}: {e}")
        
        return config
    
    def save_to_file(self, config_path: str):
        """Save configuration to JSON file."""
        try:
            config_dict = {
                key: value for key, value in self.__dict__.items()
                if not key.startswith('_')
            }
            
            with open(config_path, 'w') as f:
                json.dump(config_dict, f, indent=2)
            
            logger.info(f"Configuration saved to {config_path}")
        except Exception as e:
            logger.error(f"Failed to save config to {config_path}: {e}")


class RecordingSession:
    """Represents a single recording session."""
    
    def __init__(self, session_id: str):
        """Initialize recording session."""
        self.session_id = session_id
        self.start_time = datetime.now()
        self.end_time = None
        self.duration = 0.0
        self.audio_data = None
        self.audio_file_path = None
        self.transcription_result = None
        self.transcription_id = None
        self.status = "initialized"  # initialized, recording, processing, completed, failed
        self.error_message = None
        
        # Voice activity tracking
        self.voice_activity_detected = False
        self.last_voice_time = None
        self.silence_duration = 0.0
    
    def start_recording(self):
        """Mark session as recording."""
        self.status = "recording"
        self.start_time = datetime.now()
        logger.info(f"Recording session {self.session_id} started")
    
    def stop_recording(self, audio_data):
        """Mark session as stopped and store audio data."""
        self.end_time = datetime.now()
        self.duration = (self.end_time - self.start_time).total_seconds()
        self.audio_data = audio_data
        self.status = "processing"
        logger.info(f"Recording session {self.session_id} stopped, duration: {self.duration:.2f}s")
    
    def set_transcription_result(self, result: Dict):
        """Set transcription result."""
        self.transcription_result = result
        if 'error' not in result:
            self.status = "completed"
            logger.info(f"Session {self.session_id} transcription completed")
        else:
            self.status = "failed"
            self.error_message = result['error']
            logger.error(f"Session {self.session_id} transcription failed: {self.error_message}")
    
    def set_transcription_id(self, transcription_id: int):
        """Set database transcription ID."""
        self.transcription_id = transcription_id


class SpeechRecorder:
    """Main coordinator class for speech recording and transcription."""
    
    def __init__(self, config: Optional[SpeechRecorderConfig] = None):
        """Initialize the speech recorder."""
        self.config = config or SpeechRecorderConfig()
        
        # Initialize components
        self.audio_recorder = None
        self.transcriber = None
        self.database = None
        self.keyboard_handler = None
        self.transcription_queue = None
        self.vad = None
        
        # State management
        self.is_initialized = False
        self.is_recording = False
        self.current_session: Optional[RecordingSession] = None
        self.session_counter = 0
        
        # Threading
        self.recording_thread = None
        self.processing_queue = queue.Queue()
        self.processing_thread = None
        self.stop_event = threading.Event()
        
        # Callbacks
        self.on_recording_start: Optional[Callable[[RecordingSession], None]] = None
        self.on_recording_stop: Optional[Callable[[RecordingSession], None]] = None
        self.on_transcription_complete: Optional[Callable[[RecordingSession], None]] = None
        self.on_transcription_error: Optional[Callable[[RecordingSession, str], None]] = None
        self.on_voice_activity: Optional[Callable[[bool], None]] = None
        
        # Audio file management
        if self.config.save_audio_files:
            self.audio_files_path = Path(self.config.audio_files_directory)
            self.audio_files_path.mkdir(parents=True, exist_ok=True)
        
        # Setup logging
        logging.getLogger().setLevel(self.config.log_level)
    
    def initialize(self) -> bool:
        """Initialize all components."""
        try:
            logger.info("Initializing SpeechRecorder...")
            
            # Initialize database
            logger.info("Initializing database...")
            self.database = TranscriptionDatabase(self.config.database_path)
            
            # Initialize audio recorder
            logger.info("Initializing audio recorder...")
            self.audio_recorder = AudioRecorder(
                sample_rate=self.config.sample_rate,
                channels=self.config.channels,
                device=self.config.audio_device,
                chunk_size=self.config.chunk_size
            )
            
            # Setup audio callbacks
            self.audio_recorder.on_audio_chunk = self._on_audio_chunk
            
            # Initialize transcriber
            logger.info(f"Initializing Whisper transcriber (model: {self.config.whisper_model})...")
            self.transcriber = WhisperTranscriber(
                model_name=self.config.whisper_model,
                device=self.config.whisper_device,
                language=self.config.language
            )
            
            # Setup transcription callbacks
            self.transcriber.on_transcription_complete = self._on_transcription_complete
            self.transcriber.on_transcription_error = self._on_transcription_error
            
            # Initialize transcription queue if enabled
            if self.config.transcription_queue_enabled:
                self.transcription_queue = TranscriptionQueue(
                    self.transcriber,
                    max_workers=self.config.max_transcription_workers
                )
                self.transcription_queue.on_task_complete = self._on_queue_transcription_complete
                self.transcription_queue.start()
            
            # Initialize voice activity detector
            if self.config.vad_enabled:
                self.vad = VoiceActivityDetector(
                    threshold=self.config.vad_threshold,
                    min_duration=self.config.vad_min_duration
                )
            
            # Initialize keyboard handler
            if self.config.enable_global_shortcuts:
                logger.info("Initializing global keyboard shortcuts...")
                self.keyboard_handler = GlobalKeyboardHandler()
                self.keyboard_handler.on_recording_start = self._on_hotkey_recording_start
                self.keyboard_handler.on_recording_stop = self._on_hotkey_recording_stop
                
                if not self.keyboard_handler.start_listening():
                    logger.warning("Failed to start global keyboard listener")
            
            # Start processing thread
            self.processing_thread = threading.Thread(target=self._processing_worker)
            self.processing_thread.daemon = True
            self.processing_thread.start()
            
            self.is_initialized = True
            logger.info("SpeechRecorder initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize SpeechRecorder: {e}")
            return False
    
    def shutdown(self):
        """Shutdown the speech recorder and cleanup resources."""
        logger.info("Shutting down SpeechRecorder...")
        
        # Stop recording if active
        if self.is_recording:
            self.stop_recording()
        
        # Stop processing
        self.stop_event.set()
        
        # Stop transcription queue
        if self.transcription_queue:
            self.transcription_queue.stop()
        
        # Stop keyboard handler
        if self.keyboard_handler:
            self.keyboard_handler.stop_listening()
        
        # Wait for processing thread
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=5.0)
        
        logger.info("SpeechRecorder shutdown complete")
    
    def start_recording(self) -> Optional[RecordingSession]:
        """Start a new recording session."""
        if not self.is_initialized:
            logger.error("SpeechRecorder not initialized")
            return None
        
        if self.is_recording:
            logger.warning("Recording already in progress")
            return self.current_session
        
        try:
            # Create new session
            self.session_counter += 1
            session_id = f"session_{self.session_counter}_{int(time.time())}"
            self.current_session = RecordingSession(session_id)
            
            # Start audio recording
            if self.audio_recorder.start_recording():
                self.is_recording = True
                self.current_session.start_recording()
                
                # Reset VAD state
                if self.vad:
                    self.vad.is_speaking = False
                    self.vad.last_voice_time = 0
                
                # Call callback
                if self.on_recording_start:
                    self.on_recording_start(self.current_session)
                
                return self.current_session
            else:
                logger.error("Failed to start audio recording")
                return None
                
        except Exception as e:
            logger.error(f"Error starting recording: {e}")
            return None
    
    def stop_recording(self) -> bool:
        """Stop the current recording session."""
        if not self.is_recording or not self.current_session:
            logger.warning("No recording in progress")
            return False
        
        try:
            # Stop audio recording
            audio_data = self.audio_recorder.stop_recording()
            self.is_recording = False
            
            if audio_data is not None and len(audio_data) > 0:
                # Check minimum duration
                duration = len(audio_data) / self.config.sample_rate
                if duration < self.config.min_recording_duration:
                    logger.info(f"Recording too short ({duration:.2f}s), discarding")
                    self.current_session = None
                    return False
                
                # Stop the session with audio data
                self.current_session.stop_recording(audio_data)
                
                # Save audio file if enabled
                if self.config.save_audio_files:
                    self._save_audio_file(self.current_session)
                
                # Queue for transcription
                self.processing_queue.put(('transcribe', self.current_session))
                
                # Call callback
                if self.on_recording_stop:
                    self.on_recording_stop(self.current_session)
                
                return True
            else:
                logger.warning("No audio data recorded")
                self.current_session = None
                return False
                
        except Exception as e:
            logger.error(f"Error stopping recording: {e}")
            self.is_recording = False
            self.current_session = None
            return False
    
    def toggle_recording(self) -> bool:
        """Toggle recording on/off."""
        if self.is_recording:
            return self.stop_recording()
        else:
            session = self.start_recording()
            return session is not None
    
    def _on_audio_chunk(self, audio_chunk):
        """Handle audio chunk during recording."""
        if not self.is_recording or not self.current_session:
            return
        
        try:
            # Voice activity detection
            if self.vad:
                voice_detected = self.vad.process_audio(audio_chunk, self.config.sample_rate)
                
                current_time = time.time()
                
                if voice_detected:
                    if not self.current_session.voice_activity_detected:
                        self.current_session.voice_activity_detected = True
                        logger.debug("Voice activity detected")
                        
                        if self.on_voice_activity:
                            self.on_voice_activity(True)
                    
                    self.current_session.last_voice_time = current_time
                    self.current_session.silence_duration = 0.0
                
                else:
                    # Calculate silence duration
                    if self.current_session.last_voice_time:
                        self.current_session.silence_duration = current_time - self.current_session.last_voice_time
                        
                        # Auto-stop if silence threshold reached
                        if (self.config.auto_stop_enabled and 
                            self.current_session.voice_activity_detected and
                            self.current_session.silence_duration >= self.config.silence_timeout):
                            
                            logger.info(f"Auto-stopping recording after {self.current_session.silence_duration:.1f}s of silence")
                            self.stop_recording()
                            return
            
            # Check maximum duration
            if self.current_session:
                elapsed = (datetime.now() - self.current_session.start_time).total_seconds()
                if elapsed >= self.config.max_recording_duration:
                    logger.info(f"Maximum recording duration reached ({elapsed:.1f}s)")
                    self.stop_recording()
            
        except Exception as e:
            logger.error(f"Error processing audio chunk: {e}")
    
    def _save_audio_file(self, session: RecordingSession):
        """Save audio data to file."""
        try:
            timestamp = session.start_time.strftime("%Y%m%d_%H%M%S")
            filename = f"recording_{timestamp}_{session.session_id}.wav"
            file_path = self.audio_files_path / filename
            
            if self.audio_recorder.save_audio(session.audio_data, str(file_path)):
                session.audio_file_path = str(file_path)
                logger.info(f"Audio saved to: {file_path}")
            
        except Exception as e:
            logger.error(f"Error saving audio file: {e}")
    
    def _processing_worker(self):
        """Background worker for processing tasks."""
        while not self.stop_event.is_set():
            try:
                # Get task with timeout
                task_type, data = self.processing_queue.get(timeout=1.0)
                
                if task_type == 'transcribe':
                    self._process_transcription(data)
                
                self.processing_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in processing worker: {e}")
    
    def _process_transcription(self, session: RecordingSession):
        """Process transcription for a session."""
        try:
            logger.info(f"Starting transcription for session {session.session_id}")
            
            if self.transcription_queue:
                # Use queue for transcription
                self.transcription_queue.add_task(
                    session.session_id,
                    session.audio_data,
                    sample_rate=self.config.sample_rate
                )
            else:
                # Direct transcription
                result = self.transcriber.transcribe_array(
                    session.audio_data,
                    sample_rate=self.config.sample_rate
                )
                
                self._handle_transcription_result(session, result)
            
        except Exception as e:
            logger.error(f"Error processing transcription for session {session.session_id}: {e}")
            session.status = "failed"
            session.error_message = str(e)
            
            if self.on_transcription_error:
                self.on_transcription_error(session, str(e))
    
    def _handle_transcription_result(self, session: RecordingSession, result: Dict):
        """Handle transcription result."""
        try:
            session.set_transcription_result(result)
            
            if 'error' not in result and self.config.auto_save:
                # Save to database
                transcription_id = self.database.add_transcription(
                    text=result['text'],
                    duration=session.duration,
                    audio_file_path=session.audio_file_path,
                    confidence=result.get('confidence'),
                    notes=f"Session: {session.session_id}, Model: {result.get('model_name', 'unknown')}"
                )
                
                session.set_transcription_id(transcription_id)
                logger.info(f"Transcription saved to database with ID: {transcription_id}")
            
            # Call callback
            if 'error' not in result and self.on_transcription_complete:
                self.on_transcription_complete(session)
            elif 'error' in result and self.on_transcription_error:
                self.on_transcription_error(session, result['error'])
            
        except Exception as e:
            logger.error(f"Error handling transcription result: {e}")
            session.status = "failed"
            session.error_message = str(e)
            
            if self.on_transcription_error:
                self.on_transcription_error(session, str(e))
    
    def _on_transcription_complete(self, text: str, result: Dict):
        """Handle direct transcription completion."""
        # This is called by the transcriber directly
        pass
    
    def _on_transcription_error(self, error: str):
        """Handle direct transcription error."""
        # This is called by the transcriber directly
        logger.error(f"Transcription error: {error}")
    
    def _on_queue_transcription_complete(self, task_id: str, result: Dict):
        """Handle queue transcription completion."""
        # Find the session by task_id (which is session_id)
        if hasattr(self, '_pending_sessions'):
            session = self._pending_sessions.get(task_id)
            if session:
                self._handle_transcription_result(session, result)
                del self._pending_sessions[task_id]
    
    def _on_hotkey_recording_start(self):
        """Handle global hotkey recording start."""
        if not self.is_recording:
            logger.info("Global hotkey: Starting recording")
            self.start_recording()
    
    def _on_hotkey_recording_stop(self):
        """Handle global hotkey recording stop."""
        if self.is_recording:
            logger.info("Global hotkey: Stopping recording")
            self.stop_recording()
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status information."""
        status = {
            'is_initialized': self.is_initialized,
            'is_recording': self.is_recording,
            'current_session_id': self.current_session.session_id if self.current_session else None,
            'config': {
                'whisper_model': self.config.whisper_model,
                'sample_rate': self.config.sample_rate,
                'auto_stop_enabled': self.config.auto_stop_enabled,
                'vad_enabled': self.config.vad_enabled,
                'save_audio_files': self.config.save_audio_files
            }
        }
        
        # Add current session info
        if self.current_session:
            elapsed = (datetime.now() - self.current_session.start_time).total_seconds()
            status['current_session'] = {
                'id': self.current_session.session_id,
                'status': self.current_session.status,
                'elapsed_time': elapsed,
                'voice_activity_detected': self.current_session.voice_activity_detected,
                'silence_duration': self.current_session.silence_duration
            }
        
        # Add component status
        if self.transcriber:
            status['transcriber'] = self.transcriber.get_model_info()
        
        if self.audio_recorder:
            status['audio_recorder'] = {
                'sample_rate': self.audio_recorder.sample_rate,
                'channels': self.audio_recorder.channels,
                'device': self.audio_recorder.device
            }
        
        return status
    
    def get_available_audio_devices(self):
        """Get available audio input devices."""
        if self.audio_recorder:
            return self.audio_recorder.get_available_devices()
        return []
    
    def set_audio_device(self, device_id: Optional[int]):
        """Set audio input device."""
        if self.audio_recorder:
            self.audio_recorder.set_device(device_id)
            self.config.audio_device = device_id
    
    def set_whisper_model(self, model_name: str) -> bool:
        """Change Whisper model."""
        if self.transcriber:
            success = self.transcriber.set_model(model_name)
            if success:
                self.config.whisper_model = model_name
            return success
        return False
    
    def test_components(self) -> Dict[str, bool]:
        """Test all components."""
        results = {}
        
        # Test audio recorder
        try:
            if self.audio_recorder:
                test_result = self.audio_recorder.test_audio_input(duration=1.0)
                results['audio_recorder'] = test_result['success']
            else:
                results['audio_recorder'] = False
        except Exception as e:
            logger.error(f"Audio recorder test failed: {e}")
            results['audio_recorder'] = False
        
        # Test transcriber
        try:
            if self.transcriber:
                results['transcriber'] = self.transcriber.is_ready()
            else:
                results['transcriber'] = False
        except Exception as e:
            logger.error(f"Transcriber test failed: {e}")
            results['transcriber'] = False
        
        # Test database
        try:
            if self.database:
                # Try to get statistics
                stats = self.database.get_statistics()
                results['database'] = isinstance(stats, dict)
            else:
                results['database'] = False
        except Exception as e:
            logger.error(f"Database test failed: {e}")
            results['database'] = False
        
        # Test keyboard handler
        try:
            if self.keyboard_handler:
                results['keyboard_handler'] = self.keyboard_handler.is_listening
            else:
                results['keyboard_handler'] = self.config.enable_global_shortcuts is False
        except Exception as e:
            logger.error(f"Keyboard handler test failed: {e}")
            results['keyboard_handler'] = False
        
        return results


def create_speech_recorder(config_file: Optional[str] = None) -> SpeechRecorder:
    """
    Create and return a configured SpeechRecorder instance.
    
    Args:
        config_file: Optional path to configuration file
        
    Returns:
        Configured SpeechRecorder instance
    """
    if config_file:
        config = SpeechRecorderConfig.from_file(config_file)
    else:
        config = SpeechRecorderConfig()
    
    return SpeechRecorder(config)


if __name__ == "__main__":
    # Test the speech recorder
    print("Testing SpeechRecorder...")
    
    # Setup logging
    logging.basicConfig(level=logging.INFO,
                       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Create and initialize recorder
    recorder = SpeechRecorder()
    
    if not recorder.initialize():
        print("Failed to initialize SpeechRecorder")
        exit(1)
    
    print("SpeechRecorder initialized successfully")
    
    # Test components
    test_results = recorder.test_components()
    print(f"Component test results: {test_results}")
    
    # Get status
    status = recorder.get_status()
    print(f"Status: {json.dumps(status, indent=2, default=str)}")
    
    try:
        # Interactive test
        print("\nInteractive test:")
        print("Press Enter to start recording, Enter again to stop, 'q' to quit")
        
        while True:
            user_input = input("> ").strip().lower()
            
            if user_input == 'q':
                break
            elif user_input == '':
                if recorder.is_recording:
                    print("Stopping recording...")
                    recorder.stop_recording()
                else:
                    print("Starting recording...")
                    session = recorder.start_recording()
                    if session:
                        print(f"Recording session: {session.session_id}")
                    else:
                        print("Failed to start recording")
            elif user_input == 'status':
                status = recorder.get_status()
                print(f"Status: {json.dumps(status, indent=2, default=str)}")
            else:
                print("Commands: Enter (toggle recording), 'status', 'q' (quit)")
    
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    
    finally:
        print("Shutting down...")
        recorder.shutdown()
        print("SpeechRecorder test completed.")