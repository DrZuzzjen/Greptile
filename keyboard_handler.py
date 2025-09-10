"""
Global keyboard shortcut handler for speech-to-text application.
Provides cross-platform support for global hotkeys using pynput.
"""

import logging
import threading
import platform
from typing import Optional, Callable, Set, Dict, List
from pynput import keyboard
from pynput.keyboard import Key, KeyCode, Listener
import time

logger = logging.getLogger(__name__)


class GlobalKeyboardHandler:
    """Manages global keyboard shortcuts across platforms."""
    
    def __init__(self):
        """Initialize the keyboard handler."""
        self.listener: Optional[Listener] = None
        self.is_listening = False
        
        # Track pressed keys for combination detection
        self.pressed_keys: Set[Key] = set()
        self.pressed_char_keys: Set[str] = set()
        
        # Hotkey configurations
        self.hotkeys: Dict[str, Dict] = {}
        
        # Default recording hotkey (Cmd+R on macOS, Ctrl+R elsewhere)
        self.platform = platform.system().lower()
        self.modifier_key = Key.cmd if self.platform == "darwin" else Key.ctrl
        
        # Callbacks
        self.on_recording_start: Optional[Callable] = None
        self.on_recording_stop: Optional[Callable] = None
        self.on_hotkey_pressed: Optional[Callable[[str], None]] = None
        
        # Recording state
        self.is_recording = False
        self.recording_lock = threading.Lock()
        
        # Setup default hotkeys
        self._setup_default_hotkeys()
    
    def _setup_default_hotkeys(self):
        """Setup default hotkey configurations."""
        # Recording toggle hotkey
        self.add_hotkey(
            "record_toggle",
            [self.modifier_key, KeyCode.from_char('r')],
            self._handle_recording_toggle,
            description="Toggle recording on/off"
        )
        
        # Alternative recording hotkey with different modifier
        alt_modifier = Key.ctrl if self.platform == "darwin" else Key.alt
        self.add_hotkey(
            "record_toggle_alt",
            [alt_modifier, KeyCode.from_char('r')],
            self._handle_recording_toggle,
            description="Alternative toggle recording"
        )
    
    def add_hotkey(
        self,
        name: str,
        key_combination: List,
        callback: Callable,
        description: str = ""
    ):
        """
        Add a global hotkey.
        
        Args:
            name: Unique name for the hotkey
            key_combination: List of keys that form the combination
            callback: Function to call when hotkey is pressed
            description: Description of the hotkey
        """
        self.hotkeys[name] = {
            'keys': set(key_combination),
            'callback': callback,
            'description': description,
            'last_triggered': 0
        }
        
        logger.info(f"Added hotkey '{name}': {self._format_hotkey(key_combination)} - {description}")
    
    def remove_hotkey(self, name: str) -> bool:
        """
        Remove a hotkey by name.
        
        Args:
            name: Name of the hotkey to remove
            
        Returns:
            True if hotkey was removed, False if not found
        """
        if name in self.hotkeys:
            del self.hotkeys[name]
            logger.info(f"Removed hotkey: {name}")
            return True
        return False
    
    def _format_hotkey(self, key_combination: List) -> str:
        """Format key combination for display."""
        key_names = []
        for key in key_combination:
            if hasattr(key, 'name'):
                key_names.append(key.name.title())
            elif hasattr(key, 'char'):
                key_names.append(key.char.upper())
            else:
                key_names.append(str(key))
        return '+'.join(key_names)
    
    def _handle_recording_toggle(self):
        """Handle the recording toggle hotkey."""
        with self.recording_lock:
            if self.is_recording:
                logger.info("Hotkey: Stopping recording")
                self.is_recording = False
                if self.on_recording_stop:
                    self.on_recording_stop()
            else:
                logger.info("Hotkey: Starting recording")
                self.is_recording = True
                if self.on_recording_start:
                    self.on_recording_start()
        
        # Call general hotkey callback
        if self.on_hotkey_pressed:
            self.on_hotkey_pressed("record_toggle")
    
    def _on_key_press(self, key):
        """Handle key press events."""
        try:
            # Track pressed keys
            if hasattr(key, 'char') and key.char:
                self.pressed_char_keys.add(key.char.lower())
            else:
                self.pressed_keys.add(key)
            
            # Check for hotkey matches
            self._check_hotkeys()
            
        except Exception as e:
            logger.error(f"Error handling key press: {e}")
    
    def _on_key_release(self, key):
        """Handle key release events."""
        try:
            # Remove released keys from tracking
            if hasattr(key, 'char') and key.char:
                self.pressed_char_keys.discard(key.char.lower())
            else:
                self.pressed_keys.discard(key)
            
            # Handle special keys
            if key == Key.esc:
                # ESC key can be used to stop recording
                with self.recording_lock:
                    if self.is_recording:
                        logger.info("ESC pressed: Stopping recording")
                        self.is_recording = False
                        if self.on_recording_stop:
                            self.on_recording_stop()
            
        except Exception as e:
            logger.error(f"Error handling key release: {e}")
    
    def _check_hotkeys(self):
        """Check if any registered hotkeys are currently pressed."""
        current_time = time.time()
        
        for name, hotkey_info in self.hotkeys.items():
            hotkey_keys = hotkey_info['keys']
            
            # Check if all keys in the combination are currently pressed
            if self._is_hotkey_pressed(hotkey_keys):
                # Prevent rapid triggering (debounce)
                if current_time - hotkey_info['last_triggered'] > 0.5:
                    hotkey_info['last_triggered'] = current_time
                    
                    try:
                        logger.debug(f"Hotkey triggered: {name}")
                        hotkey_info['callback']()
                    except Exception as e:
                        logger.error(f"Error executing hotkey callback for '{name}': {e}")
    
    def _is_hotkey_pressed(self, hotkey_keys: Set) -> bool:
        """
        Check if all keys in a hotkey combination are currently pressed.
        
        Args:
            hotkey_keys: Set of keys that form the hotkey
            
        Returns:
            True if all keys are pressed, False otherwise
        """
        for key in hotkey_keys:
            if hasattr(key, 'char') and key.char:
                # Character key
                if key.char.lower() not in self.pressed_char_keys:
                    return False
            else:
                # Special key (modifier, etc.)
                if key not in self.pressed_keys:
                    return False
        
        return True
    
    def start_listening(self) -> bool:
        """
        Start listening for global keyboard events.
        
        Returns:
            True if listening started successfully, False otherwise
        """
        if self.is_listening:
            logger.warning("Keyboard listener is already running")
            return True
        
        try:
            self.listener = Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release
            )
            
            self.listener.start()
            self.is_listening = True
            
            logger.info("Global keyboard listener started")
            logger.info(f"Platform: {self.platform}")
            logger.info("Registered hotkeys:")
            for name, info in self.hotkeys.items():
                keys_str = self._format_hotkey(list(info['keys']))
                logger.info(f"  {name}: {keys_str} - {info['description']}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error starting keyboard listener: {e}")
            self.is_listening = False
            return False
    
    def stop_listening(self):
        """Stop listening for keyboard events."""
        if not self.is_listening:
            return
        
        try:
            if self.listener:
                self.listener.stop()
                self.listener = None
            
            self.is_listening = False
            self.pressed_keys.clear()
            self.pressed_char_keys.clear()
            
            logger.info("Global keyboard listener stopped")
            
        except Exception as e:
            logger.error(f"Error stopping keyboard listener: {e}")
    
    def get_recording_state(self) -> bool:
        """
        Get current recording state.
        
        Returns:
            True if recording, False otherwise
        """
        with self.recording_lock:
            return self.is_recording
    
    def set_recording_state(self, recording: bool):
        """
        Manually set recording state.
        
        Args:
            recording: New recording state
        """
        with self.recording_lock:
            if self.is_recording != recording:
                self.is_recording = recording
                logger.info(f"Recording state set to: {recording}")
                
                if recording and self.on_recording_start:
                    self.on_recording_start()
                elif not recording and self.on_recording_stop:
                    self.on_recording_stop()
    
    def get_hotkeys_info(self) -> Dict:
        """
        Get information about registered hotkeys.
        
        Returns:
            Dictionary with hotkey information
        """
        info = {}
        
        for name, hotkey_info in self.hotkeys.items():
            keys_str = self._format_hotkey(list(hotkey_info['keys']))
            info[name] = {
                'keys': keys_str,
                'description': hotkey_info['description'],
                'last_triggered': hotkey_info['last_triggered']
            }
        
        return info
    
    def test_hotkeys(self, duration: float = 10.0) -> List[str]:
        """
        Test hotkey detection for a specified duration.
        
        Args:
            duration: Test duration in seconds
            
        Returns:
            List of triggered hotkeys during test
        """
        triggered_hotkeys = []
        
        def test_callback(hotkey_name):
            triggered_hotkeys.append({
                'name': hotkey_name,
                'timestamp': time.time()
            })
            print(f"Hotkey triggered: {hotkey_name}")
        
        # Store original callback
        original_callback = self.on_hotkey_pressed
        self.on_hotkey_pressed = test_callback
        
        try:
            print(f"Testing hotkeys for {duration} seconds...")
            print("Press any registered hotkeys to test detection")
            
            self.start_listening()
            time.sleep(duration)
            
        finally:
            self.stop_listening()
            self.on_hotkey_pressed = original_callback
        
        return triggered_hotkeys
    
    def create_custom_hotkey(
        self,
        name: str,
        modifier: str,
        key: str,
        callback: Callable,
        description: str = ""
    ) -> bool:
        """
        Create a custom hotkey with string-based key specification.
        
        Args:
            name: Unique name for the hotkey
            modifier: Modifier key ('ctrl', 'cmd', 'alt', 'shift')
            key: Main key (single character or special key name)
            callback: Function to call when hotkey is pressed
            description: Description of the hotkey
            
        Returns:
            True if hotkey was created successfully, False otherwise
        """
        try:
            # Map modifier strings to Key objects
            modifier_map = {
                'ctrl': Key.ctrl,
                'cmd': Key.cmd,
                'alt': Key.alt,
                'shift': Key.shift
            }
            
            if modifier.lower() not in modifier_map:
                logger.error(f"Unknown modifier: {modifier}")
                return False
            
            modifier_key = modifier_map[modifier.lower()]
            
            # Handle special keys
            special_keys = {
                'space': Key.space,
                'enter': Key.enter,
                'tab': Key.tab,
                'esc': Key.esc,
                'backspace': Key.backspace,
                'delete': Key.delete,
                'home': Key.home,
                'end': Key.end,
                'page_up': Key.page_up,
                'page_down': Key.page_down,
                'up': Key.up,
                'down': Key.down,
                'left': Key.left,
                'right': Key.right
            }
            
            if key.lower() in special_keys:
                main_key = special_keys[key.lower()]
            else:
                # Regular character key
                main_key = KeyCode.from_char(key.lower())
            
            # Create hotkey
            self.add_hotkey(name, [modifier_key, main_key], callback, description)
            return True
            
        except Exception as e:
            logger.error(f"Error creating custom hotkey: {e}")
            return False


