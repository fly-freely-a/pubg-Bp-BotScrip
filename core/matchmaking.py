"""识别排队提示中的固定文字，排除计时器和动画。"""
from core.interaction import InteractionPromptMatcher


class QueuePromptMatcher(InteractionPromptMatcher):
    def __init__(self, template):
        if template is None or template.size == 0:
            raise ValueError('无法加载 start_matching.png，请检查 Config.IMAGE_DIR')
        h, w = template.shape[:2]
        # 此资源包含计时器、动画和取消按钮，仅使用固定的“开始匹配”文字。
        label = template[int(h * 0.18):int(h * 0.50), int(w * 0.26):int(w * 0.45)]
        super().__init__(label, scales=(0.25, 0.33, 0.4, 0.5, 0.6, 0.75, 1.0, 1.25))
