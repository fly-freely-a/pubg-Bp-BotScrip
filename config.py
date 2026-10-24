# pubg2/config.py

class Config:
    # --- 路径配置 ---
    IMAGE_DIR = r"E:\pythonDemo\pubg\image"
    MODEL_PATH = r"E:\pythonDemo\aipubg\runs\detect\pubg_toilet_model-7\weights\best.engine"

    # --- 游戏参数 ---
    REF_WIDTH = 1000
    REF_HEIGHT = 1000
    MAP_SIZE = 1050
    JUMP_DISTANCE_THRESHOLD = 150
    NEAR_TARGET_SEARCH_DISTANCE = 5.0  # 归一化截图中小地图像素距离，非游戏米数
    SECONDARY_PASSWORD = "131932"  # 例如"你的二级密码"
    # --- 精确跳伞点位 ---
    TARGET_POINTS = [
        {"id": 1, "x": 544, "y": 577, "name": "精确厕所_1"},
        {"id": 2, "x": 529, "y": 211, "name": "精确厕所_2"},
        {"id": 3, "x": 645, "y": 465, "name": "精确厕所_3"},
        {"id": 4, "x": 596, "y": 508, "name": "精确厕所_4"},
        {"id": 5, "x": 662, "y": 412, "name": "精确厕所_5"},
        {"id": 6, "x": 312, "y": 626, "name": "精确厕所_6"},
        {"id": 8, "x": 305, "y": 163, "name": "精确厕所_8"},
        {"id": 9, "x": 339, "y": 161, "name": "精确厕所_9"},
    ]

    # --- 视觉模板匹配阈值 ---
    THRESHOLDS = {
        'start_btn': 0.75, 'loading': 0.85, 'count4': 0.65,
        'user': 0.4, 'feiji': 0.55, 'target': 0.65,
        'naozhong': 0.70, 'leave_game': 0.65,
        'password': 0.88,'err':0.80,'confirm2':0.80,
        'back': 0.8, 'next': 0.80, 'confirm': 0.80, 'close': 0.80
    }

