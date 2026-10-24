# pubg2/main.py
import time
import keyboard
import ctypes
import pyautogui
import pydirectinput
import sys

# 💡 强制声明 DPI 感知，完美解决屏幕缩放导致的截图抓瞎问题！
try:
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass

pyautogui.FAILSAFE = False
pydirectinput.FAILSAFE = False

# 导入业务机器人类
from logic.bot import PUBGSmartMarkerV9

if __name__ == "__main__":
    controller = PUBGSmartMarkerV9()
    print("\n" + "=" * 50)
    print("🎮 脚本已就绪！请选择模式：")
    print("1. 正常挂机模式 (全自动拉起游戏 + 匹配跳伞)")
    print("2. 靶场单步测试模式 (请先进入游戏并标记黄点)")
    print("=" * 50)

    try:
        while True:
            # 🌟 核心修改：使用原生 input() 完美兼容所有手机远程控制软件！
            # 注意：手机端输入 1 之后，记得按一下手机键盘上的【回车/发送】键
            choice = input("等待输入... (请输入 1 或 2 并按回车): ").strip()
            controller.init_yolo()
            if choice == '1':
                print("\n🚀 正在为您启动全自动挂机主循环...")
                time.sleep(0.5)
                controller.run()
                break

            elif choice == '2':
                print("\n🚀 正在为您自动切回游戏...")
                controller.init_yolo()
                if controller.bring_pubg_to_front():
                    time.sleep(0.5)  # 缓冲时间
                    print("🚀 成功切回游戏！请按下【F8】键立即激活地面测试...")
                    keyboard.wait('f8')
                    controller.start_auto_run()
                else:
                    print("\n💤 测试模式需要游戏处于运行状态！正在尝试为您一键拉起...")
                    if hasattr(controller, 'force_restart_pubg'):
                        controller.force_restart_pubg()
                        print("🚀 游戏已拉起，请重新运行脚本选择模式 2 进行地面测试。")
                    else:
                        print("❌ 未找到强拉函数，请先手动打开游戏。")
                break

            else:
                # 防呆设计：如果手抖输入了其他字符，提示重新输入
                print("⚠️ 输入无效，请输入数字 1 或 2！")

    except Exception as e:
        print(f"🚨 主引导入口发生未知异常: {e}")
    finally:
        try:
            keyboard.unhook_all()
        except:
            pass

            # 2. 🛡️ 终极防线：无论程序怎么死，死前一定要把桌面还给玩家！
        print("\n🛡️ 释放安全锁：正在恢复桌面图标...")
        try:
            if hasattr(controller, 'toggle_desktop_icons'):
                controller.toggle_desktop_icons(show=True)
        except Exception as e:
            print(f"恢复桌面失败: {e}")

        print("👋 引导程序安全退出。")
        sys.exit(0)
