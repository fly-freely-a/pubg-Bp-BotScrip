import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from core.live_logs import LiveLogs, LogBuffer, Tee


class LiveLogTests(unittest.TestCase):
    def test_cr_and_stderr_style_chunks_persist_and_keep_terminal_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'test.log'
            buffer = LogBuffer(path, capacity=2)
            original = io.StringIO()
            tee = Tee(original, buffer)
            tee.write('进度1\r进度2\n半')
            tee.write('行\n')
            tee.finish()
            self.assertEqual(original.getvalue(), '进度1\r进度2\n半行\n')
            snapshot = buffer.snapshot(0)
            self.assertEqual(len(snapshot['entries']), 2)
            self.assertTrue(snapshot['entries'][-1]['text'].endswith('半行'))
            self.assertTrue(buffer.snapshot(0)['cursor'] == 3)
            self.assertTrue(buffer.snapshot(0)['entries'][0]['id'] == 2)
            # Persisted file contains even the lines evicted from the memory buffer.
            self.assertIn('进度1', path.read_text())
            self.assertIn('半行', path.read_text())
            buffer.file.close()

    def test_cursor_only_returns_new_lines_and_reports_lost_history(self):
        with tempfile.TemporaryDirectory() as directory:
            buffer = LogBuffer(Path(directory) / 'test.log', capacity=2)
            for line in ('a', 'b', 'c', 'd'):
                buffer.append(line)
            self.assertTrue(buffer.snapshot(1)['truncated'])
            self.assertEqual([e['id'] for e in buffer.snapshot(3)['entries']], [4])
            self.assertEqual(buffer.snapshot(4)['entries'], [])
            buffer.file.close()

    def test_http_serves_live_logs_only_and_restores_streams(self):
        with tempfile.TemporaryDirectory() as directory:
            stdout, stderr = sys.stdout, sys.stderr
            service = LiveLogs(directory, host='127.0.0.1', port=0)
            try:
                self.assertIsNotNone(service.server)
                base = f'http://127.0.0.1:{service.server.server_port}'
                print('测试输出')
                print('测试错误', file=sys.stderr)
                with urlopen(base + '/logs?after=0', timeout=2) as response:
                    data = json.load(response)
                text = '\n'.join(e['text'] for e in data['entries'])
                self.assertIn('测试输出', text)
                self.assertIn('测试错误', text)
                with urlopen(base, timeout=2) as response:
                    self.assertIn('暂停滚动', response.read().decode())
                for path, code in (('/config.py', 404), ('/logs?after=invalid', 400)):
                    with self.assertRaises(HTTPError) as error:
                        urlopen(base + path, timeout=2)
                    self.assertEqual(error.exception.code, code)
            finally:
                service.close()
            self.assertIs(sys.stdout, stdout)
            self.assertIs(sys.stderr, stderr)
            self.assertIn('测试输出', service.path.read_text())
