import time
import os
import ctypes  # 🚀 新增：用于调用 Windows 底层硬件 API

# ===================================================================
# 🛡️ 硬件防烧毁：定义 Windows 电源状态结构体
# ===================================================================
class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [
        ('ACLineStatus', ctypes.c_byte),
        ('BatteryFlag', ctypes.c_byte),
        ('BatteryLifePercent', ctypes.c_byte),
        ('SystemStatusFlag', ctypes.c_byte),
        ('BatteryLifeTime', ctypes.c_ulong),
        ('BatteryFullLifeTime', ctypes.c_ulong),
    ]

# ===================================================================
# 🛡️ 方案三：彻底掐断 YOLO 底层所有的联网自检...
# ===================================================================
# 🛡️ 方案三：彻底掐断 YOLO 底层所有的联网自检、更新与上报！(极速启动)
# 注意：必须写在 import ultralytics 之前！
# ===================================================================
os.environ['YOLO_VERBOSE'] = 'False'        # 关闭啰嗦的详细日志
os.environ['YOLO_UPDATE_CHECK'] = 'False'   # 严禁它去连外网检查新版本
os.environ['WANDB_DISABLED'] = 'true'       # 禁用第三方统计工具探测
os.environ['YOLO_TRACK'] = 'False'          # 彻底禁用遥测
import cv2
import math
import random
import glob
import keyboard
import pyautogui
import pydirectinput
import win32api
import win32con
import win32gui
from ultralytics import YOLO

from config import Config
from core.mixins import WindowMixin, VisionMixin, MathMixin, ActionMixin
# from core.door_diagnostics import DoorDiagnosticRecorder  # 截图诊断暂时停用


