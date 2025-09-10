"""
Speech-to-text module using OpenAI Whisper for offline transcription.
Provides high-quality speech recognition with multiple model sizes.
"""

import whisper
import numpy as np
import logging
import threading
import queue
from pathlib import Path
from typing import Optional, Dict, List, Callable, Union
import tempfile
import time
import torch

logger = logging.getLogger(__name__)


class WhisperTranscriber:
    """Handles speech-to-text transcription using OpenAI Whisper."""
    
    def __init__(
        self,
        model_name: str = "base",
        device: Optional[str] = None,
        language: Optional[str] = None,
        task: str = "transcribe"
    ):
        """
        Initialize the Whisper transcriber.
        
        Args:
            model_name: Whisper model to use (tiny, base, small, medium, large)
            device: Device to run on (cpu, cuda, auto)
            language: Language code for transcription (None for auto-detect)
            task: Task type ('transcribe' or 'translate')
        """
        self.model_name = model_name
        self.device = device or self._get_best_device()
        self.language = language
        self.task = task
        
        self.model = None
        self.is_loading = False
        self.load_error = None
        
        # Callbacks
        self.on_transcription_start: Optional[Callable] = None
        self.on_transcription_complete: Optional[Callable[[str, Dict], None]] = None
        self.on_transcription_error: Optional[Callable[[str], None]] = None
        
        # Load model in background
        self._load_model_async()
    
    def _get_best_device(self) -> str:
        """Determine the best device for Whisper inference."""
        if torch.cuda.is_available():
            return "cuda"
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return "mps"  # Apple Silicon GPU
        else:
            return "cpu"
    
    def _load_model_async(self):
        """Load the Whisper model asynchronously."""
        def load_model():
            try:
                self.is_loading = True
                logger.info(f"Loading Whisper model '{self.model_name}' on device '{self.device}'...")
                
                self.model = whisper.load_model(
                    self.model_name,
                    device=self.device
                )
                
                self.is_loading = False
                logger.info(f"Whisper model '{self.model_name}' loaded successfully")
                
            except Exception as e:
                self.is_loading = False
                self.load_error = str(e)
                logger.error(f"Error loading Whisper model: {e}")
        
        # Start loading in background thread
        loading_thread = threading.Thread(target=load_model)
        loading_thread.daemon = True
        loading_thread.start()
    
    def is_ready(self) -> bool:
        """
        Check if the model is ready for transcription.
        
        Returns:
            True if model is loaded and ready, False otherwise
        """
        return self.model is not None and not self.is_loading
    
    def wait_for_model(self, timeout: float = 60.0) -> bool:
        """
        Wait for the model to load.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if model loaded successfully, False if timeout or error
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.is_ready():
                return True
            
            if self.load_error:
                logger.error(f"Model loading failed: {self.load_error}")
                return False
            
            time.sleep(0.1)
        
        logger.error(f"Model loading timeout after {timeout} seconds")
        return False
    
    def transcribe_audio(
        self,
        audio_data: Union[np.ndarray, str, Path],
        language: Optional[str] = None,
        initial_prompt: Optional[str] = None,
        word_timestamps: bool = False,
        temperature: float = 0.0
    ) -> Dict:
        """
        Transcribe audio data or file.
        
        Args:
            audio_data: Audio data (numpy array) or path to audio file
            language: Language code (overrides instance default)
            initial_prompt: Initial prompt to guide transcription
            word_timestamps: Whether to include word-level timestamps
            temperature: Temperature for generation (0.0 for deterministic)
            
        Returns:
            Dictionary containing transcription results
        """
        if not self.is_ready():
            if not self.wait_for_model():
                error_msg = "Whisper model not ready for transcription"
                if self.on_transcription_error:
                    self.on_transcription_error(error_msg)
                return {'error': error_msg}
        
        try:
            # Call start callback
            if self.on_transcription_start:
                self.on_transcription_start()
            
            # Prepare transcription options
            options = {
                'language': language or self.language,
                'task': self.task,
                'temperature': temperature,
                'word_timestamps': word_timestamps
            }
            
            if initial_prompt:
                options['initial_prompt'] = initial_prompt
            
            # Remove None values
            options = {k: v for k, v in options.items() if v is not None}
            
            logger.info(f"Starting transcription with options: {options}")
            start_time = time.time()
            
            # Perform transcription
            if isinstance(audio_data, np.ndarray):
                # Transcribe from numpy array
                result = self.model.transcribe(audio_data, **options)
            else:
                # Transcribe from file path
                result = self.model.transcribe(str(audio_data), **options)
            
            transcription_time = time.time() - start_time
            
            # Add metadata
            result['transcription_time'] = transcription_time
            result['model_name'] = self.model_name
            result['device'] = self.device
            result['options'] = options
            
            # Calculate confidence score (average of segment probabilities)
            if 'segments' in result and result['segments']:
                confidences = [seg.get('avg_logprob', 0) for seg in result['segments']]
                if confidences:
                    # Convert log probabilities to confidence scores
                    result['confidence'] = float(np.exp(np.mean(confidences)))
                else:
                    result['confidence'] = 0.5  # Default confidence
            else:
                result['confidence'] = 0.5
            
            logger.info(f"Transcription completed in {transcription_time:.2f}s")
            logger.info(f"Transcribed text: {result['text'][:100]}...")
            
            # Call completion callback
            if self.on_transcription_complete:
                self.on_transcription_complete(result['text'], result)
            
            return result
            
        except Exception as e:
            error_msg = f"Error during transcription: {e}"
            logger.error(error_msg)
            
            if self.on_transcription_error:
                self.on_transcription_error(error_msg)
            
            return {'error': error_msg}
    
    def transcribe_file(self, file_path: Union[str, Path]) -> Dict:
        """
        Transcribe audio from file.
        
        Args:
            file_path: Path to audio file
            
        Returns:
            Dictionary containing transcription results
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            error_msg = f"Audio file not found: {file_path}"
            logger.error(error_msg)
            return {'error': error_msg}
        
        logger.info(f"Transcribing file: {file_path}")
        return self.transcribe_audio(file_path)
    
    def transcribe_array(
        self,
        audio_array: np.ndarray,
        sample_rate: int = 16000
    ) -> Dict:
        """
        Transcribe audio from numpy array.
        
        Args:
            audio_array: Audio data as numpy array
            sample_rate: Sample rate of audio data
            
        Returns:
            Dictionary containing transcription results
        """
        try:
            # Whisper expects 16kHz mono audio
            if sample_rate != 16000:
                logger.warning(f"Audio sample rate is {sample_rate}Hz, but Whisper expects 16kHz")
                # You might want to resample here using librosa
            
            # Ensure audio is in correct format
            if audio_array.ndim > 1:
                # Convert to mono if stereo
                audio_array = np.mean(audio_array, axis=1)
            
            # Normalize audio to [-1, 1] range
            if audio_array.dtype != np.float32:
                audio_array = audio_array.astype(np.float32)
            
            max_val = np.max(np.abs(audio_array))
            if max_val > 0:
                audio_array = audio_array / max_val
            
            logger.info(f"Transcribing audio array: {len(audio_array)} samples at {sample_rate}Hz")
            return self.transcribe_audio(audio_array)
            
        except Exception as e:
            error_msg = f"Error processing audio array: {e}"
            logger.error(error_msg)
            return {'error': error_msg}
    
    def get_available_models(self) -> List[str]:
        """
        Get list of available Whisper models.
        
        Returns:
            List of model names
        """
        return ["tiny", "base", "small", "medium", "large"]
    
    def get_supported_languages(self) -> List[str]:
        """
        Get list of supported languages.
        
        Returns:
            List of language codes
        """
        if not self.is_ready():
            # Return common languages if model not loaded
            return ["en", "es", "fr", "de", "it", "pt", "ru", "ja", "ko", "zh"]
        
        try:
            # Get languages from the model
            return list(whisper.tokenizer.LANGUAGES.keys())
        except:
            return ["en", "es", "fr", "de", "it", "pt", "ru", "ja", "ko", "zh"]
    
    def detect_language(self, audio_data: Union[np.ndarray, str, Path]) -> Dict:
        """
        Detect the language of audio without full transcription.
        
        Args:
            audio_data: Audio data or file path
            
        Returns:
            Dictionary with detected language and confidence
        """
        if not self.is_ready():
            return {'error': 'Model not ready'}
        
        try:
            # Load audio if it's a file path
            if isinstance(audio_data, (str, Path)):
                audio = whisper.load_audio(str(audio_data))
            else:
                audio = audio_data
            
            # Detect language
            audio = whisper.pad_or_trim(audio)
            mel = whisper.log_mel_spectrogram(audio).to(self.model.device)
            _, probs = self.model.detect_language(mel)
            
            # Get top languages
            top_langs = sorted(probs.items(), key=lambda x: x[1], reverse=True)[:5]
            
            return {
                'detected_language': top_langs[0][0],
                'confidence': float(top_langs[0][1]),
                'top_languages': [(lang, float(prob)) for lang, prob in top_langs]
            }
            
        except Exception as e:
            error_msg = f"Error detecting language: {e}"
            logger.error(error_msg)
            return {'error': error_msg}
    
    def set_model(self, model_name: str) -> bool:
        """
        Change the Whisper model.
        
        Args:
            model_name: New model name to load
            
        Returns:
            True if model changed successfully, False otherwise
        """
        if model_name == self.model_name and self.is_ready():
            return True
        
        try:
            logger.info(f"Changing Whisper model from '{self.model_name}' to '{model_name}'")
            self.model_name = model_name
            self.model = None
            self.load_error = None
            
            # Load new model
            self._load_model_async()
            return True
            
        except Exception as e:
            logger.error(f"Error changing model: {e}")
            return False
    
    def get_model_info(self) -> Dict:
        """
        Get information about the current model.
        
        Returns:
            Dictionary with model information
        """
        return {
            'model_name': self.model_name,
            'device': self.device,
            'language': self.language,
            'task': self.task,
            'is_ready': self.is_ready(),
            'is_loading': self.is_loading,
            'load_error': self.load_error
        }