class KeyboardShortcutManager:
    """Higher-level manager for keyboard shortcuts with presets."""
    
    def __init__(self):
        """Initialize the shortcut manager."""
        self.handler = GlobalKeyboardHandler()
        self.presets = self._create_presets()
    
    def _create_presets(self) -> Dict:
        """Create predefined shortcut presets."""
        return {
            'default': {
                'record_toggle': ('ctrl' if self.handler.platform != 'darwin' else 'cmd', 'r'),
                'quick_record': ('alt', 'r')
            },
            'vim_style': {
                'record_toggle': ('ctrl', 'space'),
                'stop_record': ('esc', None)
            },
            'accessibility': {
                'record_toggle': ('ctrl', 'shift', 'm'),
                'quick_record': ('ctrl', 'q')
            }
        }
    
    def apply_preset(self, preset_name: str) -> bool:
        """
        Apply a predefined shortcut preset.
        
        Args:
            preset_name: Name of the preset to apply
            
        Returns:
            True if preset was applied successfully, False otherwise
        """
        if preset_name not in self.presets:
            logger.error(f"Unknown preset: {preset_name}")
            return False
        
        try:
            # Clear existing hotkeys
            self.handler.hotkeys.clear()
            
            # Apply preset hotkeys
            preset = self.presets[preset_name]
            
            for hotkey_name, key_combo in preset.items():
                if len(key_combo) == 2 and key_combo[1] is not None:
                    self.handler.create_custom_hotkey(
                        hotkey_name,
                        key_combo[0],
                        key_combo[1],
                        self.handler._handle_recording_toggle,
                        f"Preset {preset_name}: {hotkey_name}"
                    )
            
            logger.info(f"Applied preset: {preset_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error applying preset {preset_name}: {e}")
            return False


