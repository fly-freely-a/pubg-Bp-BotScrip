"""F 提示模板匹配，不依赖 Windows 输入接口。"""
import cv2


class InteractionPromptMatcher:
    def __init__(self, template, scales=(0.65, 0.75, 0.85, 1.0, 1.15, 1.3, 1.5, 1.75, 2.0)):
        if template is None or template.size == 0:
            raise ValueError('无法加载 F.png 交互模板，请检查 Config.IMAGE_DIR')
        gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        self.templates = []
        for scale in scales:
            resized = cv2.resize(gray, None, fx=scale, fy=scale)
            self.templates.append((scale, resized))

    def match(self, frame):
        if frame is None or frame.size == 0:
            return 0.0, None, None
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        best = (0.0, None, None)
        for scale, template in self.templates:
            h, w = template.shape[:2]
            if h > gray.shape[0] or w > gray.shape[1]:
                continue
            result = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
            _, score, _, pos = cv2.minMaxLoc(result)
            if score > best[0]:
                best = (float(score), (pos[0], pos[1], w, h), scale)
        return best
