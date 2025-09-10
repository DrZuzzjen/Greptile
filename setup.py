#!/usr/bin/env python3
"""
Setup script for Speech-to-Text Transcriber application.
Handles installation, dependency management, and system configuration.
"""

import os
import sys
import subprocess
import platform
import logging
from pathlib import Path
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)


class SetupManager:
    """Manages application setup and installation."""
    
    def __init__(self):
        """Initialize setup manager."""
        self.platform = platform.system().lower()
        self.python_version = sys.version_info
        self.errors = []
        self.warnings = []
        
        # Minimum requirements
        self.min_python_version = (3, 8)
        self.required_packages = [
            'openai-whisper',
            'sounddevice',
            'numpy',
            'scipy',
            'pynput',
            'librosa',
            'soundfile'
        ]
        
        # Optional packages
        self.optional_packages = [
            'pytest',
            'pytest-cov'
        ]
        
        # Platform-specific requirements
        self.platform_packages = {
            'darwin': [],  # macOS
            'linux': ['python3-tk'],  # Linux
            'windows': []  # Windows
        }
    
    def check_python_version(self) -> bool:
        """Check if Python version meets requirements."""
        print(f"Checking Python version... {self.python_version.major}.{self.python_version.minor}")
        
        if self.python_version < self.min_python_version:
            self.errors.append(
                f"Python {self.min_python_version[0]}.{self.min_python_version[1]}+ required, "
                f"found {self.python_version.major}.{self.python_version.minor}"
            )
            return False
        
        print("✅ Python version OK")
        return True
    
    def check_system_dependencies(self) -> bool:
        """Check system-level dependencies."""
        print("Checking system dependencies...")
        
        success = True
        
        # Check for ffmpeg (required by librosa)
        if not self._command_exists('ffmpeg'):
            self.warnings.append(
                "ffmpeg not found. Some audio formats may not work. "
                "Install with: brew install ffmpeg (macOS) or apt-get install ffmpeg (Linux)"
            )
        
        # Check platform-specific dependencies
        platform_deps = self.platform_packages.get(self.platform, [])
        if platform_deps:
            print(f"Platform-specific dependencies for {self.platform}: {platform_deps}")
            # Note: We can't automatically install system packages
            self.warnings.append(
                f"Please ensure these system packages are installed: {platform_deps}"
            )
        
        print("✅ System dependencies checked")
        return success
    
    def install_python_packages(self, include_optional: bool = False) -> bool:
        """Install Python packages."""
        print("Installing Python packages...")
        
        packages_to_install = self.required_packages.copy()
        if include_optional:
            packages_to_install.extend(self.optional_packages)
        
        success = True
        
        for package in packages_to_install:
            print(f"  Installing {package}...")
            
            try:
                result = subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', package],
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout per package
                )
                
                if result.returncode == 0:
                    print(f"    ✅ {package} installed successfully")
                else:
                    print(f"    ❌ Failed to install {package}")
                    print(f"    Error: {result.stderr}")
                    self.errors.append(f"Failed to install {package}: {result.stderr}")
                    success = False
            
            except subprocess.TimeoutExpired:
                print(f"    ❌ Timeout installing {package}")
                self.errors.append(f"Timeout installing {package}")
                success = False
            
            except Exception as e:
                print(f"    ❌ Error installing {package}: {e}")
                self.errors.append(f"Error installing {package}: {e}")
                success = False
        
        return success
    
    def verify_installation(self) -> bool:
        """Verify that all components can be imported."""
        print("Verifying installation...")
        
        modules_to_test = [
            ('whisper', 'OpenAI Whisper'),
            ('sounddevice', 'Sound Device'),
            ('numpy', 'NumPy'),
            ('scipy', 'SciPy'),
            ('pynput', 'PyNput'),
            ('librosa', 'Librosa'),
            ('soundfile', 'Sound File'),
            ('tkinter', 'Tkinter (GUI)'),
            ('sqlite3', 'SQLite3'),
            ('threading', 'Threading'),
            ('queue', 'Queue'),
            ('pathlib', 'PathLib')
        ]
        
        success = True
        
        for module, name in modules_to_test:
            try:
                __import__(module)
                print(f"  ✅ {name} import OK")
            except ImportError as e:
                if module == 'tkinter':
                    print(f"  ⚠️  {name} import failed (GUI will not work): {e}")
                    self.warnings.append(f"Tkinter not available - GUI mode will not work")
                else:
                    print(f"  ❌ {name} import failed: {e}")
                    self.errors.append(f"Failed to import {module}: {e}")
                    success = False
            except Exception as e:
                print(f"  ❌ {name} import error: {e}")
                self.errors.append(f"Error importing {module}: {e}")
                success = False
        
        return success
    
    def test_components(self) -> bool:
        """Test basic functionality of key components."""
        print("Testing components...")
        
        success = True
        
        # Test audio system
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            input_devices = [d for d in devices if d['max_input_channels'] > 0]
            
            if input_devices:
                print(f"  ✅ Audio system OK ({len(input_devices)} input devices found)")
            else:
                print("  ⚠️  No audio input devices found")
                self.warnings.append("No audio input devices detected")
        
        except Exception as e:
            print(f"  ❌ Audio system test failed: {e}")
            self.errors.append(f"Audio system test failed: {e}")
            success = False
        
        # Test Whisper (basic load test)
        try:
            import whisper
            print("  Testing Whisper model loading...")
            
            # Try to load the smallest model
            model = whisper.load_model("tiny")
            print("  ✅ Whisper model loading OK")
            
        except Exception as e:
            print(f"  ❌ Whisper test failed: {e}")
            self.errors.append(f"Whisper test failed: {e}")
            success = False
        
        # Test database
        try:
            import sqlite3
            import tempfile
            import os
            
            # Create temporary database
            with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
                tmp_path = tmp.name
            
            try:
                conn = sqlite3.connect(tmp_path)
                cursor = conn.cursor()
                cursor.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
                cursor.execute("INSERT INTO test (id) VALUES (1)")
                cursor.execute("SELECT * FROM test")
                result = cursor.fetchone()
                conn.close()
                
                if result == (1,):
                    print("  ✅ Database system OK")
                else:
                    raise Exception("Database test query failed")
            
            finally:
                # Clean up
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        
        except Exception as e:
            print(f"  ❌ Database test failed: {e}")
            self.errors.append(f"Database test failed: {e}")
            success = False
        
        return success
    
    def create_desktop_shortcut(self) -> bool:
        """Create desktop shortcut (platform-specific)."""
        print("Creating desktop shortcut...")
        
        try:
            script_dir = Path(__file__).parent
            main_script = script_dir / "main.py"
            
            if not main_script.exists():
                self.warnings.append("main.py not found - cannot create shortcut")
                return False
            
            if self.platform == "darwin":  # macOS
                self._create_macos_shortcut(main_script)
            elif self.platform == "linux":
                self._create_linux_shortcut(main_script)
            elif self.platform == "windows":
                self._create_windows_shortcut(main_script)
            else:
                self.warnings.append(f"Desktop shortcuts not supported on {self.platform}")
                return False
            
            print("  ✅ Desktop shortcut created")
            return True
        
        except Exception as e:
            print(f"  ⚠️  Failed to create desktop shortcut: {e}")
            self.warnings.append(f"Failed to create desktop shortcut: {e}")
            return False
    
    def _create_macos_shortcut(self, main_script: Path):
        """Create macOS application bundle."""
        desktop = Path.home() / "Desktop"
        app_name = "Speech-to-Text Transcriber.app"
        app_path = desktop / app_name
        
        # Create app bundle structure
        contents_dir = app_path / "Contents"
        macos_dir = contents_dir / "MacOS"
        resources_dir = contents_dir / "Resources"
        
        for dir_path in [app_path, contents_dir, macos_dir, resources_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Create Info.plist
        info_plist = contents_dir / "Info.plist"
        info_plist.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>speech-transcriber</string>
    <key>CFBundleIdentifier</key>
    <string>com.local.speech-transcriber</string>
    <key>CFBundleName</key>
    <string>Speech-to-Text Transcriber</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
</dict>
</plist>""")
        
        # Create executable script
        executable = macos_dir / "speech-transcriber"
        executable.write_text(f"""#!/bin/bash
cd "{main_script.parent}"
{sys.executable} "{main_script}" gui
""")
        executable.chmod(0o755)
    
    def _create_linux_shortcut(self, main_script: Path):
        """Create Linux .desktop file."""
        desktop = Path.home() / "Desktop"
        desktop_file = desktop / "speech-transcriber.desktop"
        
        desktop_file.write_text(f"""[Desktop Entry]
Version=1.0
Type=Application
Name=Speech-to-Text Transcriber
Comment=Record and transcribe speech using AI
Icon=audio-input-microphone
Exec={sys.executable} "{main_script}" gui
Terminal=false
Categories=AudioVideo;Audio;
""")
        desktop_file.chmod(0o755)
    
    def _create_windows_shortcut(self, main_script: Path):
        """Create Windows shortcut."""
        try:
            import winshell
            from win32com.client import Dispatch
            
            desktop = winshell.desktop()
            shortcut_path = os.path.join(desktop, "Speech-to-Text Transcriber.lnk")
            
            shell = Dispatch('WScript.Shell')
            shortcut = shell.CreateShortCut(shortcut_path)
            shortcut.Targetpath = sys.executable
            shortcut.Arguments = f'"{main_script}" gui'
            shortcut.WorkingDirectory = str(main_script.parent)
            shortcut.IconLocation = sys.executable
            shortcut.save()
        
        except ImportError:
            # Fallback: create batch file
            desktop = Path.home() / "Desktop"
            batch_file = desktop / "Speech-to-Text Transcriber.bat"
            
            batch_file.write_text(f"""@echo off
cd /d "{main_script.parent}"
"{sys.executable}" "{main_script}" gui
pause
""")
    
    def _command_exists(self, command: str) -> bool:
        """Check if a command exists in the system PATH."""
        try:
            subprocess.run([command, '--version'], 
                         capture_output=True, 
                         check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def run_setup(self, include_optional: bool = False, 
                  create_shortcut: bool = True) -> bool:
        """Run complete setup process."""
        print("Speech-to-Text Transcriber Setup")
        print("=" * 50)
        
        success = True
        
        # Check Python version
        if not self.check_python_version():
            success = False
        
        # Check system dependencies
        self.check_system_dependencies()
        
        # Install packages
        if success:
            if not self.install_python_packages(include_optional):
                success = False
        
        # Verify installation
        if success:
            if not self.verify_installation():
                success = False
        
        # Test components
        if success:
            if not self.test_components():
                success = False
        
        # Create desktop shortcut
        if success and create_shortcut:
            self.create_desktop_shortcut()
        
        # Print summary
        print("\n" + "=" * 50)
        print("Setup Summary")
        print("=" * 50)
        
        if success:
            print("✅ Setup completed successfully!")
            print("\nNext steps:")
            print("1. Run 'python main.py gui' to launch the GUI")
            print("2. Run 'python main.py test' to test all components")
            print("3. Run 'python main.py headless' for command-line mode")
        else:
            print("❌ Setup completed with errors")
        
        if self.warnings:
            print(f"\n⚠️  Warnings ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  - {warning}")
        
        if self.errors:
            print(f"\n❌ Errors ({len(self.errors)}):")
            for error in self.errors:
                print(f"  - {error}")
        
        return success


def main():
    """Main setup entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Setup Speech-to-Text Transcriber")
    parser.add_argument("--include-optional", action="store_true",
                       help="Install optional packages (testing, etc.)")
    parser.add_argument("--no-shortcut", action="store_true",
                       help="Don't create desktop shortcut")
    parser.add_argument("--verbose", action="store_true",
                       help="Verbose output")
    
    args = parser.parse_args()
    
    # Setup logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format='%(levelname)s: %(message)s')
    
    # Run setup
    setup_manager = SetupManager()
    success = setup_manager.run_setup(
        include_optional=args.include_optional,
        create_shortcut=not args.no_shortcut
    )
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())