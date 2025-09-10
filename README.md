# Speech-to-Text Transcriber

A comprehensive, modern speech-to-text application that combines local AI processing with an intuitive interface for recording, transcribing, and managing voice recordings.

![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-lightgrey.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## ✨ Features

### 🎯 Core Functionality
- **Global Keyboard Shortcuts**: Press `Cmd+R` (macOS) or `Ctrl+R` (Windows/Linux) to start/stop recording from anywhere
- **Offline AI Transcription**: Uses OpenAI Whisper for high-quality, offline speech recognition
- **Cross-Platform Support**: Works on macOS, Windows, and Linux
- **Modern GUI Interface**: Clean, intuitive Tkinter-based interface for managing transcriptions
- **Command-Line Interface**: Full CLI support for headless operation and automation

### 🗄️ Data Management
- **SQLite Database**: Local storage with full-text search capabilities
- **Export Options**: Export transcriptions to CSV, JSON, or plain text
- **Tagging System**: Organize transcriptions with custom tags
- **Search Functionality**: Find transcriptions by text content, date, or tags
- **Edit Capabilities**: Modify transcriptions after recording

### 🎙️ Audio Features
- **High-Quality Recording**: 16kHz sample rate optimized for speech recognition
- **Voice Activity Detection**: Automatic silence detection for hands-free operation
- **Audio Device Selection**: Choose from available input devices
- **Audio File Storage**: Optional saving of original audio files
- **Real-Time Audio Level**: Visual feedback during recording

### 🔧 Advanced Features
- **Multiple Whisper Models**: Support for tiny, base, small, medium, and large models
- **Language Detection**: Automatic language detection or manual selection
- **Batch Processing**: Queue multiple recordings for processing
- **Configuration Management**: Customizable settings via JSON configuration files
- **Comprehensive Testing**: Full test suite for reliability

## 📋 Requirements

### System Requirements
- **Python**: 3.8 or higher
- **Operating System**: macOS 10.14+, Windows 10+, or Linux (Ubuntu 18.04+)
- **Memory**: 2GB RAM minimum (4GB+ recommended for larger Whisper models)
- **Storage**: 1GB available space (more for audio file storage)

### Dependencies
- `openai-whisper` - AI speech recognition
- `sounddevice` - Audio recording
- `numpy` - Numerical computations
- `scipy` - Signal processing
- `pynput` - Global keyboard shortcuts
- `librosa` - Audio processing
- `soundfile` - Audio file I/O
- `tkinter` - GUI framework (usually built-in)

## 🚀 Quick Start

### 1. Installation

#### Automatic Setup (Recommended)
```bash
# Clone or download the repository
git clone <repository-url>
cd speech-to-text-transcriber

# Run the setup script
python setup.py
```

#### Manual Installation
```bash
# Install dependencies
pip install -r requirements.txt

# Verify installation
python main.py test
```

### 2. First Run

#### Launch GUI (Recommended for beginners)
```bash
python main.py gui
```

#### Command Line Interface
```bash
# Start headless mode with global shortcuts
python main.py headless

# Record a single transcription
python main.py record --duration 10

# List existing transcriptions
python main.py list
```

### 3. Basic Usage

1. **Start Recording**: Press `Cmd+R` (macOS) or `Ctrl+R` (Windows/Linux)
2. **Speak Clearly**: The application will automatically detect voice activity
3. **Stop Recording**: Press the hotkey again or wait for auto-stop after silence
4. **View Results**: Transcriptions appear in the GUI or terminal

## 📖 Detailed Usage

### GUI Interface

The graphical interface provides the most user-friendly experience:

#### Main Window Components
- **Transcription List** (Left Panel): Browse and search all transcriptions
- **Recording Controls** (Top Right): Start/stop recording with visual feedback
- **Transcription Details** (Bottom Right): View and edit selected transcriptions

#### Key Features
- **Search Bar**: Find transcriptions by typing keywords
- **Date Filters**: Filter by today, this week, this month, or all time
- **Context Menu**: Right-click transcriptions for edit/delete/export options
- **Settings Dialog**: Configure audio devices, Whisper models, and preferences

### Command Line Interface

The CLI provides powerful automation and headless operation:

#### Recording Commands
```bash
# Record for a specific duration
python main.py record --duration 30

# Manual recording (press Enter to stop)
python main.py record --manual-stop

# Record with specific settings
python main.py record --model base --language en --save-audio

# Record and save to file
python main.py record --duration 10 --output transcription.txt
```

#### Database Management
```bash
# List all transcriptions
python main.py list

# Search transcriptions
python main.py list --query "meeting notes"

# Export all transcriptions
python main.py export all_transcriptions.csv
python main.py export all_transcriptions.json --format json
```

#### Testing and Diagnostics
```bash
# Test all components
python main.py test

# Test with audio input
python main.py test --test-audio

# Test specific Whisper model
python main.py test --model small
```

### Configuration

#### Configuration File
Create a `config.json` file to customize settings:

```json
{
  "sample_rate": 16000,
  "whisper_model": "base",
  "language": null,
  "auto_stop_enabled": true,
  "silence_timeout": 2.0,
  "save_audio_files": false,
  "database_path": "transcriptions.db",
  "enable_global_shortcuts": true,
  "vad_enabled": true,
  "vad_threshold": 0.02
}
```

Load configuration:
```bash
python main.py headless --config config.json
```

#### Audio Device Selection
```bash
# List available devices
python -c "from audio_recorder import AudioRecorder; r=AudioRecorder(); print(r.get_available_devices())"

# Use specific device
python main.py record --device 1
```

## 🎛️ Configuration Options

### Audio Settings
- **Sample Rate**: Recording sample rate (16000 recommended for Whisper)
- **Channels**: Number of audio channels (1 for mono, 2 for stereo)
- **Audio Device**: Input device selection
- **Chunk Size**: Audio processing chunk size

### Whisper Settings
- **Model**: Choose from `tiny`, `base`, `small`, `medium`, `large`
  - `tiny`: Fastest, least accurate (~39 MB)
  - `base`: Good balance (~74 MB)
  - `small`: Better accuracy (~244 MB)
  - `medium`: High accuracy (~769 MB)
  - `large`: Best accuracy (~1550 MB)
- **Language**: Specific language or auto-detection
- **Device**: CPU, CUDA, or MPS (Apple Silicon)

### Recording Settings
- **Auto-Stop**: Automatic recording termination after silence
- **Silence Timeout**: Duration of silence before auto-stop
- **Voice Activity Detection**: Enable/disable VAD
- **VAD Threshold**: Sensitivity for voice detection
- **Maximum Duration**: Maximum recording length

### Database Settings
- **Database Path**: SQLite database file location
- **Auto-Save**: Automatically save transcriptions
- **Backup**: Automatic database backups

## 🔧 Advanced Usage

### Voice Activity Detection (VAD)

VAD automatically detects when you start and stop speaking:

```python
# Configure VAD in config.json
{
  "vad_enabled": true,
  "vad_threshold": 0.02,  # Lower = more sensitive
  "vad_min_duration": 0.1
}
```

### Batch Processing

Process multiple recordings efficiently:

```bash
# Record multiple sessions
python main.py headless  # Use global shortcuts for multiple recordings

# Process existing audio files
python -c "
from speech_to_text import WhisperTranscriber
from database import TranscriptionDatabase

transcriber = WhisperTranscriber()
db = TranscriptionDatabase()

for audio_file in ['file1.wav', 'file2.wav']:
    result = transcriber.transcribe_file(audio_file)
    if 'text' in result:
        db.add_transcription(result['text'], audio_file_path=audio_file)
"
```

### Custom Keyboard Shortcuts

Customize global shortcuts programmatically:

```python
from keyboard_handler import GlobalKeyboardHandler

handler = GlobalKeyboardHandler()
handler.create_custom_hotkey(
    "custom_record", 
    "ctrl", 
    "space", 
    callback_function,
    "Custom recording shortcut"
)
```

### Integration with Other Applications

Export data for use in other applications:

```bash
# Export to CSV for Excel/Google Sheets
python main.py export transcriptions.csv

# Export to JSON for programmatic access
python main.py export transcriptions.json --format json

# Export specific search results
python main.py list --query "important" | head -10
```

## 🧪 Testing

### Run Test Suite
```bash
# Run all tests
python test_app.py --all

# Run specific test categories
python test_app.py --unit          # Unit tests only
python test_app.py --performance   # Performance tests
python test_app.py --stress        # Stress tests

# Verbose output
python test_app.py --all --verbose
```

### Manual Testing
```bash
# Test system components
python main.py test --test-audio

# Test specific model
python main.py test --model tiny

# Test without keyboard handler
python main.py test --no-keyboard
```

## 🛠️ Troubleshooting

### Common Issues

#### Audio Not Working
```bash
# Check available devices
python -c "import sounddevice as sd; print(sd.query_devices())"

# Test audio input
python main.py test --test-audio

# Try different device
python main.py record --device 0
```

#### Whisper Model Issues
```bash
# Check model loading
python -c "import whisper; whisper.load_model('base')"

# Try smaller model
python main.py record --model tiny

# Check device compatibility
python -c "import torch; print(torch.cuda.is_available())"
```

#### Global Shortcuts Not Working
- **macOS**: Grant accessibility permissions in System Preferences
- **Linux**: Install required packages: `sudo apt-get install python3-tk python3-dev`
- **Windows**: Run as administrator if needed

#### Database Issues
```bash
# Check database
python -c "from database import TranscriptionDatabase; db=TranscriptionDatabase(); print(db.get_statistics())"

# Reset database (WARNING: deletes all data)
rm transcriptions.db
python main.py test
```

### Performance Optimization

#### For Better Performance
- Use smaller Whisper models (`tiny` or `base`)
- Enable CUDA if you have a compatible GPU
- Increase system RAM for larger models
- Use SSD storage for faster database access

#### For Better Accuracy
- Use larger Whisper models (`medium` or `large`)
- Ensure good microphone quality
- Record in quiet environments
- Speak clearly and at moderate pace

### Memory Usage

Model memory requirements:
- `tiny`: ~1 GB RAM
- `base`: ~1 GB RAM
- `small`: ~2 GB RAM
- `medium`: ~5 GB RAM
- `large`: ~10 GB RAM

## 📁 Project Structure

```
speech-to-text-transcriber/
├── main.py                 # Application entry point
├── speech_recorder.py      # Core coordinator
├── audio_recorder.py       # Audio recording module
├── speech_to_text.py       # Whisper integration
├── database.py             # SQLite database management
├── keyboard_handler.py     # Global keyboard shortcuts
├── ui.py                   # Tkinter GUI interface
├── setup.py               # Automated setup script
├── test_app.py            # Comprehensive test suite
├── requirements.txt       # Python dependencies
└── README.md             # This documentation
```

## 🤝 Contributing

We welcome contributions! Here's how to get started:

1. **Fork the Repository**
2. **Create a Feature Branch**: `git checkout -b feature/amazing-feature`
3. **Make Changes**: Implement your feature or fix
4. **Run Tests**: `python test_app.py --all`
5. **Commit Changes**: `git commit -m 'Add amazing feature'`
6. **Push Branch**: `git push origin feature/amazing-feature`
7. **Create Pull Request**

### Development Guidelines
- Follow PEP 8 style guidelines
- Add tests for new features
- Update documentation as needed
- Ensure cross-platform compatibility

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **OpenAI** for the Whisper speech recognition model
- **Python Community** for the excellent libraries used
- **Contributors** who help improve this project

## 📞 Support

### Getting Help
- **Documentation**: Read this README thoroughly
- **Issues**: Create a GitHub issue for bugs or feature requests
- **Discussions**: Use GitHub Discussions for questions
- **Testing**: Run `python main.py test` to diagnose issues

### Frequently Asked Questions

**Q: Which Whisper model should I use?**
A: Start with `base` for a good balance of speed and accuracy. Use `tiny` for fastest processing or `medium`/`large` for best accuracy.

**Q: Can I use this offline?**
A: Yes! Once models are downloaded, everything runs offline.

**Q: How do I improve transcription accuracy?**
A: Use a larger model, ensure good audio quality, and speak clearly in a quiet environment.

**Q: Can I transcribe in languages other than English?**
A: Yes! Whisper supports 99 languages. Set the language in configuration or let it auto-detect.

**Q: How much storage do I need?**
A: Base installation: ~1GB. Each Whisper model: 75MB-1.5GB. Audio files (if saved): ~1MB per minute.

---

**Made with ❤️ for the open source community**