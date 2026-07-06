import os
import sys
import unittest
from unittest.mock import MagicMock, patch

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
            import importlib

            import voice.voice_listener

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
            import importlib

            import voice.voice_listener

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


class TestVoiceListenerUtils(unittest.TestCase):
    def test_to_float(self):
        import numpy as np

        from voice.voice_listener import to_float

        # Test standard float and int
        self.assertEqual(to_float(3.14), 3.14)
        self.assertEqual(to_float(42), 42.0)

        # Test None
        self.assertEqual(to_float(None), 0.0)

        # Test numpy scalar
        self.assertAlmostEqual(to_float(np.float32(1.23)), 1.23, places=5)
        self.assertAlmostEqual(to_float(np.float64(5.67)), 5.67)

        # Test numpy 0-D array
        self.assertEqual(to_float(np.array(2.34)), 2.34)

        # Test numpy 1-element array
        self.assertEqual(to_float(np.array([4.56])), 4.56)

        # Test numpy multi-element array
        self.assertEqual(to_float(np.array([7.89, 0.12])), 7.89)

        # Test list and tuple
        self.assertEqual(to_float([3.21, 4.56]), 3.21)
        self.assertEqual(to_float((6.54, 7.89)), 6.54)

        # Test empty list and empty numpy array
        self.assertEqual(to_float([]), 0.0)
        self.assertEqual(to_float(np.array([])), 0.0)

        # Test non-convertible types
        self.assertEqual(to_float("invalid"), 0.0)


if __name__ == "__main__":
    unittest.main()
