import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSTT(unittest.TestCase):
    @patch("voice.voice_listener.os.path.exists")
    @patch("voice.voice_listener.os.remove")
    def test_transcribe_audio_mlx(self, mock_remove, mock_exists):
        mock_exists.return_value = True

        # Mock mlx_whisper library
        mock_mlx = MagicMock()
        mock_mlx.transcribe.return_value = {"text": "Hello Etherfields"}

        with patch.dict("sys.modules", {"mlx_whisper": mock_mlx}):
            # Import and reload to ensure clean slate
            import voice.voice_listener
            import importlib

            importlib.reload(voice.voice_listener)

            # Manually mock module-level env
            voice.voice_listener._env = MagicMock()
            voice.voice_listener._env.get.return_value = "mlx-whisper"

            result = voice.voice_listener.transcribe_audio("dummy.wav")

            # Assertions
            self.assertEqual(result, "Hello Etherfields")
            mock_mlx.transcribe.assert_called_once_with(
                "dummy.wav", path_or_hf_repo="mlx-community/whisper-large-v3-turbo"
            )
            mock_remove.assert_called_once_with("dummy.wav")

    @patch("voice.voice_listener.os.path.exists")
    @patch("voice.voice_listener.os.remove")
    def test_transcribe_audio_faster_whisper(self, mock_remove, mock_exists):
        mock_exists.return_value = True

        # Mock WhisperModel
        mock_model = MagicMock()
        mock_segment = MagicMock()
        mock_segment.text = "Hello World"
        mock_model.transcribe.return_value = ([mock_segment], None)

        mock_model_class = MagicMock(return_value=mock_model)
        mock_fw_module = MagicMock()
        mock_fw_module.WhisperModel = mock_model_class

        with patch.dict("sys.modules", {"faster_whisper": mock_fw_module}):
            import voice.voice_listener
            import importlib

            importlib.reload(voice.voice_listener)

            # Reset global variable and manually mock env
            voice.voice_listener._stt_model = None
            voice.voice_listener._env = MagicMock()
            voice.voice_listener._env.get.return_value = "faster-whisper"

            result = voice.voice_listener.transcribe_audio("dummy.wav")

            # Assertions
            self.assertEqual(result, "Hello World")
            mock_model_class.assert_called_once_with(
                "Systran/faster-whisper-medium.en",
                device="cpu",
                compute_type="int8",
                download_root=unittest.mock.ANY,
            )
            mock_model.transcribe.assert_called_once_with("dummy.wav", beam_size=5)
            mock_remove.assert_called_once_with("dummy.wav")


if __name__ == "__main__":
    unittest.main()
