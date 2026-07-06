import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import sys
from pathlib import Path

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set ETHERFIELDS_LOCAL_DIR to avoid relying on actual host setting during test imports/setups
os.environ["ETHERFIELDS_LOCAL_DIR"] = os.getcwd()

from voice import voice_install


class TestVoiceInstall(unittest.TestCase):

    @patch("builtins.print")
    def test_print_helpers(self, mock_print):
        voice_install.print_success("Success message")
        voice_install.print_info("Info message")
        voice_install.print_warning("Warning message")
        voice_install.print_error("Error message")
        self.assertTrue(mock_print.called)

    @patch("builtins.input", side_effect=["y", "n", ""])
    def test_ask_yes_no(self, mock_input):
        self.assertTrue(voice_install.ask_yes_no("Proceed?", default=False))
        self.assertFalse(voice_install.ask_yes_no("Proceed?", default=False))
        self.assertTrue(voice_install.ask_yes_no("Proceed?", default=True))

    @patch("builtins.input", side_effect=["custom_val", ""])
    def test_ask_input(self, mock_input):
        self.assertEqual(voice_install.ask_input("Question", "default_val"), "custom_val")
        self.assertEqual(voice_install.ask_input("Question", "default_val"), "default_val")

    @patch("urllib.request.urlopen")
    @patch("builtins.open", new_callable=mock_open)
    def test_download_file_with_progress(self, mock_file, mock_urlopen):
        mock_response = MagicMock()
        mock_response.info.return_value.get.return_value = "100"
        mock_response.read.side_effect = [b"chunk1", b"chunk2", b""]
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with patch("pathlib.Path.mkdir") as mock_mkdir:
            voice_install.download_file_with_progress("http://fake.url/file.onnx", "dummy_path")
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
            mock_file.assert_called_once_with(Path("dummy_path"), "wb")

    @patch("pathlib.Path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data="KEY1=VAL1\n# COMMENT\nKEY2 = VAL2\n")
    def test_load_env_vars(self, mock_file, mock_exists):
        vars_dict = voice_install.load_env_vars()
        self.assertEqual(vars_dict, {"KEY1": "VAL1", "KEY2": "VAL2"})

    @patch("pathlib.Path.exists", return_value=True)
    def test_save_env_vars(self, mock_exists):
        existing_data = "KEY1=VAL1\nENABLE_VOICE=False\n"
        m = mock_open(read_data=existing_data)
        with patch("builtins.open", m):
            new_vars = {"ENABLE_VOICE": "True", "NEW_VAR": "NEW_VAL"}
            voice_install.save_env_vars(new_vars)
            m.assert_any_call(voice_install.REPO_ROOT / ".env", "r", encoding="utf-8")
            m.assert_any_call(voice_install.REPO_ROOT / ".env", "w", encoding="utf-8")

    @patch("builtins.input", side_effect=[
        "1",                  # ww_choice = 1 (nanowakeword)
        "etherfields",        # wake_word = etherfields
        "1",                  # pos_choice = 1 (Record or provide your own voice clips)
        "1",                  # stt_choice = 1 (mlx-whisper)
        "1",                  # tts_choice = 1 (kokoro-onnx)
        "1",                  # narrator_gender = 1 (Male)
        "1",                  # narrator_choice = 1 (bm_george)
        "1",                  # instructor_gender = 1 (Female)
        "1",                  # instructor_choice = 1 (bf_emma)
    ])
    @patch("os.makedirs")
    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data="{% if True %}template rendered{% endif %}")
    @patch("voice.voice_install.load_env_vars", return_value={})
    @patch("voice.voice_install.save_env_vars")
    @patch("subprocess.run")
    def test_main_nanowakeword_kokoro(self, mock_subrun, mock_save_env, mock_load_env, mock_file, mock_path_exists, mock_makedirs, mock_input):
        # Mock jinja2 to avoid loading actual template from disk
        mock_jinja = MagicMock()
        mock_template = MagicMock()
        mock_template.render.return_value = "rendered custom config content"
        mock_jinja.Template.return_value = mock_template
        
        with patch.dict("sys.modules", {"jinja2": mock_jinja}):
            voice_install.main()
            mock_save_env.assert_called_once()
            mock_subrun.assert_called_once_with(["uv", "sync", "--extra", "voice"], check=True)


if __name__ == "__main__":
    unittest.main()
