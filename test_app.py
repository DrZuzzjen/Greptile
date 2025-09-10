#!/usr/bin/env python3
"""
Comprehensive test suite for Speech-to-Text Transcriber application.
Tests all components and integration scenarios.
"""

import unittest
import tempfile
import os
import sys
import time
import threading
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import TranscriptionDatabase
from audio_recorder import AudioRecorder, VoiceActivityDetector
from speech_to_text import WhisperTranscriber
from keyboard_handler import GlobalKeyboardHandler
from speech_recorder import SpeechRecorder, SpeechRecorderConfig


class TestDatabase(unittest.TestCase):
    """Test database functionality."""
    
    def setUp(self):
        """Set up test database."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db = TranscriptionDatabase(self.temp_db.name)
    
    def tearDown(self):
        """Clean up test database."""
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def test_database_initialization(self):
        """Test database initialization."""
        self.assertTrue(os.path.exists(self.temp_db.name))
        
        # Test table creation
        stats = self.db.get_statistics()
        self.assertEqual(stats['total_transcriptions'], 0)
    
    def test_add_transcription(self):
        """Test adding transcriptions."""
        trans_id = self.db.add_transcription(
            text="Test transcription",
            duration=5.0,
            confidence=0.95,
            tags=["test", "unit"],
            notes="Test note"
        )
        
        self.assertIsInstance(trans_id, int)
        self.assertGreater(trans_id, 0)
        
        # Verify transcription was added
        transcription = self.db.get_transcription(trans_id)
        self.assertIsNotNone(transcription)
        self.assertEqual(transcription['text'], "Test transcription")
        self.assertEqual(transcription['duration'], 5.0)
        self.assertEqual(transcription['confidence'], 0.95)
        self.assertEqual(transcription['tags'], ["test", "unit"])
        self.assertEqual(transcription['notes'], "Test note")
    
    def test_search_transcriptions(self):
        """Test searching transcriptions."""
        # Add test data
        id1 = self.db.add_transcription("Hello world", tags=["greeting"])
        id2 = self.db.add_transcription("Python programming", tags=["code"])
        id3 = self.db.add_transcription("Hello Python", tags=["greeting", "code"])
        
        # Test text search
        results = self.db.search_transcriptions("Hello")
        self.assertEqual(len(results), 2)
        
        # Test tag search
        results = self.db.search_transcriptions(tags=["greeting"])
        self.assertEqual(len(results), 2)
        
        # Test combined search
        results = self.db.search_transcriptions("Python", tags=["code"])
        self.assertEqual(len(results), 2)
    
    def test_update_transcription(self):
        """Test updating transcriptions."""
        trans_id = self.db.add_transcription("Original text")
        
        success = self.db.update_transcription(
            trans_id,
            text="Updated text",
            tags=["updated"],
            notes="Updated note"
        )
        
        self.assertTrue(success)
        
        transcription = self.db.get_transcription(trans_id)
        self.assertEqual(transcription['text'], "Updated text")
        self.assertEqual(transcription['tags'], ["updated"])
        self.assertEqual(transcription['notes'], "Updated note")
    
    def test_delete_transcription(self):
        """Test deleting transcriptions."""
        trans_id = self.db.add_transcription("To be deleted")
        
        success = self.db.delete_transcription(trans_id)
        self.assertTrue(success)
        
        transcription = self.db.get_transcription(trans_id)
        self.assertIsNone(transcription)
    
    def test_export_functionality(self):
        """Test export functionality."""
        # Add test data
        self.db.add_transcription("Export test 1", duration=1.0)
        self.db.add_transcription("Export test 2", duration=2.0)
        
        # Test CSV export
        csv_file = tempfile.NamedTemporaryFile(delete=False, suffix='.csv')
        csv_file.close()
        
        try:
            success = self.db.export_to_csv(csv_file.name)
            self.assertTrue(success)
            self.assertTrue(os.path.exists(csv_file.name))
            
            # Verify CSV content
            with open(csv_file.name, 'r') as f:
                content = f.read()
                self.assertIn("Export test 1", content)
                self.assertIn("Export test 2", content)
        finally:
            if os.path.exists(csv_file.name):
                os.unlink(csv_file.name)
        
        # Test JSON export
        json_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        json_file.close()
        
        try:
            success = self.db.export_to_json(json_file.name)
            self.assertTrue(success)
            self.assertTrue(os.path.exists(json_file.name))
            
            # Verify JSON content
            import json
            with open(json_file.name, 'r') as f:
                data = json.load(f)
                self.assertIn('transcriptions', data)
                self.assertEqual(len(data['transcriptions']), 2)
        finally:
            if os.path.exists(json_file.name):
                os.unlink(json_file.name)


class TestAudioRecorder(unittest.TestCase):
    """Test audio recording functionality."""
    
    def setUp(self):
        """Set up audio recorder."""
        self.recorder = AudioRecorder()
    
    @patch('sounddevice.query_devices')
    def test_get_available_devices(self, mock_query):
        """Test getting available devices."""
        mock_query.return_value = [
            {'name': 'Device 1', 'max_input_channels': 2, 'default_samplerate': 44100},
            {'name': 'Device 2', 'max_input_channels': 1, 'default_samplerate': 48000},
            {'name': 'Output Only', 'max_input_channels': 0, 'default_samplerate': 44100}
        ]
        
        devices = self.recorder.get_available_devices()
        self.assertEqual(len(devices), 2)  # Only input devices
        self.assertEqual(devices[0]['name'], 'Device 1')
        self.assertEqual(devices[1]['name'], 'Device 2')
    
    def test_audio_level_calculation(self):
        """Test audio level calculation."""
        # Test with silent audio
        silent_audio = np.zeros(1000, dtype=np.float32)
        level = self.recorder.get_audio_level(silent_audio)
        self.assertEqual(level, 0.0)
        
        # Test with noise
        noise_audio = np.random.randn(1000).astype(np.float32) * 0.1
        level = self.recorder.get_audio_level(noise_audio)
        self.assertGreater(level, 0.0)
        self.assertLessEqual(level, 1.0)
    
    def test_silence_detection(self):
        """Test silence detection."""
        # Test silent audio
        silent_audio = np.zeros(1000, dtype=np.float32)
        is_silent = self.recorder.is_silent(silent_audio, threshold=0.01)
        self.assertTrue(is_silent)
        
        # Test loud audio
        loud_audio = np.ones(1000, dtype=np.float32) * 0.1
        is_silent = self.recorder.is_silent(loud_audio, threshold=0.01)
        self.assertFalse(is_silent)
    
    def test_audio_saving(self):
        """Test audio file saving."""
        # Create test audio data
        sample_rate = 16000
        duration = 1.0
        test_audio = np.sin(2 * np.pi * 440 * np.linspace(0, duration, int(sample_rate * duration)))
        test_audio = test_audio.astype(np.float32)
        
        # Save to temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
        temp_file.close()
        
        try:
            success = self.recorder.save_audio(test_audio, temp_file.name)
            self.assertTrue(success)
            self.assertTrue(os.path.exists(temp_file.name))
            
            # Verify file size is reasonable
            file_size = os.path.getsize(temp_file.name)
            self.assertGreater(file_size, 1000)  # Should be at least 1KB
        finally:
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)


class TestVoiceActivityDetector(unittest.TestCase):
    """Test voice activity detection."""
    
    def setUp(self):
        """Set up VAD."""
        self.vad = VoiceActivityDetector(threshold=0.02, min_duration=0.1)
    
    def test_voice_detection(self):
        """Test voice activity detection."""
        sample_rate = 16000
        
        # Test with silence
        silent_chunk = np.zeros(1600, dtype=np.float32)  # 0.1 seconds
        activity = self.vad.process_audio(silent_chunk, sample_rate)
        self.assertFalse(activity)
        
        # Test with voice-like signal
        voice_chunk = np.random.randn(1600).astype(np.float32) * 0.1
        activity = self.vad.process_audio(voice_chunk, sample_rate)
        # May or may not detect voice depending on random values
        self.assertIsInstance(activity, bool)


class TestSpeechToText(unittest.TestCase):
    """Test speech-to-text functionality."""
    
    def setUp(self):
        """Set up transcriber."""
        # Use tiny model for faster testing
        self.transcriber = WhisperTranscriber(model_name="tiny")
    
    def test_model_info(self):
        """Test getting model information."""
        info = self.transcriber.get_model_info()
        
        self.assertIn('model_name', info)
        self.assertIn('device', info)
        self.assertIn('is_ready', info)
        self.assertEqual(info['model_name'], 'tiny')
    
    def test_available_models(self):
        """Test getting available models."""
        models = self.transcriber.get_available_models()
        
        self.assertIsInstance(models, list)
        self.assertIn('tiny', models)
        self.assertIn('base', models)
        self.assertIn('small', models)
    
    def test_supported_languages(self):
        """Test getting supported languages."""
        languages = self.transcriber.get_supported_languages()
        
        self.assertIsInstance(languages, list)
        self.assertIn('en', languages)
    
    @unittest.skipIf(not os.environ.get('TEST_AUDIO'), "Audio testing disabled")
    def test_transcription_with_dummy_audio(self):
        """Test transcription with dummy audio data."""
        # Wait for model to load
        if not self.transcriber.wait_for_model(timeout=30):
            self.skipTest("Whisper model failed to load")
        
        # Create dummy audio (should produce nonsense transcription)
        sample_rate = 16000
        duration = 2.0
        dummy_audio = np.random.randn(int(sample_rate * duration)).astype(np.float32) * 0.1
        
        result = self.transcriber.transcribe_array(dummy_audio, sample_rate)
        
        self.assertIsInstance(result, dict)
        self.assertIn('text', result)
        self.assertNotIn('error', result)
        self.assertIsInstance(result['text'], str)


class TestKeyboardHandler(unittest.TestCase):
    """Test keyboard handler functionality."""
    
    def setUp(self):
        """Set up keyboard handler."""
        self.handler = GlobalKeyboardHandler()
    
    def test_hotkey_management(self):
        """Test hotkey registration and management."""
        # Test adding hotkey
        callback = Mock()
        self.handler.add_hotkey("test_hotkey", [self.handler.modifier_key], callback, "Test hotkey")
        
        self.assertIn("test_hotkey", self.handler.hotkeys)
        
        # Test removing hotkey
        success = self.handler.remove_hotkey("test_hotkey")
        self.assertTrue(success)
        self.assertNotIn("test_hotkey", self.handler.hotkeys)
        
        # Test removing non-existent hotkey
        success = self.handler.remove_hotkey("nonexistent")
        self.assertFalse(success)
    
    def test_hotkey_info(self):
        """Test getting hotkey information."""
        info = self.handler.get_hotkeys_info()
        
        self.assertIsInstance(info, dict)
        # Should have at least the default recording hotkey
        self.assertGreater(len(info), 0)
        
        for name, hotkey_info in info.items():
            self.assertIn('keys', hotkey_info)
            self.assertIn('description', hotkey_info)


class TestSpeechRecorderConfig(unittest.TestCase):
    """Test speech recorder configuration."""
    
    def test_default_config(self):
        """Test default configuration."""
        config = SpeechRecorderConfig()
        
        self.assertEqual(config.sample_rate, 16000)
        self.assertEqual(config.channels, 1)
        self.assertEqual(config.whisper_model, "base")
        self.assertTrue(config.auto_save)
        self.assertTrue(config.enable_global_shortcuts)
    
    def test_config_file_operations(self):
        """Test configuration file save/load."""
        config = SpeechRecorderConfig()
        config.whisper_model = "small"
        config.sample_rate = 22050
        config.language = "en"
        
        # Save to temporary file
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        temp_file.close()
        
        try:
            config.save_to_file(temp_file.name)
            self.assertTrue(os.path.exists(temp_file.name))
            
            # Load configuration
            loaded_config = SpeechRecorderConfig.from_file(temp_file.name)
            
            self.assertEqual(loaded_config.whisper_model, "small")
            self.assertEqual(loaded_config.sample_rate, 22050)
            self.assertEqual(loaded_config.language, "en")
        finally:
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)


class TestSpeechRecorderIntegration(unittest.TestCase):
    """Test speech recorder integration."""
    
    def setUp(self):
        """Set up speech recorder."""
        config = SpeechRecorderConfig()
        config.enable_global_shortcuts = False  # Disable for testing
        config.whisper_model = "tiny"  # Use smallest model
        config.database_path = tempfile.NamedTemporaryFile(delete=False, suffix='.db').name
        
        self.config = config
        self.recorder = SpeechRecorder(config)
    
    def tearDown(self):
        """Clean up."""
        self.recorder.shutdown()
        if os.path.exists(self.config.database_path):
            os.unlink(self.config.database_path)
    
    @patch('audio_recorder.AudioRecorder.start_recording')
    @patch('audio_recorder.AudioRecorder.stop_recording')
    def test_recording_workflow(self, mock_stop, mock_start):
        """Test basic recording workflow."""
        # Mock audio recording
        mock_start.return_value = True
        mock_stop.return_value = np.random.randn(16000).astype(np.float32)  # 1 second of audio
        
        # Initialize
        success = self.recorder.initialize()
        self.assertTrue(success)
        
        # Test recording session
        session = self.recorder.start_recording()
        self.assertIsNotNone(session)
        self.assertTrue(self.recorder.is_recording)
        
        success = self.recorder.stop_recording()
        self.assertTrue(success)
        self.assertFalse(self.recorder.is_recording)
    
    def test_status_reporting(self):
        """Test status reporting."""
        # Initialize
        if not self.recorder.initialize():
            self.skipTest("Failed to initialize recorder")
        
        status = self.recorder.get_status()
        
        self.assertIsInstance(status, dict)
        self.assertIn('is_initialized', status)
        self.assertIn('is_recording', status)
        self.assertIn('config', status)
        self.assertTrue(status['is_initialized'])
        self.assertFalse(status['is_recording'])


class TestApplicationIntegration(unittest.TestCase):
    """Test complete application integration."""
    
    @patch('speech_to_text.WhisperTranscriber.wait_for_model')
    @patch('audio_recorder.AudioRecorder.get_available_devices')
    def test_component_initialization(self, mock_devices, mock_wait):
        """Test that all components can be initialized together."""
        mock_devices.return_value = [
            {'id': 0, 'name': 'Test Device', 'channels': 1, 'sample_rate': 44100}
        ]
        mock_wait.return_value = True
        
        # Test database
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        try:
            db = TranscriptionDatabase(temp_db.name)
            stats = db.get_statistics()
            self.assertEqual(stats['total_transcriptions'], 0)
            
            # Test audio recorder
            recorder = AudioRecorder()
            devices = recorder.get_available_devices()
            self.assertIsInstance(devices, list)
            
            # Test transcriber
            transcriber = WhisperTranscriber(model_name="tiny")
            models = transcriber.get_available_models()
            self.assertIsInstance(models, list)
            
            # Test keyboard handler
            keyboard = GlobalKeyboardHandler()
            info = keyboard.get_hotkeys_info()
            self.assertIsInstance(info, dict)
        
        finally:
            if os.path.exists(temp_db.name):
                os.unlink(temp_db.name)


def run_performance_tests():
    """Run performance tests (not part of unittest)."""
    print("Running performance tests...")
    
    # Test database performance
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    
    try:
        db = TranscriptionDatabase(temp_db.name)
        
        # Test bulk insert performance
        start_time = time.time()
        num_records = 100
        
        for i in range(num_records):
            db.add_transcription(f"Test transcription {i}", duration=float(i))
        
        insert_time = time.time() - start_time
        print(f"Inserted {num_records} records in {insert_time:.2f}s ({num_records/insert_time:.1f} records/sec)")
        
        # Test search performance
        start_time = time.time()
        results = db.search_transcriptions("Test", limit=1000)
        search_time = time.time() - start_time
        print(f"Searched {len(results)} records in {search_time:.3f}s")
    
    finally:
        if os.path.exists(temp_db.name):
            os.unlink(temp_db.name)


def run_stress_tests():
    """Run stress tests (not part of unittest)."""
    print("Running stress tests...")
    
    # Test rapid recording start/stop
    config = SpeechRecorderConfig()
    config.enable_global_shortcuts = False
    config.whisper_model = "tiny"
    config.database_path = tempfile.NamedTemporaryFile(delete=False, suffix='.db').name
    
    recorder = SpeechRecorder(config)
    
    try:
        if recorder.initialize():
            print("Testing rapid start/stop cycles...")
            
            for i in range(10):
                session = recorder.start_recording()
                if session:
                    time.sleep(0.1)  # Brief recording
                    recorder.stop_recording()
                    print(f"  Cycle {i+1} completed")
                else:
                    print(f"  Cycle {i+1} failed to start")
        
        recorder.shutdown()
    
    finally:
        if os.path.exists(config.database_path):
            os.unlink(config.database_path)


def main():
    """Main test runner."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Speech-to-Text Transcriber")
    parser.add_argument("--unit", action="store_true", help="Run unit tests")
    parser.add_argument("--performance", action="store_true", help="Run performance tests")
    parser.add_argument("--stress", action="store_true", help="Run stress tests")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if not any([args.unit, args.performance, args.stress, args.all]):
        args.unit = True  # Default to unit tests
    
    success = True
    
    if args.unit or args.all:
        print("Running unit tests...")
        
        # Create test suite
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        
        # Add test cases
        test_classes = [
            TestDatabase,
            TestAudioRecorder,
            TestVoiceActivityDetector,
            TestSpeechToText,
            TestKeyboardHandler,
            TestSpeechRecorderConfig,
            TestSpeechRecorderIntegration,
            TestApplicationIntegration
        ]
        
        for test_class in test_classes:
            tests = loader.loadTestsFromTestCase(test_class)
            suite.addTests(tests)
        
        # Run tests
        verbosity = 2 if args.verbose else 1
        runner = unittest.TextTestRunner(verbosity=verbosity)
        result = runner.run(suite)
        
        if not result.wasSuccessful():
            success = False
            print(f"\nUnit tests failed: {len(result.failures)} failures, {len(result.errors)} errors")
    
    if args.performance or args.all:
        try:
            run_performance_tests()
        except Exception as e:
            print(f"Performance tests failed: {e}")
            success = False
    
    if args.stress or args.all:
        try:
            run_stress_tests()
        except Exception as e:
            print(f"Stress tests failed: {e}")
            success = False
    
    print("\n" + "=" * 50)
    if success:
        print("All tests completed successfully! ✅")
        return 0
    else:
        print("Some tests failed! ❌")
        return 1


if __name__ == "__main__":
    sys.exit(main())