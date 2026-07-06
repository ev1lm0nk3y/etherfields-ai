import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestAssistant(unittest.TestCase):
    def setUp(self):
        # Prevent any audio playback from actually executing
        self.play_patcher = patch("voice.voice_assistant.play_audio_file")
        self.mock_play = self.play_patcher.start()
        
        # Mock env loaded variables
        self.env_patcher = patch("voice.voice_assistant._env", {
            "TTS_ENGINE": "kokoro",
            "VOICE_REF_NARRATIVE": "bm_george",
            "VOICE_REF_INSTRUCTION": "bf_emma",
            "OPENAI_API_KEY": "fake_openai_key",
            "ELEVENLABS_API_KEY": "fake_elevenlabs_key"
        })
        self.mock_env = self.env_patcher.start()

    def tearDown(self):
        self.play_patcher.stop()
        self.env_patcher.stop()

    @patch("voice.voice_assistant.get_kokoro")
    @patch("soundfile.write")
    def test_speak_text_kokoro(self, mock_sf_write, mock_get_kokoro):
        mock_kokoro = MagicMock()
        mock_kokoro.create.return_value = ([0.1, 0.2], 22050)
        mock_get_kokoro.return_value = mock_kokoro

        import voice.voice_assistant
        result = voice.voice_assistant.speak_text_kokoro(
            "Hello World", 
            voice="bm_george", 
            output_path="test_cache.wav"
        )
        
        self.assertTrue(result)
        mock_kokoro.create.assert_called_once_with("Hello World", voice="bm_george", speed=1.0, lang="en-us")
        mock_sf_write.assert_called_once_with("test_cache.wav", [0.1, 0.2], 22050)
        self.mock_play.assert_called_once_with("test_cache.wav")

    @patch("urllib.request.urlopen")
    def test_speak_text_openai(self, mock_urlopen):
        # Mock response from OpenAI
        mock_response = MagicMock()
        mock_response.read.return_value = b"fake_mp3_data"
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # Mock open built-in to prevent file writing to disk
        with patch("builtins.open", unittest.mock.mock_open()) as mock_file:
            import voice.voice_assistant
            result = voice.voice_assistant.speak_text_openai(
                "OpenAI rules",
                voice="onyx",
                output_path="test_openai.wav"
            )

            self.assertTrue(result)
            mock_urlopen.assert_called_once()
            mock_file.assert_called_once_with("test_openai.wav", "wb")
            mock_file().write.assert_called_once_with(b"fake_mp3_data")
            self.mock_play.assert_called_once_with("test_openai.wav")

    @patch("urllib.request.urlopen")
    def test_speak_text_elevenlabs(self, mock_urlopen):
        # Mock response from ElevenLabs
        mock_response = MagicMock()
        mock_response.read.return_value = b"fake_elevenlabs_data"
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with patch("builtins.open", unittest.mock.mock_open()) as mock_file:
            import voice.voice_assistant
            result = voice.voice_assistant.speak_text_elevenlabs(
                "ElevenLabs premium",
                voice_id="pNInz6obpg7ANgFlW75D",
                output_path="test_eleven.wav"
            )

            self.assertTrue(result)
            mock_urlopen.assert_called_once()
            mock_file.assert_called_once_with("test_eleven.wav", "wb")
            mock_file().write.assert_called_once_with(b"fake_elevenlabs_data")
            self.mock_play.assert_called_once_with("test_eleven.wav")

    def test_clean_script_text(self):
        import voice.voice_assistant
        dirty = "**Hello** {1.5s} World `code` {0.5s}!"
        clean = voice.voice_assistant.clean_script_text(dirty)
        self.assertEqual(clean, "Hello World code !")

if __name__ == "__main__":
    unittest.main()