def create_keyboard_handler() -> GlobalKeyboardHandler:
    """
    Create and return a configured GlobalKeyboardHandler instance.
    
    Returns:
        Configured GlobalKeyboardHandler instance
    """
    return GlobalKeyboardHandler()


if __name__ == "__main__":
    # Test the keyboard handler
    print("Testing Global Keyboard Handler...")
    
    handler = GlobalKeyboardHandler()
    
    # Set up test callbacks
    def on_start():
        print("🎤 Recording started!")
    
    def on_stop():
        print("⏹️  Recording stopped!")
    
    def on_hotkey(name):
        print(f"🔥 Hotkey pressed: {name}")
    
    handler.on_recording_start = on_start
    handler.on_recording_stop = on_stop
    handler.on_hotkey_pressed = on_hotkey
    
    # Show registered hotkeys
    print("\nRegistered hotkeys:")
    hotkeys_info = handler.get_hotkeys_info()
    for name, info in hotkeys_info.items():
        print(f"  {name}: {info['keys']} - {info['description']}")
    
    # Test hotkey detection
    print(f"\nTesting on platform: {handler.platform}")
    print("Starting keyboard listener...")
    print("Press Cmd+R (macOS) or Ctrl+R (other) to toggle recording")
    print("Press ESC to stop recording")
    print("Press Ctrl+C to exit")
    
    try:
        triggered = handler.test_hotkeys(duration=30.0)
        print(f"\nTest completed. Triggered hotkeys: {len(triggered)}")
        for hotkey in triggered:
            print(f"  {hotkey['name']} at {hotkey['timestamp']}")
    
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    
    finally:
        handler.stop_listening()
        print("Keyboard handler test completed.")