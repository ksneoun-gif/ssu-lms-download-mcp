import json
import contextlib
import io
from unittest.mock import patch, Mock
import bootstrap
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from install_windows import configuration, configure

class WindowsConfigurationTests(unittest.TestCase):
    def test_missing_server_is_rejected(self):
        with TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                configuration(Path(directory),Path(__file__))

    def test_direct_python_and_both_manifests(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);(root/'server.py').touch();python=root/'python.exe';python.touch()
            config=configuration(root,python)
            configure(root,config)
            server=config['mcpServers']['ssu-lms']
            self.assertEqual(server['command'],str(python.resolve()))
            self.assertEqual(server['args'],['-u',str(root.resolve()/'server.py')])
            self.assertEqual((root/'.mcp.json').read_bytes(),(root/'mcp.json').read_bytes())
            self.assertEqual(json.loads((root/'.mcp.json').read_text()),config)

    def test_original_config_backup_is_not_overwritten(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);(root/'.mcp.json').write_text('original')
            configure(root,{'first':True});configure(root,{'second':True})
            self.assertEqual((root/'.mcp.json.before-windows-setup').read_text(),'original')
            self.assertEqual(json.loads((root/'.mcp.json').read_text()),{'second':True})
            self.assertFalse(list(root.glob('*.new')))

    def test_existing_environment_is_not_recreated(self):
        with TemporaryDirectory() as directory:
            python=bootstrap.environment_python(Path(directory))
            python.parent.mkdir(parents=True);python.touch()
            with patch.dict('bootstrap.os.environ',{'SSU_LMS_ENV':directory}), patch('sys.argv',['bootstrap.py','--setup','--check']), patch('bootstrap.missing_modules',return_value=[]), patch('bootstrap.subprocess.run') as run, patch('importlib.util.find_spec',return_value=Mock()), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(bootstrap.main(),0)
            self.assertEqual(len(run.call_args_list),1)
            self.assertIn('pip',run.call_args.args[0])
            self.assertNotIn('venv',run.call_args.args[0])

    def test_distributed_setup_files_match(self):
        root=Path(__file__).resolve().parent
        for name in ('start.ps1','install_windows.py','verify_local.py','bootstrap.py'):
            self.assertEqual((root/name).read_bytes(),(root/'plugins/ssu-lms'/name).read_bytes())

if __name__=='__main__':
    unittest.main()
