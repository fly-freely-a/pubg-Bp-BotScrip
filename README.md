# PUBG 全自动挂机与智能目标检测脚本 (pubg-Bot-Scrip)

这是一个基于 Python 开发的 PUBG (绝地求生) 自动化挂机与图像识别辅助脚本。项目核心结合了 **YOLOv8 (Ultralytics)** 目标检测框架，用于实时识别游戏内场景，并结合底层键鼠驱动实现自动化操作。本项目是一款完全免费开源的PUBG自动挂机脚本，现阶段仅支持在艾伦格厕所点位自动挂机刷取BP，后续会迭代适配更多地图点位。实测在无BP加成卡的环境下，单日可获取约2w BP，作者与友人长期测试使用未出现封号情况，但不代表绝对安全。
游戏内语言需要设置中文简体，因为识图只做了中文的，且关闭色盲模式，分辨率画质帧数无要求限制，但画面比例最好为16:9，比如1280x720，1920x1080，2560x1440，不过既然挂机，建议1280x720，画质和渲染比例也可以适当降低。
---

## ✨ 核心功能

### 紧急停止

脚本显示快捷键已启动后，在任意窗口按 **END** 或 **Ctrl+Shift+F12**，即可释放键盘和鼠标按键、恢复桌面图标并退出整个脚本，包括等待 F8 和执行长动作期间。停止后需要重新启动脚本。**HOME** 仅用于暂停/继续，不作为紧急停止键。

### 门旁 F 提示识别

`Config.IMAGE_DIR` 必须包含项目自带的 `F.png`。脚本使用多种尺寸的灰度模板匹配，保持 0.72 阈值，并在停止移动后再次核验提示才发送 F。对门阶段每两秒输出一次交互诊断；门已接近但 F 匹配未达阈值时，每十秒将带匹配位置和分数的截图覆盖保存到项目的 `debug/interaction/door_prompt.png`，可用于检查实际图标与模板的差异。该匹配仅识别 F 图标，不能识别“推门”等文字，也不保证游戏已经成功开门。

- **🚀 全自动挂机模式**：全自动拉起游戏客户端、自动参与匹配、自动完成跳伞等循环操作。
- **🧠 YOLOv8 智能目标识别**：内置 YOLOv8 深度学习模型，可对游戏画面（厕所、门框等）进行高精度实时检测。
- **🛡️ 驱动级键鼠模拟**：采用 `PyDirectInput` 绕过常规检测，模拟原生硬件级输入，确保游戏内视角转向与按键精准有效。

---

## 🛠️ 环境准备与安装指南

为了保证脚本在游戏运行时的图像识别流畅度 (FPS)，强烈建议电脑配备 **NVIDIA 显卡** 以开启 CUDA 硬件加速。

### 1. 克隆或下载项目
在本地终端执行或直接在 GitHub 下载 ZIP 解压：
```bash
git clone [https://github.com/xxsybzd/pubg-Bot-Scrip.git](https://github.com/xxsybzd/pubg-Bot-Scrip.git)
cd pubg-Bot-Scrip
2. 安装基础依赖
确保你的电脑已安装 Python 3.13 或以上版本。在项目根目录下运行以下命令，一键安装所有必要的第三方库（包含 OpenCV、YOLOv8 核心库、PyAutoGUI 等）：
pip install -r requirements.txt

3. 配置显卡加速（可选，强烈推荐 🚀）
默认安装的 PyTorch 可能是 CPU 版本，运行 YOLOv8 会有较大延迟。若有 NVIDIA 显卡，请执行以下命令切换为 CUDA 加速版本：
# 卸载默认的 CPU 版 torch
pip uninstall torch torchvision torchaudio

# 安装对应 CUDA 版本的 PyTorch（以 CUDA 12.4 为例，可根据自身显卡驱动调整）
pip install torch torchvision torchaudio --index-url [https://download.pytorch.org/whl/cu124](https://download.pytorch.org/whl/cu124)

最后config.py文件设置路径
## ⚙️ 核心参数配置（运行前必看 ⚠️）

在首次运行脚本前，请务必先打开项目中的 `config.py` 文件，根据你本地的实际情况修改以下核心配置（参考代码中的 `class Config`）：

### 1. 核心配置项说明

```python
class Config:
    # 1. 游戏截图/图片资源存放路径
    # ⚠️ 必须修改为你本地电脑上的绝对路径，否则程序无法读取和保存图片！
    IMAGE_DIR = r"E:\pythonDemo\pubg\image"

    # 2. YOLOv8 模型权重路径
    # 默认支持原生的 .pt 格式，或导出的 TensorRT .engine 加速格式（推荐路径指向你的 best 权重文件）
    MODEL_PATH = r"E:\pythonDemo\aipubg\runs\detect\pubg_toilet_model-7\weights\best.pt"

    # 3. 游戏二级密码
    # 用于全自动挂机场景下自动解锁二级密码。请填入你自己的 6 位游戏二级密码
    SECONDARY_PASSWORD = "你的二级密码"