class TranscriptionQueue:
    """Manages a queue of transcription tasks for batch processing."""
    
    def __init__(self, transcriber: WhisperTranscriber, max_workers: int = 1):
        """
        Initialize transcription queue.
        
        Args:
            transcriber: WhisperTranscriber instance
            max_workers: Maximum number of worker threads
        """
        self.transcriber = transcriber
        self.max_workers = max_workers
        self.task_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.workers = []
        self.is_running = False
        
        self.on_task_complete: Optional[Callable[[str, Dict], None]] = None
    
    def start(self):
        """Start the queue workers."""
        if self.is_running:
            return
        
        self.is_running = True
        
        for i in range(self.max_workers):
            worker = threading.Thread(target=self._worker)
            worker.daemon = True
            worker.start()
            self.workers.append(worker)
        
        logger.info(f"Started {self.max_workers} transcription workers")
    
    def stop(self):
        """Stop the queue workers."""
        self.is_running = False
        
        # Add sentinel values to wake up workers
        for _ in range(self.max_workers):
            self.task_queue.put(None)
        
        # Wait for workers to finish
        for worker in self.workers:
            worker.join(timeout=5.0)
        
        self.workers = []
        logger.info("Stopped transcription workers")
    
    def add_task(self, task_id: str, audio_data: Union[np.ndarray, str, Path], **kwargs):
        """
        Add a transcription task to the queue.
        
        Args:
            task_id: Unique identifier for the task
            audio_data: Audio data to transcribe
            **kwargs: Additional arguments for transcription
        """
        task = {
            'id': task_id,
            'audio_data': audio_data,
            'kwargs': kwargs,
            'timestamp': time.time()
        }
        
        self.task_queue.put(task)
        logger.info(f"Added transcription task: {task_id}")
    
    def _worker(self):
        """Worker thread for processing transcription tasks."""
        while self.is_running:
            try:
                task = self.task_queue.get(timeout=1.0)
                
                if task is None:  # Sentinel value to stop worker
                    break
                
                # Process transcription
                logger.info(f"Processing transcription task: {task['id']}")
                result = self.transcriber.transcribe_audio(
                    task['audio_data'],
                    **task['kwargs']
                )
                
                # Add task info to result
                result['task_id'] = task['id']
                result['task_timestamp'] = task['timestamp']
                
                # Put result in result queue
                self.result_queue.put(result)
                
                # Call completion callback
                if self.on_task_complete and 'text' in result:
                    self.on_task_complete(task['id'], result)
                
                self.task_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in transcription worker: {e}")
    
    def get_results(self) -> List[Dict]:
        """
        Get all available results from the queue.
        
        Returns:
            List of transcription results
        """
        results = []
        
        while not self.result_queue.empty():
            try:
                result = self.result_queue.get_nowait()
                results.append(result)
                self.result_queue.task_done()
            except queue.Empty:
                break
        
        return results


