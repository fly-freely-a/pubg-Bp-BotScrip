# pubg2/core/mixins.py
import os
import time
import math
import cv2
import numpy as np
from PIL import ImageGrab
import win32gui
import win32con
import win32api
import pyautogui
import pydirectinput


class WindowMixin:
    """处理Windows窗口与屏幕截图的底层组件"""

    def bring_pubg_to_front(self):
        """
        强行将游戏窗口推到最前台，绕过 Windows 防抢焦点机制
        """
        import win32gui
        import win32con
        import win32api
        import time

        # 1. 🌟 寻找游戏窗口：保留你原本精准的寻找逻辑（带空格的标题）
        hwnd = win32gui.FindWindow(None, "PUBG：绝地求生 ")
        if not hwnd:
            hwnd = win32gui.FindWindow("UnrealWindow", "PUBG：绝地求生 ")

        if not hwnd:
            print("❌ 找不到游戏窗口，请确认游戏是否已启动！")
            return False

        # 记录当前游戏句柄
        self.pubg_hwnd = hwnd

        try:
            # 2. 如果当前已经在最前面，直接返回，不浪费时间
            current_fg = win32gui.GetForegroundWindow()
            if current_fg == hwnd:
                return True

            # 3. 🌟 核心黑魔法：模拟按下 Alt 键，欺骗 Windows 开放焦点权限
            # (弃用 pyautogui，改用更底层、防屏蔽的 win32api)
            win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
            win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
            time.sleep(0.05)

            # 4. 判断窗口状态：如果被最小化了，必须先恢复，否则置顶会崩溃
            placement = win32gui.GetWindowPlacement(hwnd)
            if placement[1] == win32con.SW_SHOWMINIMIZED:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.2)

            # 5. 现在可以安全、合法地强行置顶了！
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.1)
            return True

        except Exception as e:
            print(f"\n⚠️ 常规置顶被系统拦截，启动备用强拉方案: {e}")
            try:
                # 6. 备用强拉方案：利用 TopMost 属性强行在屏幕最顶层画出来，再取消 TopMost
                win32gui.ShowWindow(hwnd, win32con.SW_SHOWNOACTIVATE)
                win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                                      win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
                win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                                      win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
                return True
            except:
                pass
            return False
    def capture_game_screen(self):
        if not self.pubg_hwnd or win32gui.IsIconic(self.pubg_hwnd):
            return None, None
        try:
            win_rect = win32gui.GetWindowRect(self.pubg_hwnd)
            client_rect = win32gui.GetClientRect(self.pubg_hwnd)
            client_w, client_h = client_rect[2], client_rect[3]

            # 🛡️ 防御 1：防止窗口极度缩小或消失时导致的宽高为 0
            if client_w <= 0 or client_h <= 0:
                return None, None

            border_x = (win_rect[2] - win_rect[0] - client_w) // 2
            border_y = (win_rect[3] - win_rect[1] - client_h) - border_x
            screenshot = ImageGrab.grab(bbox=win_rect)

            # 🛡️ 防御 2：防止截图失败返回 None 导致 np.array 报错
            if screenshot is None:
                return None, None

            full_img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            raw_game_img = full_img[border_y:border_y + client_h, border_x:border_x + client_w]

            # 🛡️ 防御 3 (终极装甲)：物理内存与图像维度严格校验！
            # 凡是尺寸为0，或者不是3通道彩色图的畸形数据，全部拦截！
            if raw_game_img is None or raw_game_img.size == 0 or len(raw_game_img.shape) != 3:
                return None, None

            virtual_w, virtual_h = 1920, 1080
            if client_w != virtual_w or client_h != virtual_h:
                game_img = cv2.resize(raw_game_img, (virtual_w, virtual_h), interpolation=cv2.INTER_AREA)
            else:
                game_img = raw_game_img

            window_info = {
                'screen_pos': (win_rect[0], win_rect[1]),
                'border': (border_x, border_y),
                'real_client_size': (client_w, client_h),
                'game_size': (virtual_w, virtual_h),
                'map_offset': ((virtual_w - self.MAP_SIZE) // 2, (virtual_h - self.MAP_SIZE) // 2),
            }
            return game_img, window_info

        except Exception as e:
            # 即使发生意外，也安全地返回 None，绝不让程序崩溃
            return None, None

    def _get_desktop_handles(self):
        """内部方法：精确获取桌面相关的所有底层窗口句柄"""
        import win32gui
        hwnd_progman = win32gui.FindWindow("Progman", "Program Manager")

        # 1. 正常情况
        hwnd_shelldll = win32gui.FindWindowEx(hwnd_progman, 0, "SHELLDLL_DefView", None)
        if hwnd_shelldll:
            hwnd_lv = win32gui.FindWindowEx(hwnd_shelldll, 0, "SysListView32", None)
            return hwnd_lv, hwnd_progman, hwnd_shelldll

        # 2. 幽灵窗口情况 (如使用了动态壁纸)
        hwnd_workerw = 0
        while True:
            hwnd_workerw = win32gui.FindWindowEx(0, hwnd_workerw, "WorkerW", None)
            if not hwnd_workerw:
                break
            hwnd_shelldll = win32gui.FindWindowEx(hwnd_workerw, 0, "SHELLDLL_DefView", None)
            if hwnd_shelldll:
                hwnd_lv = win32gui.FindWindowEx(hwnd_shelldll, 0, "SysListView32", None)
                return hwnd_lv, hwnd_progman, hwnd_shelldll

        return 0, 0, 0

    def toggle_desktop_icons(self, show=True):
        """
        🛡️ 防误触装甲：双重打击机制动态显示/隐藏桌面图标
        """
        import win32gui
        import win32con
        import time
        try:
            hwnd_lv, hwnd_progman, hwnd_shelldll = self._get_desktop_handles()
            if not hwnd_lv:
                return

            # 判断当前状态
            is_visible = win32gui.IsWindowVisible(hwnd_lv)
            if bool(is_visible) == bool(show):
                return  # 状态一致，不需要做任何操作

            # ⚔️ 第一击：常规发送
            win32gui.SendMessage(hwnd_progman, win32con.WM_COMMAND, 0x7402, 0)
            time.sleep(0.3)

            # ⚔️ 第二击：如果被拦截，强攻底层模块
            if bool(win32gui.IsWindowVisible(hwnd_lv)) != bool(show):
                win32gui.SendMessage(hwnd_shelldll, win32con.WM_COMMAND, 0x7402, 0)
                time.sleep(0.3)

        except Exception as e:
            print(f"⚠️ 切换桌面图标状态失败: {e}")

class VisionMixin:
    """处理OpenCV与底层识图的组件"""

    def _load_img(self, filename):
        path = os.path.join(self.image_dir, filename)
        if not os.path.exists(path):
            return None
        return cv2.imread(path)

    # 🌟 新增 custom_thresh 参数，允许外部临时覆盖默认阈值
    def find_image(self, screen, template_name, custom_thresh=None):
        # 动态懒加载新增的 confirm2.png
        if template_name == 'confirm2' and not hasattr(self, 'confirm2_template'):
            self.confirm2_template = self._load_img('confirm2.png')

        templates = {
            'start_btn': getattr(self, 'start_btn_template', None),
            'loading': getattr(self, 'loading_template', None),
            'count4': getattr(self, 'count4_template', None),
            'target': getattr(self, 'target_template', None),
            'naozhong': getattr(self, 'naozhong_template', None),
            'leave_game': getattr(self, 'leave_game_template', None),
            'password': getattr(self, 'password_template', None),
            'err': getattr(self, 'err_template', None),
            'back': getattr(self, 'back_template', None),
            'next': getattr(self, 'next_template', None),
            'confirm': getattr(self, 'confirm_template', None),
            'confirm2': getattr(self, 'confirm2_template', None),
            'close': getattr(self, 'close_template', None),
            'cancel': getattr(self, 'cancel_template', None)
            }
        template = templates.get(template_name)
        if screen is None or template is None: return False, 0.0, None

        try:
            result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            # 🌟 核心逻辑：如果有临时传入的阈值就用传入的，否则用字典配置的，最后默认 0.8
            if custom_thresh is not None:
                thresh = custom_thresh
            elif hasattr(self, 'thresholds'):
                thresh = self.thresholds.get(template_name, 0.8)
            else:
                thresh = 0.8

            if max_val > 0.2:
                if template_name in ['count4', 'naozhong', 'start_btn', 'password']:
                    print(f"   🔍 识图监控: {template_name} 得分:{max_val:.4f} (当前设定阈值:{thresh:.2f})",
                            end="\r", flush=True)
            if max_val >= thresh:
                h, w = template.shape[:2]
                if template_name in ['count4', 'back', 'confirm', 'confirm2', 'password']:
                    print(f"\n   🎯 精准命中目标: {template_name} (得分:{max_val:.4f})")
                return True, float(max_val), (int(max_loc[0] + w // 2), int(max_loc[1] + h // 2))
            return False, float(max_val), None
        except Exception:
            return False, 0.0, None

    def find_image_in_map(self, map_img, template_name, custom_thresh=None):
        templates = {'user': self.user_template, 'feiji': self.feiji_template}
        template = templates.get(template_name)
        thresh = custom_thresh if custom_thresh else self.thresholds.get(template_name, 0.7)
        if map_img is None or template is None: return False, 0.0, None
        try:
            h, w = template.shape[:2]
            result = cv2.matchTemplate(map_img, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val >= thresh:
                return True, float(max_val), (int(max_loc[0] + w // 2), int(max_loc[1] + h // 2))
            return False, float(max_val), None
        except Exception:
            return False, 0.0, None

    def find_user_on_map(self, map_img):
        if map_img is None: return False, None, 0.0, None

        # 1. 尝试常规识图 (快速匹配)
        found, conf, pos = self.find_image_in_map(map_img, 'user', 0.6)
        if found: return True, pos, conf, 'template'

        # 2. 🌟 既然识图不稳，直接提取你图片中的“黄色圆圈”或“中心白点”
        try:
            hsv = cv2.cvtColor(map_img, cv2.COLOR_BGR2HSV)

            # 针对你图片中的黄色圆圈 (队友/自身高亮色)
            lower_yellow = np.array([20, 100, 100])
            upper_yellow = np.array([30, 255, 255])
            mask = cv2.inRange(hsv, lower_yellow, upper_yellow)

            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for cnt in contours:
                area = cv2.contourArea(cnt)
                # 严格限制面积，只找圆圈大小的物体，过滤掉地图大面积黄色块
                if 50 < area < 400:
                    x, y, w, h = cv2.boundingRect(cnt)
                    # 比例校验：User图标接近正方形
                    if 0.8 < (w / h) < 1.2:
                        cx, cy = x + w // 2, y + h // 2
                        return True, (cx, cy), 0.9, 'color_logic'
        except Exception:
            pass

        return False, None, 0.0, None

    def extract_flight_path_v2(self, map_img):
        if map_img is None or len(map_img) == 0: return []
        try:
            hsv = cv2.cvtColor(map_img, cv2.COLOR_BGR2HSV)
            mask1 = cv2.inRange(hsv, np.array([0, 100, 100]), np.array([8, 255, 255]))
            mask2 = cv2.inRange(hsv, np.array([170, 100, 100]), np.array([180, 255, 255]))
            red_mask = mask1 | mask2
            kernel = np.ones((5, 5), np.uint8)
            red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel, iterations=3)
            points = cv2.findNonZero(red_mask)
            if points is not None and len(points) > 50:
                return [(int(p[0][0]), int(p[0][1])) for p in points]
            return []
        except Exception:
            return []

    def find_target_on_compass(self, game_img):
        if game_img is None: return None
        h, w = game_img.shape[:2]
        start_x, end_x = int(w * 0.25), int(w * 0.75)
        roi = game_img[0:int(h * 0.038), start_x:end_x]
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array([20, 150, 150]), np.array([35, 255, 255]))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            largest = max(contours, key=cv2.contourArea)
            if cv2.contourArea(largest) > 5:
                M = cv2.moments(largest)
                if M['m00'] > 0: return int(M['m10'] / M['m00']) + start_x
        return None


class MathMixin:
    """处理坐标转换与几何测算的组件"""
    def transform_coordinates(self, ref_x, ref_y):
        scale_x = self.MAP_SIZE / self.ref_width
        scale_y = self.MAP_SIZE / self.ref_height
        return int(ref_x * scale_x), int(ref_y * scale_y)
    def find_best_target(self, flight_path):
        if not flight_path or len(flight_path) < 50:
            return self.target_points[0], self.transform_coordinates(self.target_points[0]['x'],
                                                                     self.target_points[0]['y']), 9999
        results = []
        for target in self.target_points:
            map_x, map_y = self.transform_coordinates(target['x'], target['y'])
            min_dist = float('inf')
            step = max(1, len(flight_path) // 300)
            for i in range(0, len(flight_path), step):
                px, py = flight_path[i]
                d = math.sqrt((map_x - px) ** 2 + (map_y - py) ** 2)
                if d < min_dist: min_dist = d
            results.append({'target': target, 'coords': (map_x, map_y), 'distance': min_dist})
        results.sort(key=lambda x: x['distance'])
        best_choice = results[0]
        jumpable_targets = [r for r in results if r['distance'] <= self.jump_distance_threshold]
        if len(jumpable_targets) > 1:
            for r in jumpable_targets:
                if r['target']['name'] != "精确厕所_1":
                    best_choice = r
                    break
        print(f"   ✅ 测距完毕，选择跳伞区域: {best_choice['target']['name']} (理论距离={best_choice['distance']:.1f}px)")
        return best_choice['target'], best_choice['coords'], best_choice['distance']

    def convert_to_screen(self, map_coords, window_info):
        if window_info is None or map_coords is None: return None, None
        win_x, win_y = window_info['screen_pos']
        bor_x, bor_y = window_info['border']
        off_x, off_y = window_info['map_offset']
        virtual_x = off_x + map_coords[0]
        virtual_y = off_y + map_coords[1]
        real_w, real_h = window_info['real_client_size']
        real_x = int(virtual_x * (real_w / 1920.0))
        real_y = int(virtual_y * (real_h / 1080.0))
        return int(win_x + bor_x + real_x), int(win_y + bor_y + real_y)

    def virtual_to_real_screen(self, virtual_x, virtual_y, window_info):
        if window_info is None or virtual_x is None or virtual_y is None: return None, None
        win_x, win_y = window_info['screen_pos']
        bor_x, bor_y = window_info['border']
        real_w, real_h = window_info['real_client_size']
        real_x = int(virtual_x * (real_w / 1920.0))
        real_y = int(virtual_y * (real_h / 1080.0))
        return int(win_x + bor_x + real_x), int(win_y + bor_y + real_y)

    def get_next_dense_target(self):
        if hasattr(self, 'current_target_id'):
            self.target_points = [t for t in self.target_points if t['id'] != self.current_target_id]
        if not self.target_points: return None
        curr_x, curr_y = self.initial_target_coords
        best_target = None
        max_neighbors = -1
        min_dist_to_us = float('inf')
        neighbor_radius = 250.0
        for t in self.target_points:
            t_map_x, t_map_y = self.transform_coordinates(t['x'], t['y'])
            dist_from_us = math.sqrt((t_map_x - curr_x) ** 2 + (t_map_y - curr_y) ** 2)
            neighbors = 0
            for other_t in self.target_points:
                if other_t['id'] != t['id']:
                    o_map_x, o_map_y = self.transform_coordinates(other_t['x'], other_t['y'])
                    if math.sqrt((o_map_x - t_map_x) ** 2 + (o_map_y - t_map_y) ** 2) <= neighbor_radius:
                        neighbors += 1
            if neighbors > max_neighbors:
                max_neighbors = neighbors
                min_dist_to_us = dist_from_us
                best_target = t
            elif neighbors == max_neighbors:
                if dist_from_us < min_dist_to_us:
                    min_dist_to_us = dist_from_us
                    best_target = t
        return best_target


class ActionMixin:
    """处理键鼠执行与原子动作的组件"""

    def force_restart_pubg(self):
        import os
        import time
        print("\n" + "!" * 60)
        print("🚨 [看门狗警报] 游戏陷入死锁或掉线！启动【物理拔管重连】协议！")
        print("!" * 60)

        # 1. 灭霸级强杀
        print("   🔪 正在强杀游戏本体与所有反作弊引擎...")
        kill_list = [
            "TslGame.exe", "ExecPubg.exe", "TslGame_BE.exe",
            "BEService.exe", "zksvc.exe", "ucldr_battlegrounds_gl.exe", "wellbia.exe"
        ]
        for proc in kill_list:
            os.system(f"taskkill /F /IM {proc} /T >nul 2>&1")

        print("   🧹 内存清理完毕，等待残留句柄释放...")
        time.sleep(8)

        # 2. 重新拉起
        print("   🚀 正在通过 Steam 协议重新拉起绝地求生...")
        os.startfile("steam://rungameid/578080")

        # =========================================================
        # 🌟 3. 核心升级：动态视觉唤醒雷达 (最多等150秒，好了就提前出仓)
        # =========================================================
        print("   👁️ 开启【动态视觉雷达】侦测画面，告别死等...")
        is_game_ready = False

        # 循环 75 次，每次休息 2 秒，最多 150 秒
        for i in range(75):
            time.sleep(2)

            # 尝试把游戏拉到前台，如果成功说明窗口已经创建出来了
            if self.bring_pubg_to_front():
                # 尝试抓取游戏画面
                game_img, _ = self.capture_game_screen()

                if game_img is not None:
                    # 用视觉检测是否出现了特定标志！
                    # 如果看到了“二级密码”、“大厅开始按钮”、或者“Loading黑屏”任何一个
                    f_pw, _, _ = self.find_image(game_img, 'password')
                    f_start, _, _ = self.find_image(game_img, 'start_btn')
                    f_load, _, _ = self.find_image(game_img, 'loading')

                    if f_pw or f_start or f_load:
                        print(f"\n   🎯 破壳成功！在第 {i * 2 + 2} 秒侦测到游戏画面已就绪！提前打断休眠！")
                        is_game_ready = True
                        break  # 🌟 核心：立刻跳出循环，不再等待！

            print(f"   ⏳ ... 游戏仍在加载中 (已等待 {i * 2 + 2}/150 秒) ...", end="\r")

        if not is_game_ready:
            print("\n   ⚠️ 150秒到达极限，强制结束等待，交由主循环接管！")

        # 4. 夺回焦点与清理
        print("   🔄 尝试重新接管游戏窗口焦点...")
        self.bring_pubg_to_front()

        # 狂按 ESC 清理赛季弹窗
        import pydirectinput
        for _ in range(5):
            pydirectinput.press('esc')
            time.sleep(1.0)

        print("   ✅ 重连抢救流程执行完毕，交还控制权给主循环！")
    def handle_password_input(self, game_img, window_info):
        """
        处理房间/匹配密码输入逻辑
        :return: 如果成功触发了密码输入返回 True，否则返回 False
        """
        import pydirectinput
        import win32api
        import win32con
        import time

        # 1. 寻找密码框标志
        found_pw, conf_pw, pos_pw = self.find_image(game_img, 'password')

        if found_pw:
            print(f"\n🔒 识别到密码输入框 (置信度:{conf_pw:.2f})，准备输入密码...")

            # 将虚拟坐标转换为真实屏幕物理坐标
            screen_x, screen_y = self.virtual_to_real_screen(pos_pw[0], pos_pw[1], window_info)
            if screen_x is None: return False

            # 【动作 1】：把鼠标移过去并点击，以获取输入框的焦点
            win32api.SetCursorPos((screen_x, screen_y))
            time.sleep(0.1)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.05)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            time.sleep(0.4)  # 等待光标闪烁

            # 【动作 2】：模拟键盘输入密码
            print("⌨️ 正在输入配置的二级密码...")
            pydirectinput.write(self.secondary_password, interval=0.05)
            time.sleep(0.5)

            # 【动作 3】：重新截图，寻找“确认”按钮
            new_img, _ = self.capture_game_screen()
            if new_img is not None:
                # 🌟 优先寻找专属的 confirm2.png
                found_cf, conf_cf, pos_cf = self.find_image(new_img, 'confirm2')
                # 如果没找到，再找通用的 confirm.png
                if not found_cf:
                    found_cf, conf_cf, pos_cf = self.find_image(new_img, 'confirm')

                if found_cf:
                    print(f"✅ 找到确认按钮 (置信度:{conf_cf:.2f})，执行点击提交！")
                    cx, cy = self.virtual_to_real_screen(pos_cf[0], pos_cf[1], window_info)

                    win32api.SetCursorPos((cx, cy))
                    time.sleep(0.1)
                    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                    time.sleep(0.05)
                    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

                    # 💡 强制等待3秒，让游戏加载并关闭弹窗，防止死循环
                    print("⏳ 等待密码验证与弹窗关闭...")
                    time.sleep(3.0)
                    return True
                else:
                    print("⚠️ 屏幕上未发现【确认】按钮！等待下一次循环重试...")
                    time.sleep(1.0)
                    return True
        return False

    def rotate_mouse_raw(self, dx, dy=0):
        """处理底层视角旋转，并强制将鼠标死死锁在游戏窗口中心 (完美兼容窗口化)"""
        # 1. 发送相对位移指令转动视角
        win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, int(dx), int(dy), 0, 0)

        # 2. 🌟 强制将物理鼠标拉回【游戏窗口】的正中心
        try:
            # 判断当前是否有 PUBG 的句柄
            if hasattr(self, 'pubg_hwnd') and self.pubg_hwnd:
                rect = win32gui.GetWindowRect(self.pubg_hwnd)
                # 精准计算当前游戏窗口的物理中心坐标
                cx = rect[0] + (rect[2] - rect[0]) // 2
                cy = rect[1] + (rect[3] - rect[1]) // 2
                win32api.SetCursorPos((cx, cy))
            else:
                # 备用方案（以防万一没获取到句柄）
                import ctypes
                user32 = ctypes.windll.user32
                win32api.SetCursorPos((user32.GetSystemMetrics(0) // 2, user32.GetSystemMetrics(1) // 2))
        except Exception:
            pass

    def anti_afk_jiggle(self):
        """🌟 强制唤醒机制：发送极其微小的相对位移，打破引擎的输入死锁"""
        # 瞬间向右再向左微动 1 个像素，肉眼几乎看不见，但足以唤醒引擎
        win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, 1, 0, 0, 0)
        time.sleep(0.01)
        win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, -1, 0, 0, 0)

    def compass_align(self, window_info):
        cw = window_info['game_size'][0]
        center_x = cw // 2
        print("🧭 [动作] 罗盘定向校准中...")
        for _ in range(100):
            if self.check_interrupt(): return False
            img, _ = self.capture_game_screen()
            target_cx = self.find_target_on_compass(img)
            if target_cx is None:
                self.rotate_mouse_raw(80, 0)
            else:
                diff = target_cx - center_x
                if abs(diff) <= 20: print("🎯 罗盘锁定完毕！"); return True
                self.rotate_mouse_raw(int(diff * 0.4), 0)
            time.sleep(0.04)
        return False

    def stop_all_movement(self):
        pydirectinput.keyUp('w');
        pydirectinput.keyUp('a')
        pydirectinput.keyUp('s');
        pydirectinput.keyUp('d')
        pydirectinput.keyUp('shift');
        pydirectinput.keyUp('ctrl')

    def pickup_all_items_in_tab(self, window_info):
        print("   🔍 锁定'附近物品'第一格，准备执行原地狂点(利用UI自动顶替)...")
        start_x_virtual = 1920 * 0.1161
        start_y_virtual = 1080 * 0.1509
        screen_x, screen_y = self.virtual_to_real_screen(start_x_virtual, start_y_virtual, window_info)
        if screen_x is not None and screen_y is not None:
            win32api.SetCursorPos((screen_x, screen_y))
            time.sleep(0.1)
            click_count = 0
            for i in range(8):
                if self.check_interrupt(): return False
                pyautogui.rightClick()
                click_count += 1
                time.sleep(0.15)
            print(f"   🌪️ 犹如风卷残云！执行了 {click_count} 次连击，物资统统拿下！")
            return True
        return False