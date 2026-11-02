"""Read-only LAN log viewer; uses only the Python standard library."""
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import sys
import threading
from urllib.parse import parse_qs, urlsplit


PAGE = r'''<!doctype html><meta charset="utf-8"><title>脚本实时日志</title>
<style>body{background:#141820;color:#e6edf3;font:14px monospace;margin:20px}
header{position:sticky;top:0;background:#141820;padding:10px 0}button{margin-right:10px}
pre{white-space:pre-wrap;overflow-wrap:anywhere}#status{color:#a6c8ff}</style>
<header><button id="scroll">暂停滚动</button><button id="copy">复制当前日志</button>
<span id="status">连接中…</span></header><pre id="logs"></pre>
<script>
let cursor=0, autoScroll=true, lines=[];
const output=document.getElementById('logs'), status=document.getElementById('status');
document.getElementById('scroll').onclick=function(){autoScroll=!autoScroll;this.textContent=autoScroll?'暂停滚动':'恢复滚动'};
document.getElementById('copy').onclick=async()=>{
 const text=lines.join('\n');
 try{await navigator.clipboard.writeText(text);status.textContent='已复制'}
 catch(e){const t=document.createElement('textarea');t.value=text;document.body.append(t);t.select();
 status.textContent=document.execCommand('copy')?'已复制':'请手动选择日志复制';t.remove()}
};
async function poll(){
 try{
  const response=await fetch('/logs?after='+cursor,{cache:'no-store'});
  if(!response.ok)throw new Error(response.status);
  const data=await response.json();
  if(data.truncated)lines.push('[日志提示] 部分较早日志已滚出缓存，完整记录见游戏电脑日志文件');
  for(const entry of data.entries)lines.push(entry.text);
  cursor=data.cursor;lines=lines.slice(-2000);output.textContent=lines.join('\n');
  status.textContent='已连接 · 每0.5秒刷新';if(autoScroll)window.scrollTo(0,document.body.scrollHeight);
 }catch(e){status.textContent='连接中断，正在重试…'}
 setTimeout(poll,500);
}poll();
</script>'''


class LogBuffer:
    def __init__(self, path, capacity=2000):
        self.entries = deque(maxlen=capacity)
        self.sequence = 0
        self.lock = threading.Lock()
        self.file = Path(path).open('x', encoding='utf-8')

    def append(self, line):
        text = datetime.now().strftime('%H:%M:%S.%f')[:-3] + ' ' + line
        with self.lock:
            self.sequence += 1
            self.entries.append(dict(id=self.sequence, text=text))
            self.file.write(text + '\n')
            self.file.flush()  # END uses os._exit(), so persist every completed line.

    def snapshot(self, after=0):
        with self.lock:
            entries = [entry.copy() for entry in self.entries if entry['id'] > after]
            return dict(entries=entries, cursor=self.sequence,
                        truncated=bool(self.entries and after and after < self.entries[0]['id'] - 1))


class Tee:
    def __init__(self, original, buffer):
        self.original, self.buffer = original, buffer
        self.pending = ''
        self.lock = threading.RLock()

    def write(self, text):
        with self.lock:
            result = self.original.write(text)
            self.pending += text.replace('\r', '\n')
            while '\n' in self.pending:
                line, self.pending = self.pending.split('\n', 1)
                if line:
                    self.buffer.append(line)
            # Bound unfinished lines as well as completed-line history.
            if len(self.pending) > 16384:
                self.buffer.append(self.pending[:16384])
                self.pending = self.pending[16384:]
            return result

    def flush(self):
        self.original.flush()

    def finish(self):
        with self.lock:
            if self.pending:
                self.buffer.append(self.pending)
                self.pending = ''
            self.original.flush()

    def __getattr__(self, name):
        return getattr(self.original, name)


def make_handler(buffer):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urlsplit(self.path)
            if url.path == '/':
                content, mime = PAGE.encode('utf-8'), 'text/html; charset=utf-8'
            elif url.path == '/logs':
                try:
                    after = max(0, int(parse_qs(url.query).get('after', ['0'])[0]))
                except ValueError:
                    self.send_error(400)
                    return
                content = json.dumps(buffer.snapshot(after), ensure_ascii=False).encode('utf-8')
                mime = 'application/json; charset=utf-8'
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, *args):
            pass  # Never send browser polling requests back into the log stream.
    return Handler


class LiveLogs:
    def __init__(self, directory, host='0.0.0.0', port=8765):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / (datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.log')
        self.buffer = LogBuffer(self.path)
        self.stdout = Tee(sys.stdout, self.buffer)
        self.stderr = Tee(sys.stderr, self.buffer)
        self.server = None
        sys.stdout, sys.stderr = self.stdout, self.stderr
        try:
            self.server = ThreadingHTTPServer((host, port), make_handler(self.buffer))
            threading.Thread(target=self.server.serve_forever, daemon=True).start()
        except OSError as error:
            print(f'[日志] 网页启动失败:{error}；终端和文件记录继续工作。')
        print(f'[日志] 本次完整日志:{self.path}')
        if self.server is not None:
            addresses = {'127.0.0.1'}
            try:
                addresses.update(socket.gethostbyname_ex(socket.gethostname())[2])
            except OSError:
                pass
            for address in sorted(addresses):
                if address != '0.0.0.0':
                    print(f'[日志] 浏览器地址:http://{address}:{self.server.server_port}')
            print('[日志] 其他电脑请使用游戏电脑的局域网 IPv4 地址；网页仅供查看日志。')

    def close(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        self.stdout.finish()
        self.stderr.finish()
        sys.stdout, sys.stderr = self.stdout.original, self.stderr.original
        self.buffer.file.close()