def create_transcriber(
    model_name: str = "base",
    device: Optional[str] = None,
    language: Optional[str] = None
) -> WhisperTranscriber:
    """
    Create and return a configured WhisperTranscriber instance.
    
    Args:
        model_name: Whisper model to use
        device: Device to run on
        language: Language for transcription
        
    Returns:
        Configured WhisperTranscriber instance
    """
    return WhisperTranscriber(
        model_name=model_name,
        device=device,
        language=language
    )


if __name__ == "__main__":
    # Test the transcriber
    print("Testing Whisper Transcriber...")
    
    transcriber = WhisperTranscriber(model_name="base")
    
    print(f"Available models: {transcriber.get_available_models()}")
    print(f"Supported languages: {transcriber.get_supported_languages()[:10]}...")
    
    # Wait for model to load
    print("Waiting for model to load...")
    if transcriber.wait_for_model():
        print("Model loaded successfully!")
        print(f"Model info: {transcriber.get_model_info()}")
        
        # Test with dummy audio data
        print("\nTesting with dummy audio data...")
        dummy_audio = np.random.randn(16000).astype(np.float32) * 0.1  # 1 second of noise
        result = transcriber.transcribe_array(dummy_audio)
        
        if 'error' not in result:
            print(f"Transcription: {result['text']}")
            print(f"Confidence: {result.get('confidence', 'N/A')}")
            print(f"Time taken: {result.get('transcription_time', 'N/A'):.2f}s")
        else:
            print(f"Error: {result['error']}")
    else:
        print("Failed to load model")
    
    print("Transcriber test completed.")