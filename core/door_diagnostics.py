"""后台保存开门诊断，避免编码和磁盘写入阻塞操作循环。"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
from pathlib import Path
from uuid import uuid4

import cv2


class DoorDiagnosticRecorder:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.pending = None

    def submit(self, frame, metadata):
        if self.pending is not None:
            if not self.pending.done():
                return False  # 不积压过时画面。
            self._report_result()
        self.pending = self.executor.submit(self._save, frame.copy(), metadata.copy())
        return True

    def _save(self, frame, metadata):
        self.directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.fromtimestamp(metadata['captured_at']).strftime('%Y%m%d_%H%M%S_%f')
        stem = f'{stamp}_{uuid4().hex[:8]}'
        ok, encoded = cv2.imencode('.png', frame)
        if not ok:
            raise RuntimeError('原始画面编码失败')
        # 微秒时间戳加唯一后缀；排他创建，绝不覆盖旧截图。
        image_path = self.directory / f'{stem}.png'
        with image_path.open('xb') as f:
            f.write(encoded.tobytes())
        metadata['image_file'] = image_path.name
        with (self.directory / f'{stem}.json').open('x', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    def _report_result(self):
        try:
            self.pending.result()
        except Exception as e:
            print(f'⚠️ [开门诊断] 保存失败:{e}')

    def close(self):
        self.executor.shutdown(wait=True)
        if self.pending is not None:
            self._report_result()
