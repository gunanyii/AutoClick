import tkinter as tk
from tkinter import ttk, simpledialog
import pyautogui
import time
import threading
import json
from pynput import mouse, keyboard
from pynput.keyboard import Key, KeyCode
CONFIG_FILE = "clicker_tasks.json"

class AutoClicker:
    def __init__(self, root):
        self.root = root
        self.running = False
        self.recording = False
        self.click_thread = None
        self.record_listener = None
        self.tasks = {}
        self.current_task = None
        self.custom_start_key = KeyCode.from_char('p')
        self.setup_ui()
        self.load_settings()
        self.setup_hotkeys()
        self.set_window_topmost(True)
        self.last_position = None
        self.root.bind("<<PositionUpdate>>", self.update_progress)
    def setup_ui(self):
        """创建并布局UI组件"""
        self.root.geometry("1070x1000")
        style = ttk.Style()
        style.theme_use('clam')
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        # 任务管理区域
        task_frame = ttk.LabelFrame(main_frame, text="任务管理", padding=10)
        task_frame.grid(row=0, column=0, columnspan=2, sticky='ew', pady=5)
        ttk.Label(task_frame, text="任务名称:").grid(row=0, column=0, sticky='w')
        self.task_name_entry = ttk.Entry(task_frame, width=25)
        self.task_name_entry.grid(row=0, column=1, padx=5)
        btn_frame = ttk.Frame(task_frame)
        btn_frame.grid(row=0, column=2, padx=5)
        ttk.Button(btn_frame, text="保存任务", command=self.save_task).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="删除任务", command=self.delete_task).pack(side=tk.LEFT, padx=2)
        self.task_list = tk.Listbox(task_frame, height=6, width=30)
        self.task_list.grid(row=1, column=0, columnspan=3, pady=5, sticky='ew')
        self.task_list.bind("<<ListboxSelect>>", self.load_task)
        # 位置管理区域
        pos_frame = ttk.LabelFrame(main_frame, text="位置管理", padding=10)
        pos_frame.grid(row=1, column=0, sticky='nsew', pady=5)
        self.pos_list = tk.Listbox(pos_frame, height=8, width=35)
        self.pos_list.pack(fill=tk.BOTH, expand=True)
        self.pos_list.bind("<Double-1>", self.edit_position_delay)
        pos_btn_frame = ttk.Frame(pos_frame)
        pos_btn_frame.pack(pady=5)
        self.record_btn = ttk.Button(pos_btn_frame, text="开始录制", command=self.toggle_recording)
        self.record_btn.pack(side=tk.LEFT, padx=2)
        ttk.Button(pos_btn_frame, text="删除位置", command=self.delete_position).pack(side=tk.LEFT, padx=2)
        ttk.Button(pos_btn_frame, text="清空位置", command=self.clear_positions).pack(side=tk.LEFT, padx=2)
        # 参数设置区域
        setting_frame = ttk.LabelFrame(main_frame, text="设置", padding=10)
        setting_frame.grid(row=1, column=1, sticky='nsew', pady=5)
        ttk.Label(setting_frame, text="位置延时（秒）:").grid(row=0, column=0, sticky='w')
        self.pos_delay_entry = self.create_validated_entry(setting_frame, default="1.0")
        self.pos_delay_entry.grid(row=0, column=1, pady=2)
        ttk.Label(setting_frame, text="任务间隔（秒）:").grid(row=1, column=0, sticky='w')
        self.task_delay_entry = self.create_validated_entry(setting_frame, default="1.0")
        self.task_delay_entry.grid(row=1, column=1, pady=2)
        self.loop_var = tk.BooleanVar()
        ttk.Checkbutton(setting_frame, text="循环执行", variable=self.loop_var).grid(row=2, column=0, columnspan=2,
                                                                                     sticky='w')
        hotkey_frame = ttk.Frame(setting_frame)
        hotkey_frame.grid(row=3, column=0, columnspan=2, pady=5)
        ttk.Label(hotkey_frame, text="快捷键:").pack(side=tk.LEFT)
        self.key_entry = ttk.Entry(hotkey_frame, width=5)
        self.key_entry.insert(0, "p")
        self.key_entry.pack(side=tk.LEFT, padx=2)
        ttk.Button(hotkey_frame, text="设置", command=self.set_custom_key).pack(side=tk.LEFT)
        self.topmost_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(setting_frame, text="窗口顶置", variable=self.topmost_var,
                        command=lambda: self.set_window_topmost(self.topmost_var.get())).grid(row=4, column=0,
                                                                                              columnspan=2, sticky='w')
        # 状态控制区域
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=2, column=0, columnspan=2, pady=10)
        self.start_btn = ttk.Button(control_frame, text="开始 (p)", command=self.toggle_click)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        self.status_label = ttk.Label(control_frame, text="就绪")
        self.status_label.pack(side=tk.LEFT, padx=5)
        self.coord_label = ttk.Label(control_frame, text="坐标: (0, 0)")
        self.coord_label.pack(side=tk.RIGHT, padx=5)
        # 实时坐标跟踪
        self.mouse_listener = mouse.Listener(on_move=self.update_coord_display)
        self.mouse_listener.daemon = True
        self.mouse_listener.start()
        # 配置行列权重
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)
    def create_validated_entry(self, parent, default):
        """创建带验证的输入框"""
        vcmd = (parent.register(self.validate_number), '%P')
        entry = ttk.Entry(parent, width=10, validate='key', validatecommand=vcmd)
        entry.insert(0, default)
        return entry
    def validate_number(self, value):
        """验证数字输入"""
        if value == "" or (value.count('.') <= 1 and value.replace('.', '').isdigit()):
            return True
        return False
    def update_coord_display(self, x, y):
        """实时更新坐标显示"""
        self.coord_label.config(text=f"坐标: ({int(x)}, {int(y)})")
        self.last_position = (x, y)
    def setup_hotkeys(self):
        """设置热键监听"""
        self.keyboard_listener = keyboard.Listener(on_press=self.handle_hotkey)
        self.keyboard_listener.daemon = True
        self.keyboard_listener.start()
    def handle_hotkey(self, key):
        """处理热键事件"""
        try:
            if key == self.custom_start_key:
                self.toggle_click()
        except AttributeError:
            pass
    def set_custom_key(self):
        """设置自定义热键"""
        key_name = self.key_entry.get().strip().lower()
        try:
            if hasattr(Key, key_name):
                self.custom_start_key = getattr(Key, key_name)
            else:
                self.custom_start_key = KeyCode.from_char(key_name)
            self.start_btn.config(text=f"开始 ({key_name})")
        except Exception:
            pass
    def toggle_click(self):
        """切换点击状态"""
        if self.running:
            self.stop_clicking()
        else:
            if not self.pos_list.size():
                return
            self.start_clicking()
    def start_clicking(self):
        """开始执行点击"""
        self.running = True
        self.start_btn.config(text="停止")
        self.status_label.config(text="运行中...")
        positions = []
        for item in self.pos_list.get(0, tk.END):
            parts = item.split(" 延时: ")
            coords = parts[0][1:-1].split(", ")
            positions.append((
                float(coords[0]),
                float(coords[1]),
                float(parts[1].replace("秒", ""))
            ))
        self.click_thread = threading.Thread(
            target=self.execute_clicks,
            args=(positions, float(self.task_delay_entry.get())),
            daemon=True
        )
        self.click_thread.start()
    def execute_clicks(self, positions, task_delay):
        """执行点击操作"""
        try:
            while self.running:
                for index, (x, y, delay) in enumerate(positions):
                    if not self.running:
                        break
                    self.root.event_generate("<<PositionUpdate>>",
                                             when="tail",
                                             data={"current": index + 1, "total": len(positions)})
                    pyautogui.moveTo(x, y)
                    pyautogui.click()
                    time.sleep(delay)
                if not self.loop_var.get():
                    break
                time.sleep(task_delay)
        finally:
            self.root.after(0, self.stop_clicking)
    def stop_clicking(self):
        """停止点击"""
        self.running = False
        self.start_btn.config(text="开始")
        self.status_label.config(text="已停止")
    def toggle_recording(self):
        """切换录制状态"""
        if self.recording:
            self.stop_recording()
        else:
            self.start_recording()
    def start_recording(self):
        """开始录制"""
        if self.last_position is None:
            return
        self.recording = True
        self.record_btn.config(text="停止录制")
        self.status_label.config(text="录制中...")
        self.record_listener = mouse.Listener(on_click=self.record_click)
        self.record_listener.daemon = True
        self.record_listener.start()
    def record_click(self, x, y, button, pressed):
        """记录点击事件"""
        if pressed and button == mouse.Button.left:
            try:
                delay = float(self.pos_delay_entry.get())
            except ValueError:
                delay = 1.0
            self.pos_list.insert(tk.END, f"({x:.0f}, {y:.0f}) 延时: {delay}秒")
            return True
    def stop_recording(self):
        """停止录制"""
        self.recording = False
        self.record_btn.config(text="开始录制")
        self.status_label.config(text="就绪")
        if self.record_listener:
            self.record_listener.stop()
        # 删除最后一次记录的坐标
        if self.pos_list.size() > 0:
            self.pos_list.delete(tk.END)
    def edit_position_delay(self, event):
        """编辑位置延时"""
        selection = self.pos_list.curselection()
        if not selection:
            return
        index = selection[0]
        old_text = self.pos_list.get(index)
        current_delay = old_text.split("延时: ")[1].replace("秒", "")
        new_delay = simpledialog.askfloat("编辑延时", "输入新的延时（秒）:",
                                          initialvalue=current_delay,
                                          minvalue=0.1, maxvalue=60)
        if new_delay:
            new_text = old_text.split(" 延时: ")[0] + f" 延时: {new_delay}秒"
            self.pos_list.delete(index)
            self.pos_list.insert(index, new_text)
    def save_task(self):
        """保存任务"""
        task_name = self.task_name_entry.get().strip()
        if not task_name:
            return
        positions = []
        for item in self.pos_list.get(0, tk.END):
            parts = item.split(" 延时: ")
            coords = parts[0][1:-1].split(", ")
            positions.append((
                float(coords[0]),
                float(coords[1]),
                float(parts[1].replace("秒", ""))
            ))
        try:
            task_delay = float(self.task_delay_entry.get())
        except ValueError:
            return
        self.tasks[task_name] = {
            "positions": positions,
            "task_delay": task_delay,
            "loop": self.loop_var.get()
        }
        self.save_settings()
        self.load_task_list()
    def load_task_list(self):
        """加载任务列表"""
        self.task_list.delete(0, tk.END)
        for task in sorted(self.tasks.keys()):
            self.task_list.insert(tk.END, task)
    def set_window_topmost(self, topmost):
        """设置窗口置顶"""
        self.root.wm_attributes("-topmost", topmost)
    def save_settings(self):
        """保存配置到文件"""
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.tasks, f, indent=2)
    def load_settings(self):
        """从文件加载配置"""
        try:
            with open(CONFIG_FILE) as f:
                self.tasks = json.load(f)
                # 转换旧格式坐标数据
                for task in self.tasks.values():
                    if isinstance(task['positions'][0], dict):
                        task['positions'] = [
                            (p['x'], p['y'], p['delay'])
                            for p in task['positions']
                        ]
            self.load_task_list()
        except (FileNotFoundError, json.JSONDecodeError):
            self.tasks = {}
    def update_progress(self, event):
        data = event.data
        self.status_label.config(
            text=f"正在执行 {data['current']}/{data['total']}"
        )
    def delete_task(self):
        """删除选中的任务"""
        selection = self.task_list.curselection()
        if not selection:
            return
        task_name = self.task_list.get(selection[0])
        del self.tasks[task_name]
        self.save_settings()
        self.load_task_list()
    def delete_position(self):
        """删除选中的位置"""
        selection = self.pos_list.curselection()
        if not selection:
            return
        self.pos_list.delete(selection[0])
    def clear_positions(self):
        """清空所有位置"""
        self.pos_list.delete(0, tk.END)
    def load_task(self, event=None):
        """加载选中的任务"""
        selection = self.task_list.curselection()
        if not selection:
            return
        task_name = self.task_list.get(selection[0])
        task = self.tasks[task_name]
        self.pos_list.delete(0, tk.END)
        for x, y, delay in task['positions']:
            self.pos_list.insert(tk.END, f"({x:.0f}, {y:.0f}) 延时: {delay}秒")
        self.task_delay_entry.delete(0, tk.END)
        self.task_delay_entry.insert(0, str(task['task_delay']))
        self.loop_var.set(task['loop'])
        self.current_task = task_name

if __name__ == "__main__":
    root = tk.Tk()
    root.title("AutoClick")
    AutoClicker(root)
    root.mainloop()