class PUBGSmartMarkerV9(WindowMixin, VisionMixin, MathMixin, ActionMixin):
    def __init__(self):
        # 初始化状态
        self.pubg_hwnd = None
        self.running = True
        self.is_paused = False
        # 动态绑定 Config 中的变量
        self.image_dir = str((Config.BASE_DIR / Config.IMAGE_DIR).resolve())
        self.model_path = str((Config.BASE_DIR / Config.MODEL_PATH).resolve())
        self.ref_width = Config.REF_WIDTH
        self.ref_height = Config.REF_HEIGHT
        self.MAP_SIZE = Config.MAP_SIZE
        self.jump_distance_threshold = Config.JUMP_DISTANCE_THRESHOLD
        self.target_points = Config.TARGET_POINTS.copy()
        self.thresholds = Config.THRESHOLDS.copy()
        self.secondary_password = getattr(Config, 'SECONDARY_PASSWORD', "131932")

        # 🌟 方案一：懒加载，先把模型置为空，此时不读硬盘！
        self.yolo_model = None
        self.toilet_class_id = 0
        self.door_class_id = 1

        print("📦 正在极速加载 UI 资源库...")

        self.start_btn_template = self._load_img("start_btn.png")
        self.loading_template = self._load_img("loading.png")
        self.count4_template = self._load_img("count4.png")
        self.user_template = self._load_img("user.png")
        self.feiji_template = self._load_img("feiji.png")
        self.target_template = self._load_img("target.png")
        self.naozhong_template = self._load_img("naozhong.png")
        self.leave_game_template = self._load_img("leave_game.png")
        self.password_template = self._load_img("password.png")
        self.err_template = self._load_img("err.png")
        self.back_template = self._load_img("back.png")
        self.next_template = self._load_img("next.png")
        self.confirm_template = self._load_img("confirm.png")
        self.close_template = self._load_img("close.png")
        self.cancel_template = self._load_img("cancle.png")
        self.flying_ui_template = self._load_img("flying_ui.png")

        # ====================================================
        # 🌟 雷达参数与多重目标库加载
        # ====================================================
        self.mm_offset_x = -25
        self.mm_offset_y = -10
        self.mm_size_adjust = 0
        self.radar_templates = []
        search_pattern = os.path.join(self.image_dir, "target*.png")
        for t_path in glob.glob(search_pattern):
            name = os.path.basename(t_path)
            template, mask = self._load_template_with_mask(t_path)
            if template is not None:
                self.radar_templates.append({"name": name, "template": template, "mask": mask})

        self.is_waiting_for_jump = False
        self.best_jump_point_coords = None
        self.has_marked_this_match = False
        self.initial_target_coords = None

        keyboard.add_hotkey('home', self.toggle_pause)
        keyboard.add_hotkey('end', self.emergency_stop)
        keyboard.add_hotkey('ctrl+shift+f12', self.emergency_stop)
        print("💡 快捷键已启动：【HOME】暂停/开始，【END】或【Ctrl+Shift+F12】紧急停止")
        print("=" * 60)

    def init_yolo(self):
        """🌟 专属的点火函数：只有在用户输入了 1 或 2 之后，才执行这一步"""
        if self.yolo_model is None:
            print("\n" + "=" * 60)
            print("🧠 正在唤醒 YOLOv8 视觉中枢 (引擎加速模式)...")
            self.yolo_model = YOLO(self.model_path, task='detect')
            print("✅ 大脑加载完毕，已具备实战视力！")
            print("=" * 60)
    def _load_template_with_mask(self, path):
        if not os.path.exists(path): return None, None
        img_raw = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if img_raw is None: return None, None
        if len(img_raw.shape) == 3 and img_raw.shape[2] == 4:
            template = img_raw[:, :, :3]
            alpha_channel = img_raw[:, :, 3]
            mask = cv2.merge([alpha_channel, alpha_channel, alpha_channel])
            return template, mask
        else:
            return cv2.imread(path), None

    def rotate_mouse_raw(self, x_delta, y_delta):
        try:
            if self.pubg_hwnd:
                current_fg = win32gui.GetForegroundWindow()
                if current_fg != self.pubg_hwnd:
                    win32gui.SetForegroundWindow(self.pubg_hwnd)
        except Exception:
            pass

        # 🌟 核心修复：只保留相对移动！彻底删除了强制归中(SetCursorPos)的毒瘤代码
        win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, int(x_delta), int(y_delta), 0, 0)

    def get_radar_distance(self, game_img):
        if game_img is None: return None
        h_real, w_real = game_img.shape[:2]
        base_size = int(h_real * 0.42)
        mm_size = base_size + self.mm_size_adjust
        base_offset_y = int(h_real * 0.02)
        base_offset_x = 0

        mm_x1 = w_real - mm_size + base_offset_x + self.mm_offset_x
        mm_y1 = h_real - mm_size - base_offset_y + self.mm_offset_y
        mm_x1 = max(0, min(mm_x1, w_real - 10))
        mm_y1 = max(0, min(mm_y1, h_real - 10))
        mm_x2 = min(mm_x1 + mm_size, w_real)
        mm_y2 = min(mm_y1 + mm_size, h_real)

        minimap = game_img[mm_y1:mm_y2, mm_x1:mm_x2]
        actual_h, actual_w = minimap.shape[:2]

        best_val = -1
        best_loc = None
        best_shape = None

        for t_data in self.radar_templates:
            if t_data["mask"] is not None:
                res = cv2.matchTemplate(minimap, t_data["template"], cv2.TM_CCOEFF_NORMED, mask=t_data["mask"])
            else:
                res = cv2.matchTemplate(minimap, t_data["template"], cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            if max_val > best_val:
                best_val = max_val
                best_loc = max_loc
                best_shape = t_data["template"].shape[:2]

        user_x, user_y = actual_w // 2, actual_h // 2
        if best_val > 0.45:
            th, tw = best_shape
            target_x = best_loc[0] + tw // 2
            target_y = best_loc[1] + th // 2
            dist = math.hypot(target_x - user_x, target_y - user_y)
            return dist
        return None

    def emergency_stop(self):
        """直接结束进程，避免只退出热键线程或等待业务循环检查停止标志。"""
        self.running = False
        self.is_paused = True
        try:
            pydirectinput.FAILSAFE = False
            for key in pydirectinput.KEYBOARD_MAPPING:
                try:
                    pydirectinput.keyUp(key, _pause=False)
                except Exception:
                    pass
            for button in ('left', 'right', 'middle'):
                try:
                    pydirectinput.mouseUp(button=button, _pause=False)
                except Exception:
                    pass
            self.toggle_desktop_icons(show=True)
        finally:
            os._exit(0)

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        print(f"\n{'⏸️ 脚本已暂停' if self.is_paused else '▶️ 脚本继续运行'}")

        # ==========================================================
        # 🚀 绝活：底层硬件防烧毁机制 (每5秒检测一次是否断电)
        # ==========================================================
    def check_power_safe(self):
            curr_time = time.time()
            # 控制频率：每 5 秒读取一次底层硬件状态，防卡顿
            if curr_time - getattr(self, 'last_power_check_time', 0) > 5.0:
                self.last_power_check_time = curr_time
                try:
                    status = SYSTEM_POWER_STATUS()
                    ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status))

                    # ACLineStatus: 0 = 电池供电(断电), 1 = 交流电供电, 255 = 未知状态
                    if status.ACLineStatus == 0:
                        print("\n\n" + "💥" * 25)
                        print("🚨🚨🚨 [硬件防烧毁最高警报] 🚨🚨🚨")
                        print("⚠️ 警告：检测到宿舍已断电，当前正在使用【电池】供电！")
                        print("⚠️ 高负载下电池放电极易击穿显卡供电模块！")
                        print("⚠️ 引擎立即执行紧急物理切断！！！")
                        print("💥" * 25 + "\n\n")
                        self.running = False  # 强行拉下程序的总闸
                        return False
                except Exception:
                    pass
            return self.running
    def check_interrupt(self):
        # 🌟 修复点：彻底移除会导致死锁的 while self.is_paused 阻塞循环
        # 将暂停逻辑完全交给外层业务循环处理，保持此处轻量级
        # 1. 优先执行底层硬件供电安全检测
        if not self.check_power_safe():
            return True  # 发现断电，立刻向全系统广播中断信号！
        if keyboard.is_pressed('end'):
            self.running = False
            return True
        return not self.running

    def handle_secondary_password(self, game_img, window_info):
        found_pwd, conf_pwd, pos_pwd = self.find_image(game_img, 'password')
        if found_pwd:
            print(f"\n   🔐 拦截到【二级密码】验证弹窗 (匹配度:{conf_pwd:.2f})！挂起其他操作...")
            win_x, win_y = window_info['screen_pos']
            bor_x, bor_y = window_info['border']
            real_w, real_h = window_info['real_client_size']
            real_click_x = int(pos_pwd[0] * (real_w / 1920.0))
            real_click_y = int(pos_pwd[1] * (real_h / 1080.0))
            win32api.SetCursorPos((win_x + bor_x + real_click_x, win_y + bor_y + real_click_y))
            time.sleep(0.2);
            pyautogui.click();
            time.sleep(0.5)
            password = self.secondary_password
            for char in password:
                pydirectinput.keyDown(char);
                time.sleep(0.04);
                pydirectinput.keyUp(char);
                time.sleep(0.25)
            time.sleep(0.5)
            latest_img, _ = self.capture_game_screen()
            if latest_img is not None:
                found_conf, conf_val, pos_conf = self.find_image(latest_img, 'confirm')
                if found_conf:
                    real_conf_x = int(pos_conf[0] * (real_w / 1920.0))
                    real_conf_y = int(pos_conf[1] * (real_h / 1080.0))
                    win32api.SetCursorPos((win_x + bor_x + real_conf_x, win_y + bor_y + real_conf_y))
                    time.sleep(0.1);
                    pyautogui.click();
                    time.sleep(0.3);
                    pyautogui.click()
                else:
                    pydirectinput.press('enter')
            time.sleep(3.0)
            return True
        return False

    def handle_endgame(self, game_img, window_info):
        if game_img is None: return False
        h, w = game_img.shape[:2]
        bottom_half = game_img[int(h * 0.4):h, 0:w]
        for btn_name in ['err', 'confirm', 'close', 'next', 'back','cancel']:
            found, conf, pos = self.find_image(bottom_half, btn_name)
            if found:
                print(f"\n   💀 发现脱战按钮 [{btn_name}.png]！执行脱战！")
                win_x, win_y = window_info['screen_pos']
                bor_x, bor_y = window_info['border']
                real_w, real_h = window_info['real_client_size']
                if btn_name == 'back':
                    real_click_x = int((1920 * 0.08) * (real_w / 1920.0))
                else:
                    real_click_x = int(pos[0] * (real_w / 1920.0))
                real_click_y = int((pos[1] + int(h * 0.4)) * (real_h / 1080.0))
                win32api.SetCursorPos((win_x + bor_x + real_click_x, win_y + bor_y + real_click_y))
                time.sleep(0.1);
                pyautogui.click();
                time.sleep(0.5);
                pyautogui.click();
                time.sleep(1.5)
                return True
        return False

    def reset_tactical_target(self, window_info):
        if not self.initial_target_coords: return False
        self.stop_all_movement()
        pydirectinput.press('m');
        time.sleep(1.5)
        pydirectinput.press('delete');
        time.sleep(0.5)
        game_img, new_window_info = self.capture_game_screen()
        if game_img is None: pydirectinput.press('m'); return False
        screen_x, screen_y = self.convert_to_screen(self.initial_target_coords, new_window_info)
        if screen_x is not None and screen_y is not None:
            pyautogui.moveTo(screen_x, screen_y);
            time.sleep(0.2);
            pyautogui.rightClick()
        pydirectinput.press('m');
        time.sleep(1.0)
        self.compass_align(window_info)
        return True

    def smart_mark(self, flight_path, window_info):
        print("\n" + "=" * 60)
        print("🗺️  计算航线与精确标点...")
        print("=" * 60)
        best_target, best_coords, min_dist = self.find_best_target(flight_path)
        screen_x, screen_y = self.convert_to_screen(best_coords, window_info)
        if screen_x is not None and screen_y is not None:
            pyautogui.moveTo(screen_x, screen_y);
            time.sleep(0.1);
            pyautogui.rightClick()
            print(f"   🎯 已直接标记精确坐标点: {best_target['name']}")
            self.initial_target_coords = best_coords
            self.current_target_id = best_target['id']
            if min_dist > 100.0:
                print(f"\n⛔ 警告: 目标点 {best_target['name']} 理论最短距离为 {min_dist:.1f}px")
                print("⛔ 距离超过战术底线 (100px)！航线过偏，准备主动秒退本局...")
                pydirectinput.keyDown('m');
                time.sleep(0.1);
                pydirectinput.keyUp('m');
                time.sleep(1.0)
                pydirectinput.press('esc');
                time.sleep(1.0)
                clicked_leave = False
                game_img, new_window_info = self.capture_game_screen()
                if game_img is not None:
                    found, conf, pos = self.find_image(game_img, 'leave_game')
                    if found:
                        win_x, win_y = new_window_info['screen_pos']
                        bor_x, bor_y = new_window_info['border']
                        real_w, real_h = new_window_info['real_client_size']
                        rx = int(pos[0] * (real_w / 1920.0));
                        ry = int(pos[1] * (real_h / 1080.0))
                        win32api.SetCursorPos((win_x + bor_x + rx, win_y + bor_y + ry))
                        time.sleep(0.1);
                        pyautogui.click();
                        clicked_leave = True
                if not clicked_leave:
                    virtual_cx = 150;
                    virtual_cy = 500
                    click_x, click_y = self.virtual_to_real_screen(virtual_cx, virtual_cy, window_info)
                    if click_x and click_y:
                        win32api.SetCursorPos((click_x, click_y));
                        time.sleep(0.1);
                        pyautogui.click()
                time.sleep(1.0)
                self.is_waiting_for_jump = False
                self.has_marked_this_match = False
                return False

            print("\n🔄 保持地图打开，等待跳伞...\n")
            self.is_waiting_for_jump = True
            self.best_jump_point_coords = best_coords
            self.wait_for_jump(window_info, min_dist)
            return True

    def wait_for_jump(self, window_info, theoretical_min_dist):
        print("🪂 启动实时空降追踪模式 (纯动能追踪版)...")
        jump_loop_count = 0
        min_recorded_dist = float('inf')
        base_trigger = theoretical_min_dist + 50.0
        real_time_trigger = min(max(base_trigger, 80.0), 150.0)

        time.sleep(2)
        last_endgame_check = time.time()
        last_log_print_time = 0
        jump_timeout_start = None
        has_boarded_plane = False
        last_seen_time = time.time()
        last_user_pos = None
        last_user_pos_time = time.time()
        fly_past_counter = 0

        def execute_safe_jump(current_win_info, j_dist):
            cw, ch = current_win_info['game_size']
            cx = current_win_info['screen_pos'][0] + current_win_info['border'][0] + int(cw / 2)
            cy = current_win_info['screen_pos'][1] + current_win_info['border'][1] + int(ch / 2)
            win32api.SetCursorPos((cx, cy))
            time.sleep(0.1)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.05)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            time.sleep(0.3)

            pydirectinput.keyDown('m');
            time.sleep(0.25);
            pydirectinput.keyUp('m');
            time.sleep(0.5)
            pydirectinput.keyDown('f');
            time.sleep(0.2);
            pydirectinput.keyUp('f');
            time.sleep(0.5)
            pydirectinput.keyDown('v');
            time.sleep(0.1);
            pydirectinput.keyUp('v')

            self.is_waiting_for_jump = False
            time.sleep(0.5)
            self.execute_ai_bot_behavior(current_win_info, jump_distance=j_dist)
            return True

        while self.running and jump_loop_count < 600:
            if self.is_paused: time.sleep(1); continue
            jump_loop_count += 1
            game_img, new_window_info = self.capture_game_screen()
            if game_img is None: time.sleep(0.2); continue

            if time.time() - last_endgame_check > 2.0:
                if self.handle_endgame(game_img, new_window_info):
                    self.is_waiting_for_jump = False
                    return False
                last_endgame_check = time.time()

            found_nao, nao_conf, _ = self.find_image(game_img, 'naozhong')
            if not found_nao:
                pydirectinput.keyDown('m');
                time.sleep(0.1);
                pydirectinput.keyUp('m');
                time.sleep(1.0)

            found_count4, _, _ = self.find_image(game_img, 'count4')
            if found_count4:
                jump_timeout_start = None
                has_boarded_plane = False
                last_user_pos = None
                time.sleep(0.5)
                continue

            mx, my = new_window_info['map_offset']
            map_img = game_img[my:my + self.MAP_SIZE, mx:mx + self.MAP_SIZE]

            # ==================================================
            # 📊 第一步：先把所有嫌疑人的得分都算出来！
            # ==================================================
            # 1. 用 user 的照片去匹配
            user_found_raw, user_pos_raw, user_conf_raw, _ = self.find_user_on_map(map_img)
            # 2. 用 target 的照片去匹配
            found_t, conf_t, pos_t = self.find_image(map_img, 'target')
            # 3. 用飞机的照片去匹配
            found_feiji, conf_feiji, pos_feiji = self.find_image(map_img, 'feiji')

            # ==================================================
            # 🖨️ 视觉雷达监控 (每 1 秒强制换行打印一次，绝不被覆盖)
            # ==================================================
            curr_sec = int(time.time())
            last_print_sec = getattr(self, 'last_radar_print_sec', 0)

            if curr_sec > last_print_sec:
                print(
                    f"   📊 [视觉雷达] User得分:{user_conf_raw:.2f} | Target得分:{conf_t:.2f} | 飞机得分:{conf_feiji:.2f}")
                self.last_radar_print_sec = curr_sec

            # ==================================================
            # 🚀 第三步：极简逻辑判定 (只认高分！)
            # ==================================================
            if found_feiji and conf_feiji > 0.50:  # 稍微放宽点飞机的条件，防止蓝海/绿地背景干扰
                user_found = True
                user_pos = pos_feiji
                user_conf = conf_feiji
            else:
                user_found = user_found_raw
                user_pos = user_pos_raw
                user_conf = user_conf_raw

                # 🛡️ 核心修改：大道至简！把原本 0.48 的门槛直接拔高到 0.65！
                # 这样即使它把 target 认成了 user (得分大概0.5左右)，也绝对及格不了！
                if user_found and user_conf < 0.89:
                    user_found = False

            if user_found:
                last_seen_time = time.time()
                if not has_boarded_plane:
                    if last_user_pos is not None:
                        move_dist = math.sqrt(
                            (user_pos[0] - last_user_pos[0]) ** 2 + (user_pos[1] - last_user_pos[1]) ** 2)
                        time_diff = time.time() - last_user_pos_time
                        if move_dist > 200.0:
                            has_boarded_plane = True
                            jump_timeout_start = time.time()
                            min_recorded_dist = float('inf')
                        elif time_diff > 1.5:
                            speed = move_dist / time_diff
                            if speed > 15.0:
                                has_boarded_plane = True
                                jump_timeout_start = time.time()
                                min_recorded_dist = float('inf')
                            else:
                                last_user_pos = user_pos
                                last_user_pos_time = time.time()
                    else:
                        last_user_pos = user_pos
                        last_user_pos_time = time.time()
                else:
                    if last_user_pos is not None:
                        move_dist = math.sqrt(
                            (user_pos[0] - last_user_pos[0]) ** 2 + (user_pos[1] - last_user_pos[1]) ** 2)
                        time_diff = time.time() - last_user_pos_time
                        if time_diff < 1.0 and move_dist > 80.0: user_found = False
                    if user_found:
                        last_user_pos = user_pos
                        last_user_pos_time = time.time()

            if has_boarded_plane and jump_timeout_start:
                time_since_last_seen = time.time() - last_seen_time
                total_flight_time = time.time() - jump_timeout_start
                if time_since_last_seen > 5.0 or total_flight_time > 90.0:
                    return execute_safe_jump(new_window_info, 150.0)

            target_x, target_y = None, None
            if self.best_jump_point_coords:
                target_x, target_y = self.best_jump_point_coords
            else:
                f_t, _, p_t = self.find_image(game_img, 'target')
                if f_t: target_x = p_t[0] - mx; target_y = p_t[1] - my

            if user_found and target_x is not None:
                dist = math.sqrt((user_pos[0] - target_x) ** 2 + (user_pos[1] - target_y) ** 2)
                if dist > min_recorded_dist + 200:
                    pass
                elif dist < min_recorded_dist:
                    min_recorded_dist = dist

                if has_boarded_plane:
                    flight_time = time.time() - jump_timeout_start
                    if int(time.time() * 10) % 10 == 0:
                        print(
                            f"   ✈️ 航班监控 -> 当前距标点: {dist:.1f}px | 跳伞红线: {real_time_trigger:.1f}px | 已飞: {flight_time:.1f}秒",
                            end='\r')
                if dist <= real_time_trigger+20:
                    if has_boarded_plane:
                        flight_time = time.time() - jump_timeout_start
                        print("\n" + "=" * 50)
                        print("🚨 [跳伞引擎] 触发跳舱指令！")
                        print("   🔍 触发原因核查：")
                        print(f"      1. 实时距离 (dist) : {dist:.1f} px")
                        print(f"      2. 动态阈值 (trigger): {real_time_trigger+20:.1f} px")
                        print(f"      3. 判定公式        : {dist:.1f} <= {real_time_trigger+20:.1f} -> 成立！")
                        print(f"      4. 上飞机时长      : {flight_time:.1f} 秒")
                        print("=" * 50)
                        if time.time() - jump_timeout_start > 5.0:
                            return execute_safe_jump(new_window_info, dist)

                if has_boarded_plane and dist > min_recorded_dist + 50 and min_recorded_dist != float('inf'):
                    fly_past_counter += 1
                    if fly_past_counter >= 3:
                        if min_recorded_dist <= 150.0:
                            return execute_safe_jump(new_window_info, min_recorded_dist)
                        else:
                            pydirectinput.press('m');
                            self.is_waiting_for_jump = False;
                            self.has_marked_this_match = True
                            return False
                else:
                    fly_past_counter = 0
            time.sleep(0.05)

        self.is_waiting_for_jump = False
        pydirectinput.keyDown('m');
        time.sleep(0.1);
        pydirectinput.keyUp('m')
        return False

    def execute_ai_bot_behavior(self, window_info, jump_distance=0.0):
        cw, ch = window_info['game_size']
        center_x = cw / 2
        center_y = ch / 2
        print("\n" + "=" * 60)
        print("🤖 [AI大本营] 实战空降 -> 桥接视觉本能突击 (已优化防拉扯)")
        print("=" * 60)
        time.sleep(1)
       # self.compass_align(window_info)
        # ==========================================================
        # 🚀 专属空降极速校准引擎 (暴力锁头版)
        # 天上不需要YOLO看图，不怕画面模糊，直接拉满灵敏度瞬间甩过去！
        # ==========================================================
        print("   🧭 启动【极速空降校准】，暴力锁头...")
        pydirectinput.press('n')
        align_start = time.time()
        while time.time() - align_start < 2.0:  # 最多只给它 2 秒的校准时间
            c_img, _ = self.capture_game_screen()
            if c_img is None: time.sleep(0.02); continue
            tx = self.find_target_on_compass(c_img)
            if tx is not None:
                diff_x = tx - center_x
                # 🎯 容差放宽到 3 像素，只要大方向对准了立刻起步，不再强求完美的 0 像素！
                if abs(diff_x) <= 3:
                    print("   🎯 极速校准完毕，完美对正！")
                    break

                # 🚀 暴力乘数！比地面转头快 3 到 5 倍！一秒钟内直接甩到目标！
                # 如果甩得太猛过了头，把 15.0 调小(如10.0)；如果还嫌慢，调大(如20.0)
                self.rotate_mouse_raw(int(diff_x * 15.0), 0)
            else:
                self.rotate_mouse_raw(120, 0)  # 没看到黄点，快速大风车寻找

            time.sleep(0.02)  # 极短延迟，超高频刷新
        # ==========================================================
            # ==========================================================
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.05)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

            # 算出从开始跳伞到现在花了多少时间
            time_spent = time.time() - align_start
            if time_spent < 0.5:
                print(f"   ⏳ 校准太快(仅{time_spent:.1f}s)，等待出舱动画结束...")
                time.sleep(0.5 - time_spent)
            # 👇 1. 空中直接按 N 开启小地图
            print("   🗺️ 按 N 开启小地图，启动空中实时雷达测距...")

            time.sleep(0.5)
            pydirectinput.keyDown('w')
            fly_start = time.time()

            # 👇 2. 实时雷达平飞循环 (取代了原来的固定时间 w_time)
            while time.time() - fly_start < 60:  # 设个60秒最大超时保护
                if self.is_paused: time.sleep(0.1); fly_start += 0.1; continue
                if self.check_interrupt(): return
                d_img, current_window_info = self.capture_game_screen()
                if self.handle_endgame(d_img, current_window_info): self.stop_all_movement(); return

                # 空中校准逻辑 (原封不动)
                tx = self.find_target_on_compass(d_img)
                if tx is not None:
                    diff_x = tx - center_x
                    if abs(diff_x) > 4:
                        self.rotate_mouse_raw(int(diff_x * 10.0), 0)
                else:
                    self.rotate_mouse_raw(80, 0)

                if int(time.time() * 10) % 10 == 0:
                    win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, 10, 0, 0, 0)
                    win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, -10, 0, 0, 0)

                # 👇 3. 核心：读取小地图测距，距离 <= 40px 立刻跳出平飞循环！
                dist = self.get_radar_distance(d_img)
                if dist is not None:
                    if dist <= 80.0:
                        print(f"\n   🦅 雷达距离 {dist:.1f}px <= 40px！到达目标上空，立即执行垂直俯冲！")
                        break  # 打破平飞循环，进入下方的视角向下+俯冲阶段！
                    else:
                        print(f"   ✈️ 空中平飞中... 当前雷达距离: {dist:.1f}px", end='\r')

                time.sleep(0.04)

            # 把视角拉到最底（衔接后面的 shift+w 俯冲）
            for _ in range(15): self.rotate_mouse_raw(0, 250); time.sleep(0.03)
        pydirectinput.keyDown('shift')
        dive_start = time.time()
        is_d_pressed = False  # 🚀 新增：记录 D 键的状态，防重复按键

        has_seen_flying_ui = False
        lost_flying_ui_count = 0
        print("   🪂 进入俯冲阶段，开启【20秒后精准落地侦测】...")
        while time.time() - dive_start < 30:
            if self.is_paused: time.sleep(0.1); dive_start += 0.1; continue
            if self.check_interrupt():
                if is_d_pressed: pydirectinput.keyUp('d')
                return
            d_img, current_window_info = self.capture_game_screen()

            if self.handle_endgame(d_img, current_window_info):
                if is_d_pressed: pydirectinput.keyUp('d')
                self.stop_all_movement();
                return

            # 🚀 终极空降引擎：只在 20秒 到 30秒 之间开启二值化扫描！
            dive_time = time.time() - dive_start
            if 8.0 < dive_time < 30.0:
                gray_screen = cv2.cvtColor(d_img, cv2.COLOR_BGR2GRAY)
                gray_template = cv2.cvtColor(self.flying_ui_template, cv2.COLOR_BGR2GRAY)
                _, thresh_screen = cv2.threshold(gray_screen, 200, 255, cv2.THRESH_BINARY)
                _, thresh_template = cv2.threshold(gray_template, 200, 255, cv2.THRESH_BINARY)

                # 2. 匹配度计算
                res = cv2.matchTemplate(thresh_screen, thresh_template, cv2.TM_CCOEFF_NORMED)
                _, conf_fly, _, _ = cv2.minMaxLoc(res)

                # 打印仪表盘 (加长空格防止覆盖残留)
                print(f"   🪂 俯冲 {dive_time:.1f}s | KM/H 匹配度: {conf_fly:.2f} (阈值:0.50)      ", end='\r',
                      flush=True)
                # 3. 消失判定逻辑 (阈值设为 0.50)
                if conf_fly > 0.42:
                    has_seen_flying_ui = True
                    lost_flying_ui_count = 0
                elif has_seen_flying_ui:
                    lost_flying_ui_count += 1
                    if lost_flying_ui_count >= 2:
                        print()  # 换行防覆盖
                        print(f"\n   🛬 【飞行计速器瞬间消失】！确认人物已双脚触地！")
                        print(f"   ⏱️ 极速打断俯冲，为您省下 {30.0 - dive_time:.1f} 秒！")
                        break
            # 🎯 核心所在：打破30秒死循环，提前松伞！

            tx = self.find_target_on_compass(d_img)
            if tx is not None:
                diff_x = tx - center_x
                if abs(diff_x) > 4:
                    self.rotate_mouse_raw(int(diff_x * 10.0), 0)
            else:
                # 🌟 修复俯冲时的抢鼠标拉扯
                self.rotate_mouse_raw(80, 0)
            dist = self.get_radar_distance(d_img)
            if dist is not None and dist <= 20.0:
                if not is_d_pressed:
                    pydirectinput.keyDown('d')
                    is_d_pressed = True
                    print(f"   🌪️ 极近距离 ({dist:.1f}px)！切入 W+D 螺旋下坠姿态！")
            else:
                if is_d_pressed:
                    pydirectinput.keyUp('d')
                    is_d_pressed = False
        pydirectinput.keyUp('shift')
        pydirectinput.keyUp('w')
        if is_d_pressed:
            pydirectinput.keyUp('d')
        time.sleep(1.5)
        for _ in range(12): self.rotate_mouse_raw(0, -140); time.sleep(0.04)
        time.sleep(0.5)
        pydirectinput.press('v')

        # 🌟 修复落地卡死 bug，交还控制权给主循环
        return True

    def start_auto_run(self, window_info=None):
        import pydirectinput
        pydirectinput.FAILSAFE = False

        print("\n" + "=" * 60)
        print("🛠️ [实战完全体] 完美闭环：防闪烁原地罚站 + 动态偏航纠正")
        print("=" * 60)

        # 动态加载交互 UI 资源
        f_path = os.path.join(self.image_dir, 'F_2026-10-24.png')
        f_tmpl = cv2.imread(f_path) if os.path.exists(f_path) else None
        if f_tmpl is not None:
            # 该82×82模板在1920×1080现场截图中的实际图标约29×29。
            f_tmpl = cv2.resize(f_tmpl, None, fx=0.35, fy=0.35)
        print(f"🔎 [开门诊断] F模板已加载:{f_tmpl is not None} 路径:{f_path} "
              f"尺寸:{f_tmpl.shape[:2] if f_tmpl is not None else None}")
        last_door_diagnostic = 0.0
        # last_door_snapshot = 0.0
        # diagnostic_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)),
        #                               'debug', 'door_interaction')
        # door_recorder = DoorDiagnosticRecorder(diagnostic_dir)
        # print(f"📷 [开门诊断] 接近门时最多每0.25秒采样一次，按时间戳保存至 {diagnostic_dir}")

        door_path = os.path.join(self.image_dir, 'door.png')
        door3_path = os.path.join(self.image_dir, 'door3.png')
        door_tmpl = cv2.imread(door_path) if os.path.exists(door_path) else None
        door3_tmpl = cv2.imread(door3_path) if os.path.exists(door3_path) else None
        open_door_templates = [t for t in [door_tmpl, door3_tmpl] if t is not None]

        print("🔍 确认小地图状态...")

        dist_history = []
        last_w_refresh = time.time()

        keys_pressed = {'w': False, 's': False, 'a': False, 'd': False, 'shift': False, 'ctrl': False, 'c': False}

        is_sprinting = False

        def set_key(key, state):
            if keys_pressed[key] != state:
                if state:
                    pydirectinput.keyDown(key)
                else:
                    pydirectinput.keyUp(key)
                keys_pressed[key] = state

        def stop_all():
            nonlocal is_sprinting
            for k in keys_pressed.keys(): set_key(k, False)
            is_sprinting = False

            # 👇 从这里开始复制：【高频 1 像素平滑拖拽 + 死区锁死引擎】
        def smooth_glide_mouse(diff_x):
                # 1. 【死区锁死】如果门框中心距离屏幕中心小于 20 像素，视为“已完美对准”！
                # 此时直接 return，切断一切鼠标输入，彻底解决对准后还左右发抖的问题。
            if abs(diff_x) < 20:
                    return

                # 2. 【引力吸附算法】不要一次性拉满，每次只拉回偏差的 40%
                # 这样镜头离门越远，滑得越快；越靠近门，滑得越慢，形成自然的物理减速。
            move_dist = int(diff_x * 0.4)

                # 安全阀：不管偏差多大，这一帧最多只允许滑 80 像素，防大风车
            move_dist = max(-80, min(80, move_dist))

                # 3. 【核心：高频像素切割】
                # 把算出来的位移，切碎成每次只移动 3 像素，利用 for 循环瞬间执行完
                # 游戏底层会把它识别成一次“极度平滑的鼠标拖拽”！
            step = 3 if move_dist > 0 else -3
            for _ in range(abs(move_dist)):
                win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, step, 0, 0, 0)
        # 👆 复制到这里结束

        bot_state = "COMPASS_RUSH"
        entered_target_zone = False

        last_action_log = ""
        self.last_ai_print = time.time()

        circle_start = 0
        last_circle_pause_time = time.time()

        global_last_seen_time = time.time()
        global_last_door_time = 0.0

        skew_dir = 'a'
        is_skew_locked = False
        last_aspect_ratio = 0.0
        ratio_check_time = time.time()
        has_aligned_door = False

        last_space_time = 0.0
        verify_count = 0

        last_afk_move_time = time.time()

        # 全局护航计时器
        global_progress_time = time.time()

        # 罗盘黄点记忆变量
        last_valid_tx_compass = None
        last_valid_tx_time = time.time()

        print("🏃‍♂️ 开启狂奔：距离 >20px 纯看罗盘，<=20px 激活视觉索敌！")

        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.05)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

        try:
            while self.running:
                if self.is_paused:
                    stop_all()
                    time.sleep(1.0)
                    continue

                if self.check_interrupt():
                    print("\n\n🛑 接收到强行中断指令！切断引擎！")
                    break

                game_img, current_window_info = self.capture_game_screen()
                # frame_captured_at = time.time()  # 截图诊断暂时停用
                if game_img is None: time.sleep(0.05); continue

                current_f_score = 0.0
                if f_tmpl is not None:
                    res_f = cv2.matchTemplate(game_img, f_tmpl, cv2.TM_CCOEFF_NORMED)
                    current_f_score = cv2.minMaxLoc(res_f)[1]

                if self.handle_endgame(game_img, current_window_info):
                    self.has_marked_this_match = False
                    stop_all()
                    break

                h, w = game_img.shape[:2]
                center_x = w / 2

                dist = self.get_radar_distance(game_img)

                # ==========================================
                # 🌟 电子围栏与动态偏航纠正 
                # ==========================================
                if dist is not None:
                    if bot_state == "COMPASS_RUSH":
                        dist_history.append(dist)
                        if len(dist_history) > 5:
                            dist_history.pop(0)

                        if len(dist_history) == 5 and dist > 30.0:
                            if (dist_history[-1] - dist_history[0]) > 2.0 and dist_history[-1] >= dist_history[-2]:
                                print(f"\n🚨 [偏航预警] 距离持续增加 ({dist_history[0]:.1f} -> {dist:.1f}px)！目标已在背后！")
                                stop_all()
                                print("   🔄 强制向后转身找点，把真实黄点拉回视野...")
                                for _ in range(15):
                                    win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, 200, 0, 0, 0)
                                    time.sleep(0.02)
                                time.sleep(0.5) 
                                self.compass_align(current_window_info)

                                time.sleep(1.0)
                                dist_history.clear()
                                global_progress_time = time.time()
                                continue

                    if dist <= 30.0:
                        if not entered_target_zone:
                            print("\n📍 已抵达目标 20px 核心区！正式激活【YOLO视觉】逻辑！")
                            entered_target_zone = True
                    elif dist > 30.0:
                        if entered_target_zone and bot_state not in ["VERIFY_DOOR", "ITEM_PICKUP", "AFK"]:
                            print(f"\n🚨 [电子围栏报警] 偏离标点过远 ({dist:.1f}px > 30px)！判定为追错目标或迷失！")
                            print("🚨 强行关闭 YOLO 视觉，退回罗盘导航重新拉回目标点...")
                            entered_target_zone = False
                            stop_all()
                            bot_state = "COMPASS_RUSH"
                            dist_history.clear()
                            global_progress_time = time.time()
                            continue

                # ==========================================
                # 全局智能 F 交互拦截器
                # ==========================================
                if bot_state not in ["VERIFY_DOOR", "ITEM_PICKUP", "AFK"]:
                    ignore_f = False
                    if bot_state in ["RUNNING", "CIRCLING"]:
                        if time.time() - global_last_door_time > 3:
                            ignore_f = True

                    if bot_state == "APPROACH_DOOR" and not has_aligned_door:
                        ignore_f = True
                    if bot_state == 'APPROACH_DOOR':
                        reason = ('未加载F模板' if f_tmpl is None else
                                  '对齐条件拦截' if ignore_f else
                                  'F匹配未超过0.72' if current_f_score <= 0.72 else '允许进入F核验')
                        if time.time() - last_door_diagnostic >= 2.0:
                            print(f"\n🔎 [开门诊断] F得分:{current_f_score:.4f} 阈值:>0.72 "
                                  f"门已对齐:{has_aligned_door} 拦截:{ignore_f} 原因:{reason}")
                            last_door_diagnostic = time.time()
                        # # 采样不受两秒日志间隔限制；画面与分数来自同一次截图。
                        # if frame_captured_at - last_door_snapshot >= 0.25:
                        #     metadata = dict(state=bot_state, f_score=float(current_f_score),
                        #                     f_threshold=0.72, template_loaded=f_tmpl is not None,
                        #                     has_aligned_door=bool(has_aligned_door),
                        #                     ignore_f=bool(ignore_f), reason=reason,
                        #                     marker_distance=dist, captured_at=frame_captured_at)
                        #     if door_recorder.submit(game_img, metadata):
                        #         last_door_snapshot = frame_captured_at
                    if current_f_score > 0.72 and not ignore_f:
                        print(f"\n✋ 触发物理交互 [F]！(置信度: {current_f_score:.2f}) 强行打断动作，进入核验！")
                        stop_all()
                        bot_state = "VERIFY_DOOR"
                        verify_count = 1
                        global_progress_time = time.time()
                        continue
                # ==========================================
                # YOLO 视觉逻辑
                # ==========================================
                toilet_box, valid_door_box = None, None

                if self.yolo_model is not None and entered_target_zone and bot_state not in ["VERIFY_DOOR", "ITEM_PICKUP", "AFK"]:
                    results = self.yolo_model.predict(source=game_img, conf=0.5, classes=[0, 1], verbose=False,half=True, imgsz=640,)
                    toilet_boxes, door_boxes = [], []

                    for r in results:
                        for box in r.boxes:
                            x1, y1, x2, y2 = box.xyxy[0].tolist()
                            cls_id = int(box.cls[0].item())
                            conf_val = box.conf[0].item()
                            tx, ty, th, tw = (x1 + x2) / 2, (y1 + y2) / 2, y2 - y1, x2 - x1

                            if tx > w * 0.8 and ty > h * 0.6: continue

                            if cls_id == getattr(self, 'toilet_class_id', 0) and conf_val > 0.55:
                                if th > h * 0.04 or tw > w * 0.04:
                                    toilet_boxes.append({'x': tx, 'y': ty, 'h': th, 'w': tw})
                            elif cls_id == getattr(self, 'door_class_id', 1) and conf_val > 0.55:
                                if th > h * 0.1:
                                    # 🚀 新增拦截：绕桩状态下，无视偏差大于 300 的边缘大门
                                    if bot_state == "CIRCLING" and abs(tx - center_x) > 300:
                                        continue
                                    door_boxes.append({'x': tx, 'y': ty, 'h': th, 'w': tw})

                    toilet_box = max(toilet_boxes, key=lambda b: b['w'] * b['h']) if toilet_boxes else None
                    valid_door_box = max(door_boxes, key=lambda b: b['w'] * b['h']) if door_boxes else None

                    if bot_state == "COMPASS_RUSH" and toilet_box and not valid_door_box:
                        if abs(toilet_box['x'] - center_x) > 800:
                            toilet_box = None

                target_focus = valid_door_box if valid_door_box else toilet_box

                if valid_door_box: global_last_door_time = time.time()

                if target_focus:
                    global_last_seen_time = time.time()
                    curr_t = time.time()
                    t_name = "大门" if valid_door_box else "厕所"

                    if curr_t - self.last_ai_print > 1.0:
                        print(f"   👁️ AI视觉: 捕获[{t_name}] (高度:{target_focus['h']:.1f}, 偏差X:{target_focus['x'] - center_x:.1f})")
                        self.last_ai_print = curr_t

                    if bot_state == "COMPASS_RUSH":
                        print(f"\n🎯 [视觉接管] 奔袭途中发现 [{t_name}]！切入突击模式...")
                        stop_all()

                        bot_state = "APPROACH_DOOR" if valid_door_box else "RUNNING"
                        is_skew_locked = False
                        last_aspect_ratio = 0.0
                        has_aligned_door = False
                        last_action_log = ""
                        global_progress_time = time.time()
                        global_last_seen_time = time.time()
                        continue

                # ==========================================
                # 🔄 状态机：导航与动作执行
                # ==========================================

                if bot_state == "COMPASS_RUSH":
                    tx_compass = self.find_target_on_compass(game_img)
                    if tx_compass is not None:
                        last_valid_tx_compass = tx_compass
                        last_valid_tx_time = time.time()

                        diff_x = tx_compass - center_x
                        global_progress_time = time.time()

                        abs_diff = abs(diff_x)

                        if abs_diff > 80:
                            turn_multiplier = 7.5
                        elif abs_diff > 40:
                            turn_multiplier = 4.5  
                        elif abs_diff > 20:
                            turn_multiplier = 1.5 
                        else:
                            turn_multiplier = 0.5 

                        if dist is not None and dist <= 25.0 and abs_diff <= 40:
                            turn_multiplier = min(turn_multiplier, 1)

                        if abs_diff > 3:
                            self.rotate_mouse_raw(int(diff_x * turn_multiplier), 0)

                        if dist is not None and dist <= 30.0:
                            if is_sprinting:
                                print("   🚶 进圈解除疾跑，静步索敌...")
                                set_key('shift', False)
                                is_sprinting = False
                            if abs(diff_x) > 60:
                                if keys_pressed['w']:
                                    print("   🛑 目标在侧后方，停步转身...")
                                    set_key('w', False)
                            else:
                                if not keys_pressed['w']:
                                    set_key('w', True)
                            curr_t = time.time()
                            last_scrape = getattr(self, 'last_scrape_time', 0)
                            if curr_t - last_scrape > 3.0: 
                                pydirectinput.press('space') 
                                scrape_key = random.choice(['a', 'd'])
                                set_key(scrape_key, True)
                                time.sleep(0.3)
                                set_key(scrape_key, False)
                                self.last_scrape_time = time.time()
                        else:
                            if not is_sprinting:
                                set_key('w', True)
                                set_key('shift', True)
                                is_sprinting = True
                                last_w_refresh = time.time()
                            elif time.time() - last_w_refresh > 3.0:
                                set_key('shift', False)
                                set_key('w', False)
                                time.sleep(0.02)
                                set_key('w', True)
                                set_key('shift', True)
                                last_w_refresh = time.time()
                                
                            curr_t = time.time()
                            crab_end = getattr(self, 'crab_walk_end', 0)
                            next_crab = getattr(self, 'next_crab_time', curr_t + 2.0)

                            if curr_t < crab_end:
                                pass
                            else:
                                if keys_pressed['a']: set_key('a', False)
                                if keys_pressed['d']: set_key('d', False)
                                if curr_t > next_crab:
                                    k = random.choice(['a', 'd'])
                                    set_key(k, True)
                                    self.crab_walk_end = curr_t + random.uniform(1.0, 2.5)
                                    self.next_crab_time = curr_t + random.uniform(4.0, 8.0)

                            if int(time.time()) % 8 == 0:
                                pydirectinput.press('space')
                                time.sleep(0.1)
                    else:
                        time_since_last_seen = time.time() - last_valid_tx_time

                        if time_since_last_seen < 1.0:
                            if not is_sprinting:
                                set_key('w', True)
                                set_key('shift', True)
                                is_sprinting = True
                        else:
                            stop_all()
                            sweep_speed = 30 if (dist is not None and dist <= 25.0) else 120
                            self.rotate_mouse_raw(sweep_speed, 0)

                elif bot_state == "RUNNING":
                    if valid_door_box:
                        print("\n🚪 发现大门！切入最高优先级进门状态！")
                        stop_all()
                        bot_state = "APPROACH_DOOR"
                        is_skew_locked = False
                        last_aspect_ratio = 0.0
                        has_aligned_door = False
                        last_action_log = ""
                        global_progress_time = time.time()
                        continue
                    if toilet_box:
                        self.last_known_toilet_h = toilet_box['h']
                    if not toilet_box:
                        if time.time() - global_last_seen_time > 3.0:
                            last_h = getattr(self, 'last_known_toilet_h', 0)
                            if last_h > h * 0.45:
                                print("\n🧱 贴脸导致视野丢失！战术后退定距绕桩...")
                                stop_all()
                                set_key('s', True)
                                time.sleep(1.5)
                                set_key('s', False)
                                bot_state = "CIRCLING"
                                circle_start = time.time()
                                last_circle_pause_time = time.time()
                                last_action_log = ""
                                global_progress_time = time.time()
                                continue
                            else:
                                print("\n⚠️ 突击视野彻底丢失超 1.5s！退回罗盘奔袭...")
                                stop_all()
                                bot_state = "COMPASS_RUSH"
                                dist_history.clear()
                                global_progress_time = time.time()
                                continue
                        else:
                            last_h = getattr(self, 'last_known_toilet_h', 0)
                            if last_h < h * 0.35:
                                if last_action_log != "BLIND_RUSH_FAR":
                                    print("   👀 远距离视野闪断！保持惯性狂奔冲刺...")
                                    last_action_log = "BLIND_RUSH_FAR"

                                if not is_sprinting or keys_pressed['ctrl']:
                                    set_key('ctrl', False)
                                    set_key('w', False)  
                                    time.sleep(0.02)
                                    set_key('shift', True)
                                    set_key('w', True)
                                    is_sprinting = True
                            else:
                                if last_action_log != "BLIND_TOUCH_CLOSE":
                                    print("   👀 近战视野死角！保持记忆慢速盲摸...")
                                    last_action_log = "BLIND_TOUCH_CLOSE"
                                set_key('shift', False)
                                set_key('ctrl', True)
                                set_key('w', True)
                                is_sprinting = False
                            continue  
                    diff_x = toilet_box['x'] - center_x
                    if abs(diff_x) > 100.0:
                        if last_action_log != "VISUAL_ADJUST":
                            print(f"\n🛑 厕所偏离(偏差:{diff_x:.1f})！刹车纯视觉对正！")
                            stop_all()
                            last_action_log = "VISUAL_ADJUST"
                        self.rotate_mouse_raw(int(diff_x * 0.6), 0)
                    else:
                        toilet_ratio = toilet_box['h'] / h

                        if valid_door_box:
                            set_key('shift', False)
                            set_key('ctrl', True)
                            set_key('w', True)
                            if last_action_log != "FORCE_BRAKE":
                                print("   🚨 发现门框反光！紧急降速至静步...")
                                last_action_log = "FORCE_BRAKE"

                        elif toilet_ratio < 0.25:
                            if is_sprinting or keys_pressed['ctrl']:
                                set_key('shift', False)
                                set_key('ctrl', False)
                                set_key('w', False)  
                                time.sleep(0.02)
                                set_key('w', True)
                                is_sprinting = False
                            else:
                                set_key('shift', False)
                                set_key('ctrl', False)
                                set_key('w', True)

                            if last_action_log != "GEAR_3":
                                print("   🏃 目标尚远(三档)，解除疾跑，纯按 W 稳步前压...")
                                last_action_log = "GEAR_3"
                        elif toilet_ratio < 0.45:
                            if is_sprinting or not keys_pressed['ctrl']:
                                set_key('shift', False)
                                set_key('w', False)  
                                time.sleep(0.02)
                                set_key('ctrl', True)
                                set_key('w', True)
                                is_sprinting = False
                            else:
                                set_key('ctrl', True)
                                set_key('w', True)

                            if last_action_log != "GEAR_2":
                                print("   🚶 接近雷区(二档)，切入 Ctrl+W 静步索敌...")
                                last_action_log = "GEAR_2"
                        else:
                            if is_sprinting or not keys_pressed['ctrl']:
                                set_key('shift', False)
                                set_key('w', False) 
                                time.sleep(0.02)
                                set_key('ctrl', True)
                                set_key('w', True)
                                is_sprinting = False
                            else:
                                set_key('ctrl', True)
                                set_key('w', True)
                            if last_action_log != "GEAR_1":
                                print("   🛑 贴脸缓冲(一档)！防撞死漏门模式...")
                                last_action_log = "GEAR_1"
                        
                        self.rotate_mouse_raw(int(diff_x * 1.0), 0)
                        global_progress_time = time.time()

                    if toilet_box['h'] > h * 0.60:
                        if time.time() - global_last_door_time > 1.5:
                            print("\n🧱 厕所糊脸且无大门！战术后退定距绕桩...")
                            stop_all()
                            set_key('s', True)
                            time.sleep(1.5)
                            set_key('s', False)
                            bot_state = "CIRCLING"
                            circle_start = time.time()
                            last_circle_pause_time = time.time()
                            last_action_log = ""
                            global_progress_time = time.time()
                            continue

                elif bot_state == "CIRCLING":
                    global_progress_time = time.time()

                    if not toilet_box and not valid_door_box:
                        print("\n⚠️ 绕桩时丢失所有目标(无厕所无门)！强制退回罗盘！")
                        stop_all()
                        bot_state = "COMPASS_RUSH"
                        continue

                    if valid_door_box:
                        print("\n🚪 绕桩锁定大门！刹车切入大门突击！")
                        stop_all()
                        bot_state = "APPROACH_DOOR"
                        is_skew_locked = False
                        last_aspect_ratio = 0.0
                        has_aligned_door = False
                        last_action_log = ""
                        continue

                    if time.time() - last_circle_pause_time > 4.0:
                        stop_all()
                        for _ in range(12):
                            if self.is_paused: time.sleep(0.1); continue
                            if self.check_interrupt(): break
                            c_img, _ = self.capture_game_screen()
                            if c_img is None: continue
                            
                            res = self.yolo_model.predict(source=c_img, conf=0.5, classes=[0, 1], verbose=False,half=True, imgsz=640)
                            t_cx = None
                            found_door_in_pause = False
                            
                            for r in res:
                                for box in r.boxes:
                                    cls_id = int(box.cls[0].item())
                                    conf_val = box.conf[0].item()
                                    if cls_id == getattr(self, 'door_class_id', 1) and conf_val > 0.4:
                                        door_cx = (box.xyxy[0][0].item() + box.xyxy[0][2].item()) / 2
                                        if abs(door_cx - center_x) > 300:
                                            continue
                                        found_door_in_pause = True
                                        break
                                    if cls_id == getattr(self, 'toilet_class_id', 0) and conf_val > 0.7:
                                        t_cx = (box.xyxy[0][0].item() + box.xyxy[0][2].item()) / 2
                                if found_door_in_pause:
                                    break
                                    
                            if found_door_in_pause:
                                print("\n👀 [防漏门] 绕桩停顿校准时瞥见大门！紧急打断校准！")
                                break

                            if t_cx is not None:
                                self.rotate_mouse_raw(int((t_cx - center_x) * 0.6), 0)
                                if abs(t_cx - center_x) < 30: break
                            else:
                                self.rotate_mouse_raw(60, 0)
                            time.sleep(0.04)
                        last_circle_pause_time = time.time()
                    else:
                        # ==========================================
                        # 🚀 智能导航绕桩 (向心寻路引擎)
                        # ==========================================
                        tx_compass = self.find_target_on_compass(game_img)
                        if tx_compass is not None:
                            self.last_valid_tx_compass = tx_compass
                        target_tx = tx_compass if tx_compass is not None else getattr(self, 'last_valid_tx_compass', None)
                        # 动态判断最短路径
                        if target_tx is not None and target_tx > center_x:
                            set_key('a', False)
                            set_key('d', True)  # 门在右侧，向右走捷径
                            circle_dir_log = "[D向右]"
                        else:
                            set_key('d', False)
                            set_key('a', True)  # 门在左侧(或偏后)，向左走捷径
                            circle_dir_log = "[A向左]"
                        if is_sprinting:
                            set_key('shift', False)
                            is_sprinting = False
                        if toilet_box:
                            self.rotate_mouse_raw(int((toilet_box['x'] - center_x) * 0.6), 0)
                            box_ratio = toilet_box['h'] / h

                            if box_ratio < 0.40:
                                set_key('w', True)
                                set_key('s', False)
                                if last_action_log != "CIRCLE_IN":
                                    print(f"   🔄 绕桩偏远 {circle_dir_log} (比例:{box_ratio:.2f})，按住 W 向心切入...")
                                    last_action_log = "CIRCLE_IN"
                            elif box_ratio > 0.55:
                                set_key('w', False)
                                set_key('s', True)
                                if last_action_log != "CIRCLE_OUT":
                                    print(f"   🔄 绕桩贴脸 {circle_dir_log} (比例:{box_ratio:.2f})，按住 S 向外拉开...")
                                    last_action_log = "CIRCLE_OUT"
                            else:
                                set_key('w', False)
                                set_key('s', False)
                                if last_action_log != "CIRCLE_PERFECT":
                                    print(f"   🔄 黄金距离绕桩中 {circle_dir_log} (比例:{box_ratio:.2f})...")
                                    last_action_log = "CIRCLE_PERFECT"

                    if time.time() - circle_start > 30.0:
                        print("\n⚠️ 绕桩超过15秒未发现门，强行切回罗盘带离...")
                        stop_all()
                        bot_state = "COMPASS_RUSH"

                elif bot_state == "APPROACH_DOOR":
                    if last_action_log == "":
                        self.door_height_reached = False

                    if not valid_door_box:
                        time_since_lost = time.time() - global_last_door_time

                        if time_since_lost < 1:
                            if last_action_log != "BLIND_RUSH":
                                print("\n⚠️ 贴脸大门视野闪断！保持 Ctrl+W 惯坚盲进！")
                                last_action_log = "BLIND_RUSH"
                            set_key('shift', False)
                            set_key('a', False)
                            set_key('d', False)
                            set_key('ctrl', True)
                            set_key('w', True)
                            global_progress_time = time.time()
                        elif time_since_lost < 2.2:
                            stop_all()
                            if last_action_log != "WAIT_DOOR":
                                print(f"   ⏳ 视野闪断超1.5秒，原地等待扫描F...")
                                last_action_log = "WAIT_DOOR"
                        else:
                            stop_all()
                            print("\n⚠️ 彻底丢失大门超 3.5s！(超时触发)")
                            self.door_height_reached = False 
                            if toilet_box:
                                print("   🔄 视野内存在厕所，平滑降级为【厕所突击】(RUNNING)...")
                                bot_state = "RUNNING"
                            else:
                                print("   🧭 视野内无厕所/大门，彻底退回【罗盘奔袭】...")
                                bot_state = "COMPASS_RUSH"

                            last_action_log = ""
                            global_progress_time = time.time()
                            continue
                    else:
                        diff_door = valid_door_box['x'] - center_x
                        door_h = valid_door_box['h']  
                        aspect_ratio = valid_door_box['w'] / door_h  
                        
                        if door_h >= 225:
                            self.door_height_reached = True
                        has_reached_height = getattr(self, 'door_height_reached', False)
                        # 🚨 核心修复1：防暴毙急刹车！
                        # 如果门在屏幕极度边缘（偏差>180），坚决不准按 W 往前盲走！
                        # 必须松开所有移动键，专心把头转正！
                        dynamic_brake_limit = 400 if aspect_ratio < 0.45 else 180
                        if abs(diff_door) > dynamic_brake_limit:
                            if last_action_log != "DOOR_ADJUST":
                                print(
                                    f"\n   🛑 大门严重偏离(偏差:{diff_door:.1f} > 阈值{dynamic_brake_limit})！急刹车专心转正！")
                                last_action_log = "DOOR_ADJUST"
                            stop_all()  # 💡 致命一步：松开所有按键，踩死刹车！
                            self.rotate_mouse_raw(int(diff_door * 0.8), 0)  # 快速大角度把头甩正
                            global_progress_time = time.time()
                            continue

                        if not has_reached_height and aspect_ratio < 0.45:
                            set_key('a', False)
                            set_key('d', False)
                            set_key('shift', False)
                            set_key('ctrl', True)
                            set_key('w', True)
                            if last_action_log != "APPROACH_FAR":
                                print(f"\n   🚶 大门尚远 (高度:{door_h:.1f} < 200px)，保持 Ctrl+W 直线逼近...")
                                last_action_log = "APPROACH_FAR"
                            # self.rotate_mouse_raw(int(diff_door * 1.5), 0)
                            smooth_glide_mouse(diff_door)
                            global_progress_time = time.time()
                            continue

                        if aspect_ratio >= 0.45:
                            # if door_h < 500:
                            #     has_aligned_door = True
                            if abs(diff_door) <= 200:
                                has_aligned_door = True

                        if not has_aligned_door:
                            set_key('w', False)
                            set_key('shift', False)
                            set_key('ctrl', True)
                            # if last_aspect_ratio == 0.0:
                            #     last_aspect_ratio = aspect_ratio
                            #     ratio_check_time = time.time()
                            # if 'start_check_door_x' not in locals() or last_aspect_ratio == 0.0:
                            #     start_check_door_x = valid_door_box['x']

                            # 👇 核心修复：把所有“前世记忆”捆绑在一起，强制物理清洗！
                            if last_aspect_ratio == 0.0:
                                last_aspect_ratio = aspect_ratio
                                start_check_door_x = valid_door_box['x']  # 1. 强制刷新起点坐标，防瞬间百像素漂移

                                # ==========================================================
                                # 🚀 绝活：利用偏心率“看一眼”决定初始方向，彻底告别盲猜 A！
                                # ==========================================================
                                if toilet_box:
                                    eccentricity = (valid_door_box['x'] - toilet_box['x']) / toilet_box['w']
                                    # 黄金中心点大约在 0.19 左右
                                    if eccentricity > 0.19:
                                        skew_dir = 'd'
                                        print(
                                            f"   👁️ [精准起步] 偏心率 {eccentricity:.3f} (大门偏右) -> 起步方向锁定为 [D]")
                                    else:
                                        skew_dir = 'a'
                                        print(
                                            f"   👁️ [精准起步] 偏心率 {eccentricity:.3f} (大门偏左) -> 起步方向锁定为 [A]")
                                else:
                                    skew_dir = 'a'  # 万一极其贴脸没看到外墙，兜底盲猜 A
                                    print("   👁️ [精准起步] 视野无厕所外框，兜底盲猜起步 [A]")
                                # ==========================================================

                                ratio_check_time = time.time()

                            door_moved_dist = abs(valid_door_box['x'] - start_check_door_x)
                            if door_moved_dist > 100.0:
                                if not is_skew_locked and aspect_ratio < last_aspect_ratio - 0.02:
                                    skew_dir = 'd' if skew_dir == 'a' else 'a'
                                    is_skew_locked = True
                                    print(f"   🔄 [位移结算] 比例下降！方向错误！永久锁定方向至 [{skew_dir.upper()}]！")
                                elif not is_skew_locked:
                                    is_skew_locked = True
                                start_check_door_x = valid_door_box['x']
                                last_aspect_ratio = aspect_ratio

                            lock_status = "(已锁死)" if is_skew_locked else "(探测中)"
                            if last_action_log != "MOVE_ADJUST":
                                print(f"\n   [首要任务] 📐调整比例(当前:{aspect_ratio:.2f} < 0.45) -> Ctrl + [{skew_dir.upper()}] {lock_status}")
                                last_action_log = "MOVE_ADJUST"

                            anti_dir = 'd' if skew_dir == 'a' else 'a'

                            if abs(diff_door) > 200:
                                set_key(anti_dir, False)
                                set_key(skew_dir, False) 
                                # self.rotate_mouse_raw(int(diff_door * 1.5), 0)
                                smooth_glide_mouse(diff_door)

                            else:
                                set_key(anti_dir, False)
                                set_key(skew_dir, True) 
                                if time.time() - last_space_time > 4:
                                    pydirectinput.press('space')
                                    last_space_time = time.time()
                                # self.rotate_mouse_raw(int(diff_door * 0.8), 0)
                                smooth_glide_mouse(diff_door)
                            global_progress_time = time.time()
                        else:
                            set_key('a', False)
                            set_key('d', False)
                            set_key('shift', False)
                            set_key('ctrl', True)
                            set_key('w', True)
                            global_progress_time = time.time()
                            
                            if last_action_log != "CHARGE_WALK":
                                print(f"\n   [贴脸吸附] 🎯已达标，死冲模式触发！ -> 保持 Ctrl+W 极速修正偏差！")
                                last_action_log = "CHARGE_WALK"

                            # self.rotate_mouse_raw(int(diff_door * 1.5), 0)
                            smooth_glide_mouse(diff_door)
                elif bot_state == "VERIFY_DOOR":
                    global_progress_time = time.time()
                    time.sleep(0.1)
                    c_img, _ = self.capture_game_screen()
                    if c_img is None: continue
                    found_f = False
                    found_door = False
                    score_f = 0.0
                    if f_tmpl is not None:
                        res_f = cv2.matchTemplate(c_img, f_tmpl, cv2.TM_CCOEFF_NORMED)
                        score_f = cv2.minMaxLoc(res_f)[1]
                        if score_f > 0.72: found_f = True
                    for tmpl in open_door_templates:
                        res_d = cv2.matchTemplate(c_img, tmpl, cv2.TM_CCOEFF_NORMED)
                        if cv2.minMaxLoc(res_d)[1] > 0.7:
                            found_door = True
                            break
                    if found_f:
                        verify_count += 1
                        if verify_count >= 2:
                            if found_door:
                                print(f"   🎯 核验为【大门】！(F:{score_f:.2f}, 门:{found_door}) 按 F 交互，准备突入！")
                                win32api.keybd_event(0x46, 0, 0, 0)
                                time.sleep(0.05)
                                win32api.keybd_event(0x46, 0, win32con.KEYEVENTF_KEYUP, 0)
                                time.sleep(0.4)
                                bot_state = "ITEM_PICKUP"
                            else:
                                print(f"   📦 核验为【物资】！(F:{score_f:.2f}, 无门) 直接按 F 拾取！")
                                win32api.keybd_event(0x46, 0, 0, 0)
                                time.sleep(0.05)
                                win32api.keybd_event(0x46, 0, win32con.KEYEVENTF_KEYUP, 0)
                                time.sleep(0.2)  
                                bot_state = "COMPASS_RUSH"
                    else:
                        print(f"   ⚠️ F 提示闪断或误报 (F置信度:{score_f:.2f})，退回罗盘奔袭...")
                        pydirectinput.press('s')
                        pydirectinput.press('s')
                        stop_all()
                        bot_state = "COMPASS_RUSH"

                elif bot_state == "ITEM_PICKUP":
                    global_progress_time = time.time()
                    print("\n   🏃 门已开，直冲突入！...")
                    set_key('w', True)
                    rush_start = time.time()
                    while time.time() - rush_start < 2.0:
                        if self.is_paused:
                            set_key('w', False)
                            time.sleep(0.1)
                            rush_start += 0.1
                            continue
                        else:
                            set_key('w', True)
                        if self.check_interrupt(): break
                        time.sleep(0.04)

                    print("\n   ✅ 突入完成！执行搜刮战术动作！")
                    stop_all()

                    set_key('a', True)
                    time.sleep(0.6)
                    set_key('a', False)
                    pydirectinput.press('c')
                    set_key('s', True)
                    time.sleep(0.5)
                    set_key('s', False)
                    pydirectinput.press('m')
                    time.sleep(0.2)
                    pydirectinput.press('tab')
                    time.sleep(1.0)

                    if hasattr(self, 'pickup_all_items_in_tab'):
                        self.pickup_all_items_in_tab(current_window_info)

                    pydirectinput.press('tab')
                    time.sleep(0.5)

                    last_afk_move_time = time.time()
                    bot_state = "AFK"

                elif bot_state == "AFK":
                    global_progress_time = time.time()
                    if time.time() - last_afk_move_time > random.uniform(15.0, 25.0):
                        if random.random() > 0.7:
                            self.rotate_mouse_raw(random.choice([-20, 20]), 0)
                        else:
                            k = random.choice(['a', 'd'])
                            set_key(k, True)
                            time.sleep(0.02)
                            set_key(k, False)
                        last_afk_move_time = time.time()
                    time.sleep(1)

            # ==========================================
            # 🌟 全局防死锁判定 (终极安全护航)
            # ==========================================
            if time.time() - global_progress_time > 10.0:
                print(f"\n⚠️ [护航机制] 监测到系统僵死 (10秒未产生有效进度)！准备夺回焦点...")
                stop_all()

                try:
                    if hasattr(self, 'pubg_hwnd') and self.pubg_hwnd:
                        win32gui.SetForegroundWindow(self.pubg_hwnd)
                        rect = win32gui.GetWindowRect(self.pubg_hwnd)
                        cx = rect[0] + (rect[2] - rect[0]) // 2
                        cy = rect[1] + (rect[3] - rect[1]) // 2
                        win32api.SetCursorPos((cx, cy))
                except:
                    pass

                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                time.sleep(0.05)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                time.sleep(0.3)
                self.compass_align(current_window_info)

                global_progress_time = time.time()
                bot_state = "COMPASS_RUSH"

            # ==========================================
            # 📊 实时仪表盘输出
            # ==========================================
            if bot_state == "COMPASS_RUSH" and not entered_target_zone:
                dist_str = f"{dist:.1f}" if dist is not None else "??"
                print(f"🧭 罗盘导航中... 距标点: {dist_str}px (未进20px核心区) | 👁️F置信:{current_f_score:.2f}    ", end='\r')
            else:
                active_keys = "+".join([k.upper() for k, v in keys_pressed.items() if v])
                if not active_keys: active_keys = "无"
                print(f"[{bot_state}] 👁️F置信:{current_f_score:.2f} | ⌨️按:{active_keys}          ", end='\r')

        except Exception as e:
            import traceback
            print(f"\n❌ 地面执行发生严重错误:\n{traceback.format_exc()}")
        finally:
            stop_all()
            # door_recorder.close()  # 截图诊断暂时停用
            print("\n🏁 自动地面突击序列彻底结束，所有按键已释放。")

    # ----------------------------------------------------------------------
    # 主大厅循环保持不变
    # ----------------------------------------------------------------------
    def run(self):
        print("\n" + "=" * 60)
        print("🎮 绝地求生 自动匹配挂机引擎启动")
        print("=" * 60)
        # 🛡️ 新增：启动安全锁，清空桌面防误点！
        print("🛡️ 启动防误触安全锁：正在清空桌面图标...")
        self.toggle_desktop_icons(show=False)
        # 🚀 核心修改：如果一开始没找到游戏，不要退出！直接调用我们的强拉函数！
        if not self.bring_pubg_to_front():
            print("\n💤 检测到游戏未运行，正在执行全自动唤醒协议...")
            self.force_restart_pubg()  # 直接用 Steam 协议把游戏拉起来！
        self.mid_game_counter = 0
        window_lost_count = 0

        # 🌟 1. 初始化看门狗定时器
        watchdog_timer = time.time()
        map_wait_started = None

        try:
            while self.running:
                if self.is_paused: time.sleep(1); continue
                if keyboard.is_pressed('end'): break

                # 点击开始后最多等待地图5分钟，重复点击和加载不延长期限
                timeout_started = map_wait_started if map_wait_started is not None else watchdog_timer
                if time.time() - timeout_started >= 300:
                    print("\n🚨 [超时看门狗] 5分钟无进展(疑似卡死/黑屏/断网)，执行拔管重连！")
                    self.force_restart_pubg()
                    map_wait_started = None
                    watchdog_timer = time.time()
                    window_lost_count = 0  # 重启后重置窗口计数
                    continue

                if not win32gui.IsWindow(self.pubg_hwnd):
                    window_lost_count += 1
                    print(f"⚠️ 警告：检测不到游戏窗口 ({window_lost_count}/3)...")
                    time.sleep(2.0)
                    if window_lost_count >= 3:
                        # 🚀 3. 闪退拦截：不再关闭脚本，而是直接强拉游戏！
                        print("\n💥 [闪退拦截] 确认游戏已经崩溃或被关闭！正在紧急重新拉起...")
                        self.force_restart_pubg()
                        map_wait_started = None

                        # 🌟 重拉游戏后，必须重置这两个计数器
                        window_lost_count = 0
                        watchdog_timer = time.time()
                    continue
                else:
                    window_lost_count = 0

                if self.is_waiting_for_jump: time.sleep(1); continue

                game_img, window_info = self.capture_game_screen()
                if game_img is None or window_info is None: time.sleep(2); continue

                if self.handle_endgame(game_img, window_info):
                    self.has_marked_this_match = False
                    self.is_waiting_for_jump = False
                    self.best_jump_point_coords = None
                    self.initial_target_coords = None
                    continue

                if hasattr(self, 'handle_password_input'):
                    if self.handle_password_input(game_img, window_info): continue

                f_start, c_start, pos_start = self.find_image(game_img, 'start_btn')
                f_load, _, _ = self.find_image(game_img, 'loading')
                f_naozhong, _, _ = self.find_image(game_img, 'naozhong')
                f_count4, c_count4, _ = self.find_image(game_img, 'count4')
                if f_naozhong:
                    map_wait_started = None
                    watchdog_timer = time.time()
                now = time.strftime("%H:%M:%S")

                if f_start:
                    print(f"\n[{now}] 🖱️ 检测到【大厅界面】(得分:{c_start:.2f})，开始【双击】匹配")
                    # 🌟 4. 喂狗：看到开始按钮，说明游戏健康，重置看门狗寿命
                    watchdog_timer = time.time()

                    self.has_marked_this_match = False
                    self.is_waiting_for_jump = False
                    self.best_jump_point_coords = None
                    self.initial_target_coords = None
                    self.mid_game_counter = 0

                    win_x, win_y = window_info['screen_pos']
                    bor_x, bor_y = window_info['border']
                    real_w, real_h = window_info['real_client_size']

                    real_click_x = int(pos_start[0] * (real_w / 1920.0))
                    real_click_y = int(pos_start[1] * (real_h / 1080.0))
                    win32api.SetCursorPos((win_x + bor_x + real_click_x, win_y + bor_y + real_click_y))
                    time.sleep(0.1);
                    pyautogui.click();
                    time.sleep(0.5);
                    pyautogui.click();
                    if map_wait_started is None:
                        map_wait_started = time.time()
                    time.sleep(5)

                elif f_load:
                    print(f"[{now}] ⏳ 画面加载中...", end="\r", flush=True)
                    time.sleep(3)

                elif not self.has_marked_this_match:
                    if not f_naozhong:
                        print(f"[{now}] 🗺️ 正在试探：按 M 键打开地图... (等待 naozhong.png)    ", end="\r", flush=True)
                        pydirectinput.keyDown('m');
                        time.sleep(0.1);
                        pydirectinput.keyUp('m');
                        time.sleep(1.5)
                        continue

                    mx, my = window_info['map_offset']
                    map_img = game_img[my:my + self.MAP_SIZE, mx:mx + self.MAP_SIZE]
                    flight_path = self.extract_flight_path_v2(map_img)

                    is_real_flight_path = False
                    if flight_path and len(flight_path) > 50:
                        xs, ys = [p[0] for p in flight_path], [p[1] for p in flight_path]
                        if (max(xs) - min(xs)) > 400 or (max(ys) - min(ys)) > 400: is_real_flight_path = True

                    if not is_real_flight_path and not f_count4:
                        self.mid_game_counter += 1
                        print(f"[{now}] ⏳ 未提取到航线与倒计时，防误判确认中 ({self.mid_game_counter}/4)...", end="\r",
                              flush=True)
                        if self.mid_game_counter >= 4:
                            print(f"\n\n[{now}] ⚠️ 连续多次确认无果，判定游戏已在【中途阶段】！放弃识别返回大厅...")
                            pydirectinput.keyDown('m');
                            time.sleep(0.1);
                            pydirectinput.keyUp('m');
                            time.sleep(5.0)
                            self.mid_game_counter = 0
                        else:
                            time.sleep(2.0)
                        continue
                    else:
                        self.mid_game_counter = 0

                    if is_real_flight_path:
                        print(f"\n[{now}] ✅ 识别到闹钟并成功提取到真实航线！确认已准备就绪！")
                        # 🌟 5. 喂狗：成功上飞机，说明游戏健康，重置看门狗寿命
                        watchdog_timer = time.time()

                        if self.smart_mark(flight_path, window_info) is not False:
                            self.has_marked_this_match = True
                            print("\n🛬 跳伞落地完毕，主引擎正式启动地面突击！")
                            self.start_auto_run(window_info)

                            # 🌟 6. 地面战斗结束（无论是死亡还是吃鸡）出来后，再次喂狗
                            watchdog_timer = time.time()
                    else:
                        print(f"[{now}] ⏳ 倒计时识别中 (得分:{c_count4:.2f})，航线加载中，关闭地图等待刷新...")
                        pydirectinput.keyDown('m');
                        time.sleep(0.1);
                        pydirectinput.keyUp('m');
                        time.sleep(3.0)

        except KeyboardInterrupt:
            pass
        except Exception as e:
            import traceback
            print(f"\n❌ 发生严重错误:\n{traceback.format_exc()}")
        finally:
            print("\n\n🛑 接收到退出指令，安全释放按键。")
            self.stop_all_movement()
            self.running = False
            # 🛡️ 新增：解除安全锁，恢复桌面！
            print("🛡️ 释放安全锁：正在恢复桌面图标...")
            self.toggle_desktop_icons(show=True)
