import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import sys
import numpy as np

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set ETHERFIELDS_LOCAL_PATH to avoid relying on actual host setting during test imports/setups
os.environ["ETHERFIELDS_LOCAL_PATH"] = os.getcwd()

# Mock nanowakeword before importing voice_listener to ensure no issues with native libraries
mock_nanowakeword = MagicMock()
sys.modules["nanowakeword"] = mock_nanowakeword

# Mock mlx_whisper and faster_whisper before import
mock_mlx = MagicMock()
sys.modules["mlx_whisper"] = mock_mlx
mock_fw = MagicMock()
sys.modules["faster_whisper"] = mock_fw

from voice import voice_listener


class TestVoiceListener(unittest.TestCase):

    def test_to_float(self):
        # None
        self.assertEqual(voice_listener.to_float(None), 0.0)
        # numpy array
        self.assertEqual(voice_listener.to_float(np.array([1.5])), 1.5)
        self.assertEqual(voice_listener.to_float(np.array([])), 0.0)
        # list
        self.assertEqual(voice_listener.to_float([2.5]), 2.5)
        self.assertEqual(voice_listener.to_float([]), 0.0)
        # float / string
        self.assertEqual(voice_listener.to_float(3.14), 3.14)
        self.assertEqual(voice_listener.to_float("invalid"), 0.0)

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data="ETHERFIELDS_LOCAL_PATH=/dummy/dir\n")
    def test_load_env_vars(self, mock_file, mock_exists):
        vars_dict = voice_listener.load_env_vars()
        self.assertEqual(vars_dict.get("ETHERFIELDS_LOCAL_PATH"), "/dummy/dir")

    def test_nano_interpreter_wrapper(self):
        mock_model_instance = MagicMock()
        mock_model_instance.predict.return_value = {"my_model": 0.85}
        mock_nanowakeword.Model.return_value = mock_model_instance

        interpreter = voice_listener.NanoInterpreter("/dummy/path/my_model.onnx")
        self.assertEqual(interpreter.model_key, "my_model")

        # Process float32 chunk
        chunk = np.array([0.1, -0.2], dtype=np.float32)
        score = interpreter.process(chunk)
        self.assertEqual(score, 0.85)
        
        # Verify predict was called with int16 converted array
        called_arg = mock_model_instance.predict.call_args[0][0]
        self.assertEqual(called_arg.dtype, np.int16)
        
        # Test reset
        interpreter.reset()
        mock_model_instance.reset.assert_called_once()

    @patch("sounddevice.InputStream")
    @patch("soundfile.write")
    @patch("time.time", side_effect=[0, 0.5, 1.0, 1.6])  # Triggers max_duration or silence
    def test_record_question(self, mock_time, mock_sf_write, mock_input_stream):
        # Mock recording callback during __init__ call of sounddevice.InputStream
        def mock_input_stream_init(*args, **kwargs):
            callback = kwargs.get("callback")
            if callback:
                # Provide standard float32 numpy array chunk
                callback(np.array([[0.1], [0.2]], dtype=np.float32), 2, None, None)
            return MagicMock()
            
        mock_input_stream.side_effect = mock_input_stream_init

        with patch("os.system") as mock_system:
            wav_path = voice_listener.record_question(max_duration=1.5)
            self.assertTrue(wav_path.endswith("question_temp.wav"))
            mock_sf_write.assert_called_once()

    @patch("os.path.exists", return_value=True)
    @patch("os.remove")
    def test_transcribe_audio_mlx_whisper(self, mock_remove, mock_exists):
        mock_mlx.transcribe.return_value = {"text": "hello rule book"}

        with patch("voice.voice_listener._env", {"STT_PROGRAM": "mlx-whisper"}):
            text = voice_listener.transcribe_audio("dummy.wav")
            self.assertEqual(text, "hello rule book")
            mock_remove.assert_called_once_with("dummy.wav")

    @patch("os.path.exists", return_value=True)
    @patch("os.remove")
    def test_transcribe_audio_faster_whisper(self, mock_remove, mock_exists):
        mock_model = MagicMock()
        mock_segment = MagicMock()
        mock_segment.text = "hello rule book"
        mock_model.transcribe.return_value = ([mock_segment], None)

        with patch("voice.voice_listener._stt_model", mock_model):
            with patch("voice.voice_listener._env", {"STT_PROGRAM": "faster-whisper"}):
                text = voice_listener.transcribe_audio("dummy.wav")
                self.assertEqual(text, "hello rule book")
                mock_remove.assert_called_once_with("dummy.wav")

    @patch("os.path.exists", return_value=True)
    @patch("os.listdir", return_value=["req_123.json"])
    @patch("os.path.getmtime", return_value=123456)
    @patch("builtins.open", new_callable=mock_open, read_data='{"text": "speak item description"}')
    @patch("voice.voice_assistant.speak_text")
    @patch("os.remove")
    @patch("time.sleep", side_effect=InterruptedError) # break infinite worker loop
    @patch("threading.Thread")
    def test_load_narration_worker(self, mock_thread, mock_sleep, mock_remove, mock_speak, mock_file, mock_mtime, mock_listdir, mock_exists):
        import voice.voice_assistant
        sys.modules["voice_assistant"] = voice.voice_assistant

        # Run the thread's target function directly in our test thread
        voice_listener.load_narration_worker()
        target_fn = mock_thread.call_args[1]["target"]
        
        with self.assertRaises(InterruptedError):
            target_fn()
            
        mock_speak.assert_called_once_with("speak item description")
        mock_remove.assert_called_once()

    @patch("builtins.print")
    @patch("os.path.exists", return_value=True)
    @patch("os.path.isdir", return_value=True)
    @patch("os.listdir", return_value=["my_model.onnx"])
    @patch("os.path.getsize", return_value=2048)
    def test_main_list_models(self, mock_size, mock_listdir, mock_isdir, mock_exists, mock_print):
        test_args = ["voice_listener.py", "--list-models"]
        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                voice_listener.main()
            self.assertEqual(cm.exception.code, 0)
            self.assertTrue(any("my_model.onnx" in str(args) for args, kwargs in mock_print.call_args_list))


if __name__ == "__main__":
    unittest.main()
