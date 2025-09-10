"""
Audio recording module for speech-to-text application.
Handles audio recording using sounddevice with cross-platform support.
"""

import sounddevice as sd
import numpy as np
import threading
import queue
import time
import logging
from pathlib import Path
from typing import Optional, Callable, List
import soundfile as sf
from datetime import datetime

logger = logging.getLogger(__name__)


class AudioRecorder:
    """Handles audio recording operations with real-time processing capabilities."""
    
    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        dtype: str = 'float32',
        device: Optional[str] = None,
        chunk_size: int = 1024
    ):
        """
        Initialize the audio recorder.
        
        Args:
            sample_rate: Sample rate for recording (Hz)
            channels: Number of audio channels (1 for mono, 2 for stereo)
            dtype: Data type for audio samples
            device: Audio device to use (None for default)
            chunk_size: Size of audio chunks for processing
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.dtype = dtype
        self.device = device
        self.chunk_size = chunk_size
        
        self.is_recording = False
        self.audio_data = []
        self.recording_thread = None
        self.audio_queue = queue.Queue()
        
        # Callbacks
        self.on_recording_start: Optional[Callable] = None
        self.on_recording_stop: Optional[Callable] = None
        self.on_audio_chunk: Optional[Callable[[np.ndarray], None]] = None
        
        # Initialize audio system
        self._initialize_audio()
    
    def _initialize_audio(self):
        """Initialize and configure the audio system."""
        try:
            # List available devices for debugging
            devices = sd.query_devices()
            logger.info(f"Available audio devices: {len(devices)}")
            
            # Set default device if none specified
            if self.device is None:
                default_device = sd.query_devices(kind='input')
                logger.info(f"Using default input device: {default_device['name']}")
            else:
                logger.info(f"Using specified device: {self.device}")
            
            # Test audio configuration
            sd.check_input_settings(
                device=self.device,
                channels=self.channels,
                samplerate=self.sample_rate,
                dtype=self.dtype
            )
            
        except Exception as e:
            logger.error(f"Error initializing audio: {e}")
            raise
    
    def get_available_devices(self) -> List[dict]:
        """
        Get list of available audio input devices.
        
        Returns:
            List of device information dictionaries
        """
        devices = sd.query_devices()
        input_devices = []
        
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                input_devices.append({
                    'id': i,
                    'name': device['name'],
                    'channels': device['max_input_channels'],
                    'sample_rate': device['default_samplerate']
                })
        
        return input_devices
    
    def set_device(self, device_id: Optional[int] = None):
        """
        Set the audio input device.
        
        Args:
            device_id: ID of the device to use (None for default)
        """
        self.device = device_id
        logger.info(f"Audio device set to: {device_id}")
    
    def _audio_callback(self, indata, frames, time, status):
        """
        Callback function for audio stream.
        
        Args:
            indata: Input audio data
            frames: Number of frames
            time: Time information
            status: Stream status
        """
        if status:
            logger.warning(f"Audio callback status: {status}")
        
        # Put audio data in queue for processing
        self.audio_queue.put(indata.copy())
        
        # Call chunk callback if available
        if self.on_audio_chunk:
            try:
                self.on_audio_chunk(indata.copy())
            except Exception as e:
                logger.error(f"Error in audio chunk callback: {e}")
    
    def start_recording(self) -> bool:
        """
        Start audio recording.
        
        Returns:
            True if recording started successfully, False otherwise
        """
        if self.is_recording:
            logger.warning("Recording is already in progress")
            return False
        
        try:
            # Clear previous data
            self.audio_data = []
            
            # Start recording stream
            self.stream = sd.InputStream(
                device=self.device,
                channels=self.channels,
                samplerate=self.sample_rate,
                dtype=self.dtype,
                callback=self._audio_callback,
                blocksize=self.chunk_size
            )
            
            self.stream.start()
            self.is_recording = True
            
            # Start processing thread
            self.recording_thread = threading.Thread(target=self._process_audio)
            self.recording_thread.daemon = True
            self.recording_thread.start()
            
            # Call start callback
            if self.on_recording_start:
                self.on_recording_start()
            
            logger.info("Audio recording started")
            return True
            
        except Exception as e:
            logger.error(f"Error starting recording: {e}")
            return False
    
    def stop_recording(self) -> Optional[np.ndarray]:
        """
        Stop audio recording and return recorded data.
        
        Returns:
            Numpy array containing recorded audio data, or None if no data
        """
        if not self.is_recording:
            logger.warning("No recording in progress")
            return None
        
        try:
            # Stop recording
            self.is_recording = False
            
            if hasattr(self, 'stream') and self.stream:
                self.stream.stop()
                self.stream.close()
            
            # Wait for processing thread to finish
            if self.recording_thread and self.recording_thread.is_alive():
                self.recording_thread.join(timeout=2.0)
            
            # Process remaining audio data
            self._process_remaining_audio()
            
            # Combine all audio data
            if self.audio_data:
                combined_audio = np.concatenate(self.audio_data, axis=0)
                
                # Call stop callback
                if self.on_recording_stop:
                    self.on_recording_stop()
                
                logger.info(f"Recording stopped. Duration: {len(combined_audio) / self.sample_rate:.2f} seconds")
                return combined_audio
            else:
                logger.warning("No audio data recorded")
                return None
                
        except Exception as e:
            logger.error(f"Error stopping recording: {e}")
            return None
    
    def _process_audio(self):
        """Process audio data from the queue."""
        while self.is_recording:
            try:
                # Get audio data with timeout
                audio_chunk = self.audio_queue.get(timeout=0.1)
                self.audio_data.append(audio_chunk)
                self.audio_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error processing audio: {e}")
                break
    
    def _process_remaining_audio(self):
        """Process any remaining audio data in the queue."""
        while not self.audio_queue.empty():
            try:
                audio_chunk = self.audio_queue.get_nowait()
                self.audio_data.append(audio_chunk)
                self.audio_queue.task_done()
            except queue.Empty:
                break
            except Exception as e:
                logger.error(f"Error processing remaining audio: {e}")
                break
    
    def save_audio(self, audio_data: np.ndarray, filename: str) -> bool:
        """
        Save audio data to file.
        
        Args:
            audio_data: Audio data to save
            filename: Output filename
            
        Returns:
            True if save was successful, False otherwise
        """
        try:
            # Ensure the directory exists
            file_path = Path(filename)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save audio file
            sf.write(
                filename,
                audio_data,
                self.sample_rate,
                format='WAV',
                subtype='PCM_16'
            )
            
            logger.info(f"Audio saved to: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving audio to {filename}: {e}")
            return False
    
    def record_for_duration(self, duration: float, save_path: Optional[str] = None) -> Optional[np.ndarray]:
        """
        Record audio for a specific duration.
        
        Args:
            duration: Duration to record in seconds
            save_path: Optional path to save the recording
            
        Returns:
            Recorded audio data or None if failed
        """
        try:
            logger.info(f"Recording for {duration} seconds...")
            
            # Start recording
            if not self.start_recording():
                return None
            
            # Wait for specified duration
            time.sleep(duration)
            
            # Stop recording
            audio_data = self.stop_recording()
            
            # Save if path provided
            if audio_data is not None and save_path:
                self.save_audio(audio_data, save_path)
            
            return audio_data
            
        except Exception as e:
            logger.error(f"Error in timed recording: {e}")
            self.stop_recording()  # Ensure recording is stopped
            return None
    
    def get_audio_level(self, audio_chunk: np.ndarray) -> float:
        """
        Calculate audio level (RMS) for the given chunk.
        
        Args:
            audio_chunk: Audio data chunk
            
        Returns:
            RMS audio level (0.0 to 1.0)
        """
        try:
            rms = np.sqrt(np.mean(audio_chunk ** 2))
            return min(rms, 1.0)  # Clamp to 1.0
        except Exception as e:
            logger.error(f"Error calculating audio level: {e}")
            return 0.0
    
    def is_silent(self, audio_chunk: np.ndarray, threshold: float = 0.01) -> bool:
        """
        Check if audio chunk is silent.
        
        Args:
            audio_chunk: Audio data chunk
            threshold: Silence threshold (0.0 to 1.0)
            
        Returns:
            True if audio is below threshold, False otherwise
        """
        level = self.get_audio_level(audio_chunk)
        return level < threshold
    
    def get_recording_duration(self) -> float:
        """
        Get current recording duration in seconds.
        
        Returns:
            Duration in seconds
        """
        if not self.audio_data:
            return 0.0
        
        total_samples = sum(len(chunk) for chunk in self.audio_data)
        return total_samples / self.sample_rate
    
    def test_audio_input(self, duration: float = 2.0) -> dict:
        """
        Test audio input and return information about the recording.
        
        Args:
            duration: Test duration in seconds
            
        Returns:
            Dictionary with test results
        """
        logger.info(f"Testing audio input for {duration} seconds...")
        
        try:
            audio_data = self.record_for_duration(duration)
            
            if audio_data is None:
                return {
                    'success': False,
                    'error': 'Failed to record audio',
                    'duration': 0,
                    'max_level': 0,
                    'avg_level': 0
                }
            
            # Calculate statistics
            max_level = np.max(np.abs(audio_data))
            avg_level = np.mean(np.abs(audio_data))
            actual_duration = len(audio_data) / self.sample_rate
            
            result = {
                'success': True,
                'duration': actual_duration,
                'max_level': float(max_level),
                'avg_level': float(avg_level),
                'sample_rate': self.sample_rate,
                'channels': self.channels,
                'samples': len(audio_data)
            }
            
            logger.info(f"Audio test completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error in audio test: {e}")
            return {
                'success': False,
                'error': str(e),
                'duration': 0,
                'max_level': 0,
                'avg_level': 0
            }


class VoiceActivityDetector:
    """Simple voice activity detection using audio level thresholds."""
    
    def __init__(self, threshold: float = 0.02, min_duration: float = 0.1):
        """
        Initialize voice activity detector.
        
        Args:
            threshold: Audio level threshold for voice detection
            min_duration: Minimum duration for voice activity
        """
        self.threshold = threshold
        self.min_duration = min_duration
        self.is_speaking = False
        self.last_voice_time = 0
    
    def process_audio(self, audio_chunk: np.ndarray, sample_rate: int) -> bool:
        """
        Process audio chunk and detect voice activity.
        
        Args:
            audio_chunk: Audio data chunk
            sample_rate: Sample rate of audio
            
        Returns:
            True if voice activity detected, False otherwise
        """
        # Calculate audio level
        level = np.sqrt(np.mean(audio_chunk ** 2))
        
        current_time = time.time()
        
        if level > self.threshold:
            self.last_voice_time = current_time
            if not self.is_speaking:
                self.is_speaking = True
                return True
        else:
            # Check if we should stop detecting voice
            if self.is_speaking and (current_time - self.last_voice_time) > self.min_duration:
                self.is_speaking = False
        
        return self.is_speaking


def create_recorder(
    sample_rate: int = 16000,
    device: Optional[str] = None
) -> AudioRecorder:
    """
    Create and return a configured AudioRecorder instance.
    
    Args:
        sample_rate: Sample rate for recording
        device: Audio device to use
        
    Returns:
        Configured AudioRecorder instance
    """
    return AudioRecorder(sample_rate=sample_rate, device=device)


if __name__ == "__main__":
    # Test the audio recorder
    print("Testing Audio Recorder...")
    
    recorder = AudioRecorder()
    
    # List available devices
    devices = recorder.get_available_devices()
    print(f"Available input devices: {len(devices)}")
    for device in devices:
        print(f"  {device['id']}: {device['name']}")
    
    # Test audio input
    test_result = recorder.test_audio_input(duration=3.0)
    print(f"Audio test result: {test_result}")
    
    # Test manual recording
    print("\nTesting manual recording (press Enter to start, Enter again to stop)...")
    input("Press Enter to start recording...")
    
    recorder.start_recording()
    input("Recording... Press Enter to stop...")
    
    audio_data = recorder.stop_recording()
    if audio_data is not None:
        # Save test recording
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"test_recording_{timestamp}.wav"
        recorder.save_audio(audio_data, filename)
        print(f"Test recording saved as: {filename}")
    
    print("Audio recorder test completed.")