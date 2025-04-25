import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import time
import random
import threading
import uuid
from enum import Enum

# Định nghĩa các trạng thái tiến trình
class ProcessState(Enum):
    READY = "Sẵn sàng"
    RUNNING = "Đang chạy"
    WAITING = "Đang đợi"
    TERMINATED = "Đã kết thúc"

# Định nghĩa các mức độ ưu tiên
class ProcessPriority(Enum):
    HIGH = "Cao"
    MEDIUM = "Trung bình"
    LOW = "Thấp"

# Lớp đại diện cho một tiến trình
class Process:
    def __init__(self, name, priority=ProcessPriority.MEDIUM, burst_time=None):
        self.pid = str(uuid.uuid4())[:8]  # ID ngắn gọn từ UUID
        self.name = name
        self.state = ProcessState.READY
        self.priority = priority
        self.creation_time = time.time()
        self.start_time = None
        self.end_time = None
        self.burst_time = burst_time if burst_time else random.randint(1, 10)
        self.remaining_time = self.burst_time
        self.waiting_reason = None
        
    def start(self):
        if self.state == ProcessState.READY:
            self.state = ProcessState.RUNNING
            if not self.start_time:
                self.start_time = time.time()
            return True
        return False
        
    def wait(self, reason="I/O"):
        if self.state == ProcessState.RUNNING:
            self.state = ProcessState.WAITING
            self.waiting_reason = reason
            return True
        return False
        
    def resume(self):
        if self.state == ProcessState.WAITING:
            self.state = ProcessState.READY
            self.waiting_reason = None
            return True
        return False
        
    def terminate(self):
        if self.state != ProcessState.TERMINATED:
            self.state = ProcessState.TERMINATED
            self.end_time = time.time()
            return True
        return False
        
    def execute(self, time_slice=1):
        """Thực thi tiến trình trong time_slice đơn vị thời gian"""
        if self.state == ProcessState.RUNNING:
            executed = min(time_slice, self.remaining_time)
            self.remaining_time -= executed
            if self.remaining_time <= 0:
                self.terminate()
            return executed
        return 0
        
    def get_priority_value(self):
        """Trả về giá trị số của độ ưu tiên để so sánh"""
        if self.priority == ProcessPriority.HIGH:
            return 1
        elif self.priority == ProcessPriority.MEDIUM:
            return 2
        else:
            return 3

# Lớp quản lý tiến trình
class ProcessManager:
    def __init__(self):
        self.processes = {}  # {pid: Process}
        self.ready_queue = []
        self.running_process = None
        self.waiting_processes = []
        self.terminated_processes = []
        self.scheduler_running = False
        self.scheduler_thread = None
        self.scheduler_lock = threading.Lock()
        self.update_callback = None
        self.time_slice = 1  # Time slice mặc định
        
    def create_process(self, name, priority=ProcessPriority.MEDIUM, burst_time=None):
        """Tạo tiến trình mới và thêm vào hàng đợi ready"""
        process = Process(name, priority, burst_time)
        with self.scheduler_lock:
            self.processes[process.pid] = process
            self.ready_queue.append(process)
            self.ready_queue.sort(key=lambda p: p.get_priority_value())
        
        if self.update_callback:
            self.update_callback()
        return process
    
    def start_scheduler(self):
        """Bắt đầu luồng lập lịch"""
        if not self.scheduler_running:
            self.scheduler_running = True
            self.scheduler_thread = threading.Thread(target=self.scheduler_loop)
            self.scheduler_thread.daemon = True
            self.scheduler_thread.start()
            return True
        return False
    
    def stop_scheduler(self):
        """Dừng luồng lập lịch"""
        if self.scheduler_running:
            self.scheduler_running = False
            if self.scheduler_thread:
                self.scheduler_thread.join(timeout=1)
                self.scheduler_thread = None
            
            # Đưa tiến trình đang chạy về trạng thái Ready nếu có
            with self.scheduler_lock:
                if self.running_process:
                    self.running_process.state = ProcessState.READY
                    self.ready_queue.append(self.running_process)
                    self.running_process = None
            
            if self.update_callback:
                self.update_callback()
                
            return True
        return False
    
    def scheduler_loop(self):
        """Vòng lặp lập lịch tiến trình"""
        while self.scheduler_running:
            with self.scheduler_lock:
                # Chuyển tiến trình từ waiting sang ready nếu đã chờ đủ thời gian
                self.check_waiting_processes()
                
                # Nếu không có tiến trình nào đang chạy, chọn tiến trình từ hàng đợi ready
                if not self.running_process and self.ready_queue:
                    # Lấy tiến trình có độ ưu tiên cao nhất
                    next_process = self.ready_queue.pop(0)
                    next_process.start()
                    self.running_process = next_process
                
                # Thực thi tiến trình đang chạy
                if self.running_process:
                    # Không chuyển tiến trình về Ready ngay lập tức, giữ ở trạng thái Running
                    # để có thể thấy tiến trình đang chạy trong UI
                    self.running_process.execute(self.time_slice)
                    
                    # Cập nhật UI trước khi thay đổi trạng thái
                    if self.update_callback:
                        self.update_callback()
                        
                    # Giữ tiến trình ở trạng thái Running một thời gian
                    time.sleep(0.5)  # Giảm thời gian ngủ để mô phỏng nhanh hơn
                    
                    # Kiểm tra nếu tiến trình đã hoàn thành
                    if self.running_process.state == ProcessState.TERMINATED:
                        self.terminated_processes.append(self.running_process)
                        self.running_process = None
                    elif random.random() < 0.2:  # 20% cơ hội tiến trình cần I/O
                        # Mô phỏng tiến trình cần I/O
                        self.running_process.wait("I/O Operation")
                        self.waiting_processes.append(self.running_process)
                        self.running_process = None
                    else:
                        # Mô phỏng Round Robin: đưa tiến trình đang chạy về cuối hàng đợi
                        self.running_process.state = ProcessState.READY
                        self.ready_queue.append(self.running_process)
                        self.ready_queue.sort(key=lambda p: p.get_priority_value())
                        self.running_process = None
            
            # Cập nhật giao diện
            if self.update_callback:
                self.update_callback()
                
            # Tạm dừng một khoảng thời gian để mô phỏng
            time.sleep(0.5)  # Giảm thời gian ngủ để mô phỏng nhanh hơn
    
    def check_waiting_processes(self):
        """Kiểm tra và chuyển các tiến trình đợi sang trạng thái sẵn sàng"""
        # Mô phỏng ngẫu nhiên việc các tiến trình waiting sẽ quay lại ready
        waiting_to_remove = []
        for process in self.waiting_processes:
            if random.random() < 0.3:  # 30% cơ hội tiến trình sẽ sẵn sàng trở lại
                process.resume()
                self.ready_queue.append(process)
                self.ready_queue.sort(key=lambda p: p.get_priority_value())
                waiting_to_remove.append(process)
                
        for process in waiting_to_remove:
            self.waiting_processes.remove(process)
    
    def set_process_state(self, pid, new_state):
        """Thay đổi trạng thái của một tiến trình theo ID"""
        if pid not in self.processes:
            return False
            
        process = self.processes[pid]
        
        with self.scheduler_lock:
            if new_state == ProcessState.RUNNING:
                if self.running_process and self.running_process != process:
                    # Nếu có tiến trình đang chạy, đưa tiến trình đó về ready
                    self.running_process.state = ProcessState.READY
                    self.ready_queue.append(self.running_process)
                    self.ready_queue.sort(key=lambda p: p.get_priority_value())
                    
                # Xóa tiến trình khỏi các hàng đợi khác nếu có
                if process in self.ready_queue:
                    self.ready_queue.remove(process)
                if process in self.waiting_processes:
                    self.waiting_processes.remove(process)
                    
                process.start()
                self.running_process = process
                
            elif new_state == ProcessState.READY:
                # Đưa tiến trình vào hàng đợi ready
                if process.state == ProcessState.WAITING:
                    process.resume()
                    if process in self.waiting_processes:
                        self.waiting_processes.remove(process)
                        
                if process == self.running_process:
                    self.running_process = None
                    
                if process not in self.ready_queue:
                    process.state = ProcessState.READY  # Đảm bảo trạng thái được cập nhật
                    self.ready_queue.append(process)
                    self.ready_queue.sort(key=lambda p: p.get_priority_value())
                    
            elif new_state == ProcessState.WAITING:
                if process.state == ProcessState.RUNNING:
                    process.wait()
                    if process == self.running_process:
                        self.running_process = None
                elif process.state == ProcessState.READY:
                    if process in self.ready_queue:
                        self.ready_queue.remove(process)
                    process.state = ProcessState.WAITING  # Đảm bảo trạng thái được cập nhật
                    process.waiting_reason = "User Request"
                    
                if process not in self.waiting_processes:
                    self.waiting_processes.append(process)
                    
            elif new_state == ProcessState.TERMINATED:
                process.terminate()
                
                # Xóa tiến trình khỏi tất cả các hàng đợi
                if process == self.running_process:
                    self.running_process = None
                    
                if process in self.ready_queue:
                    self.ready_queue.remove(process)
                    
                if process in self.waiting_processes:
                    self.waiting_processes.remove(process)
                    
                if process not in self.terminated_processes:
                    self.terminated_processes.append(process)
        
        # Cập nhật giao diện
        if self.update_callback:
            self.update_callback()
            
        return True
            
    def get_all_processes(self):
        """Trả về danh sách tất cả các tiến trình"""
        return list(self.processes.values())
        
    def get_process_by_pid(self, pid):
        """Trả về tiến trình theo ID"""
        return self.processes.get(pid)
        
    def get_process_counts(self):
        """Trả về số lượng tiến trình theo từng trạng thái"""
        ready_count = len(self.ready_queue)
        running_count = 1 if self.running_process else 0
        waiting_count = len(self.waiting_processes)
        terminated_count = len(self.terminated_processes)
        
        return {
            "total": len(self.processes),
            "ready": ready_count,
            "running": running_count,
            "waiting": waiting_count,
            "terminated": terminated_count
        }
    
    def set_time_slice(self, time_slice):
        """Thiết lập time slice mới"""
        if time_slice > 0:
            with self.scheduler_lock:
                self.time_slice = time_slice
            return True
        return False
        
    def set_update_callback(self, callback):
        """Đặt hàm callback để cập nhật giao diện"""
        self.update_callback = callback

# Lớp giao diện người dùng
class ProcessManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Hệ thống Quản lý Tiến trình")
        self.root.geometry("900x600")
        self.root.resizable(True, True)
        
        self.process_manager = ProcessManager()
        self.process_manager.set_update_callback(self.update_ui)
        
        self.create_widgets()
        
        # Bộ lập lịch không tự động bắt đầu, người dùng phải nhấn "Bắt đầu scheduler"
        
    def create_widgets(self):
        """Tạo các thành phần giao diện"""
        # Frame chứa các điều khiển
        control_frame = ttk.LabelFrame(self.root, text="Điều khiển")
        control_frame.pack(fill="x", padx=10, pady=5)
        
        # Frame điều khiển scheduler
        scheduler_frame = ttk.Frame(control_frame)
        scheduler_frame.pack(fill="x", padx=5, pady=5)
        
        self.scheduler_status_var = tk.StringVar(value="Scheduler: Dừng")
        ttk.Label(scheduler_frame, textvariable=self.scheduler_status_var).grid(row=0, column=0, padx=5, pady=5)
        
        self.start_scheduler_btn = ttk.Button(scheduler_frame, text="Bắt đầu Scheduler", command=self.start_scheduler)
        self.start_scheduler_btn.grid(row=0, column=1, padx=5, pady=5)
        
        self.stop_scheduler_btn = ttk.Button(scheduler_frame, text="Dừng Scheduler", command=self.stop_scheduler)
        self.stop_scheduler_btn.grid(row=0, column=2, padx=5, pady=5)
        self.stop_scheduler_btn.config(state="disabled")
        
        ttk.Label(scheduler_frame, text="Time Slice:").grid(row=0, column=3, padx=5, pady=5)
        self.time_slice_var = tk.StringVar(value="1")
        time_slice_entry = ttk.Entry(scheduler_frame, textvariable=self.time_slice_var, width=5)
        time_slice_entry.grid(row=0, column=4, padx=5, pady=5)
        
        ttk.Button(scheduler_frame, text="Đặt Time Slice", command=self.set_time_slice).grid(row=0, column=5, padx=5, pady=5)
        
        # Frame tạo tiến trình
        create_frame = ttk.Frame(control_frame)
        create_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Label(create_frame, text="Tên tiến trình:").grid(row=0, column=0, padx=5, pady=5)
        self.process_name_var = tk.StringVar()
        ttk.Entry(create_frame, textvariable=self.process_name_var).grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(create_frame, text="Độ ưu tiên:").grid(row=0, column=2, padx=5, pady=5)
        self.priority_var = tk.StringVar(value=ProcessPriority.MEDIUM.value)
        ttk.Combobox(create_frame, textvariable=self.priority_var, 
                    values=[p.value for p in ProcessPriority], 
                    state="readonly").grid(row=0, column=3, padx=5, pady=5)
        
        ttk.Label(create_frame, text="Thời gian xử lý:").grid(row=0, column=4, padx=5, pady=5)
        self.burst_time_var = tk.StringVar(value="5")
        ttk.Entry(create_frame, textvariable=self.burst_time_var, width=5).grid(row=0, column=5, padx=5, pady=5)
        
        ttk.Button(create_frame, text="Tạo tiến trình", command=self.create_process).grid(row=0, column=6, padx=5, pady=5)
        ttk.Button(create_frame, text="Tạo ngẫu nhiên", command=self.create_random_processes).grid(row=0, column=7, padx=5, pady=5)
        
        # Frame điều khiển tiến trình được chọn
        process_control_frame = ttk.Frame(control_frame)
        process_control_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Label(process_control_frame, text="Thao tác với tiến trình đã chọn:").grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(process_control_frame, text="Chạy", command=lambda: self.change_process_state(ProcessState.RUNNING)).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(process_control_frame, text="Chờ I/O", command=lambda: self.change_process_state(ProcessState.WAITING)).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(process_control_frame, text="Sẵn sàng", command=lambda: self.change_process_state(ProcessState.READY)).grid(row=0, column=3, padx=5, pady=5)
        ttk.Button(process_control_frame, text="Kết thúc", command=lambda: self.change_process_state(ProcessState.TERMINATED)).grid(row=0, column=4, padx=5, pady=5)
        
        # Frame trạng thái hệ thống
        stats_frame = ttk.LabelFrame(self.root, text="Trạng thái hệ thống")
        stats_frame.pack(fill="x", padx=10, pady=5)
        
        self.stats_vars = {
            "total": tk.StringVar(value="Tổng số: 0"),
            "ready": tk.StringVar(value="Sẵn sàng: 0"),
            "running": tk.StringVar(value="Đang chạy: 0"),
            "waiting": tk.StringVar(value="Đang đợi: 0"),
            "terminated": tk.StringVar(value="Đã kết thúc: 0")
        }
        
        stats_inner_frame = ttk.Frame(stats_frame)
        stats_inner_frame.pack(fill="x", padx=5, pady=5)
        
        col = 0
        for key, var in self.stats_vars.items():
            ttk.Label(stats_inner_frame, textvariable=var).grid(row=0, column=col, padx=10, pady=5)
            col += 1
            
        # Notebook để hiển thị các danh sách tiến trình
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill="both", padx=10, pady=5)
        
        # Tạo tab cho tất cả các tiến trình
        all_processes_frame = ttk.Frame(self.notebook)
        self.notebook.add(all_processes_frame, text="Tất cả tiến trình")
        
        # Tạo bảng tiến trình
        self.process_tree = ttk.Treeview(all_processes_frame, columns=("pid", "name", "state", "priority", "burst_time", "remaining_time", "creation_time"), show="headings")
        self.process_tree.heading("pid", text="ID")
        self.process_tree.heading("name", text="Tên tiến trình")
        self.process_tree.heading("state", text="Trạng thái")
        self.process_tree.heading("priority", text="Độ ưu tiên")
        self.process_tree.heading("burst_time", text="Thời gian xử lý")
        self.process_tree.heading("remaining_time", text="Thời gian còn lại")
        self.process_tree.heading("creation_time", text="Thời điểm tạo")
        
        self.process_tree.column("pid", width=80)
        self.process_tree.column("name", width=150)
        self.process_tree.column("state", width=100)
        self.process_tree.column("priority", width=100)
        self.process_tree.column("burst_time", width=100)
        self.process_tree.column("remaining_time", width=100)
        self.process_tree.column("creation_time", width=150)
        
        scrollbar = ttk.Scrollbar(all_processes_frame, orient="vertical", command=self.process_tree.yview)
        self.process_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.process_tree.pack(expand=True, fill="both")
        
        # Tab cho các tiến trình theo trạng thái
        self.ready_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.ready_frame, text="Sẵn sàng")
        
        self.running_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.running_frame, text="Đang chạy")
        
        self.waiting_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.waiting_frame, text="Đang đợi")
        
        self.terminated_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.terminated_frame, text="Đã kết thúc")
        
        # Tạo các bảng cho từng trạng thái
        self.ready_tree = self.create_process_tree(self.ready_frame)
        self.running_tree = self.create_process_tree(self.running_frame)
        self.waiting_tree = self.create_process_tree(self.waiting_frame)
        self.terminated_tree = self.create_process_tree(self.terminated_frame)
        
        # Thanh trạng thái
        self.status_var = tk.StringVar(value="Hệ thống đang chạy...")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Cập nhật giao diện
        self.update_ui()
        
    def create_process_tree(self, parent):
        """Tạo bảng tiến trình cho từng tab"""
        tree = ttk.Treeview(parent, columns=("pid", "name", "state", "priority", "burst_time", "remaining_time", "creation_time"), show="headings")
        tree.heading("pid", text="ID")
        tree.heading("name", text="Tên tiến trình")
        tree.heading("state", text="Trạng thái")
        tree.heading("priority", text="Độ ưu tiên")
        tree.heading("burst_time", text="Thời gian xử lý")
        tree.heading("remaining_time", text="Thời gian còn lại")
        tree.heading("creation_time", text="Thời điểm tạo")
        
        tree.column("pid", width=80)
        tree.column("name", width=150)
        tree.column("state", width=100)
        tree.column("priority", width=100)
        tree.column("burst_time", width=100)
        tree.column("remaining_time", width=100)
        tree.column("creation_time", width=150)
        
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        tree.pack(expand=True, fill="both")
        
        tree.bind("<ButtonRelease-1>", self.on_tree_select)
        
        return tree
    
    def on_tree_select(self, event):
        """Xử lý khi chọn một tiến trình trong bất kỳ tab nào"""
        tree = event.widget
        selection = tree.selection()
        if selection:
            item = selection[0]
            values = tree.item(item, "values")
            pid = values[0]
            
            # Chọn tiến trình tương ứng trong tab tất cả tiến trình
            for item in self.process_tree.get_children():
                if self.process_tree.item(item, "values")[0] == pid:
                    self.process_tree.selection_set(item)
                    self.process_tree.focus(item)
                    self.process_tree.see(item)
                    break
    
    def start_scheduler(self):
        """Bắt đầu bộ lập lịch"""
        if self.process_manager.start_scheduler():
            self.scheduler_status_var.set("Scheduler: Đang chạy")
            self.start_scheduler_btn.config(state="disabled")
            self.stop_scheduler_btn.config(state="normal")
            self.status_var.set("Đã bắt đầu bộ lập lịch tiến trình")
    
    def stop_scheduler(self):
        """Dừng bộ lập lịch"""
        if self.process_manager.stop_scheduler():
            self.scheduler_status_var.set("Scheduler: Dừng")
            self.start_scheduler_btn.config(state="normal")
            self.stop_scheduler_btn.config(state="disabled")
            self.status_var.set("Đã dừng bộ lập lịch tiến trình")
    
    def set_time_slice(self):
        """Thiết lập time slice mới"""
        try:
            time_slice = int(self.time_slice_var.get())
            if time_slice <= 0:
                messagebox.showerror("Lỗi", "Time slice phải là số dương!")
                return
                
            if self.process_manager.set_time_slice(time_slice):
                self.status_var.set(f"Đã đặt time slice = {time_slice}")
        except ValueError:
            messagebox.showerror("Lỗi", "Time slice phải là số nguyên!")
        
    def create_process(self):
        """Xử lý sự kiện tạo tiến trình mới"""
        name = self.process_name_var.get().strip()
        if not name:
            messagebox.showerror("Lỗi", "Vui lòng nhập tên tiến trình!")
            return
            
        try:
            burst_time = int(self.burst_time_var.get().strip())
            if burst_time <= 0:
                messagebox.showerror("Lỗi", "Thời gian xử lý phải là số dương!")
                return
        except ValueError:
            messagebox.showerror("Lỗi", "Thời gian xử lý phải là số nguyên!")
            return
        
        priority_str = self.priority_var.get()
        priority = next((p for p in ProcessPriority if p.value == priority_str), ProcessPriority.MEDIUM)
        
        self.process_manager.create_process(name, priority, burst_time)
        self.process_name_var.set("")
        self.burst_time_var.set("5")
        self.update_ui()
        
    def create_random_processes(self):
        """Tạo nhiều tiến trình ngẫu nhiên"""
        count = simpledialog.askinteger("Tạo tiến trình", "Số lượng tiến trình muốn tạo:", initialvalue=5, minvalue=1, maxvalue=20)
        if count is None:
            return
            
        process_names = [
            "Chrome", "Firefox", "Word", "Excel", "Photoshop", 
            "Notepad", "Calculator", "Explorer", "VSCode", "Spotify",
            "Discord", "Steam", "Skype", "Outlook", "OneDrive",
            "Teams", "Zoom", "Slack", "WhatsApp", "Telegram"
        ]
        
        for _ in range(count):
            name = random.choice(process_names) + f"-{random.randint(100, 999)}"
            priority = random.choice(list(ProcessPriority))
            burst_time = random.randint(3, 15)
            self.process_manager.create_process(name, priority, burst_time)
        
        self.update_ui()
        
    def change_process_state(self, new_state):
        """Thay đổi trạng thái của tiến trình được chọn"""
        selection = self.process_tree.selection()
        if not selection:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn một tiến trình!")
            return
            
        item = selection[0]
        pid = self.process_tree.item(item, "values")[0]
        
        if self.process_manager.set_process_state(pid, new_state):
            self.update_ui()
        else:
            messagebox.showerror("Lỗi", f"Không thể chuyển tiến trình sang trạng thái {new_state.value}!")
            
    def update_ui(self):
        """Cập nhật giao diện người dùng"""
        # Cập nhật thống kê
        counts = self.process_manager.get_process_counts()
        self.stats_vars["total"].set(f"Tổng số: {counts['total']}")
        self.stats_vars["ready"].set(f"Sẵn sàng: {counts['ready']}")
        self.stats_vars["running"].set(f"Đang chạy: {counts['running']}")
        self.stats_vars["waiting"].set(f"Đang đợi: {counts['waiting']}")
        self.stats_vars["terminated"].set(f"Đã kết thúc: {counts['terminated']}")
        
        # Cập nhật danh sách tiến trình
        self.update_process_tree(self.process_tree, self.process_manager.get_all_processes())
        
        # Cập nhật danh sách theo trạng thái
        self.update_process_tree(self.ready_tree, 
                               [p for p in self.process_manager.get_all_processes() if p.state == ProcessState.READY])
        self.update_process_tree(self.running_tree, 
                               [p for p in self.process_manager.get_all_processes() if p.state == ProcessState.RUNNING])
        self.update_process_tree(self.waiting_tree, 
                               [p for p in self.process_manager.get_all_processes() if p.state == ProcessState.WAITING])
        self.update_process_tree(self.terminated_tree, 
                               [p for p in self.process_manager.get_all_processes() if p.state == ProcessState.TERMINATED])
        
        # Cập nhật tiêu đề các tab
        self.notebook.tab(1, text=f"Sẵn sàng ({counts['ready']})")
        self.notebook.tab(2, text=f"Đang chạy ({counts['running']})")
        self.notebook.tab(3, text=f"Đang đợi ({counts['waiting']})")
        self.notebook.tab(4, text=f"Đã kết thúc ({counts['terminated']})")
        
        # Cập nhật thanh trạng thái
        current_time = time.strftime("%H:%M:%S")
        scheduler_status = "Đang chạy" if self.process_manager.scheduler_running else "Dừng"
        self.status_var.set(f"Cập nhật lúc: {current_time} | Scheduler: {scheduler_status} | Tổng số tiến trình: {counts['total']}")
        
    def update_process_tree(self, tree, processes):
        """Cập nhật nội dung của một bảng tiến trình"""
        # Lưu các mục đã chọn
        selected_items = []
        for item in tree.selection():
            selected_items.append(tree.item(item, "values")[0])
        
        # Xóa tất cả các mục cũ
        for item in tree.get_children():
            tree.delete(item)
            
        # Thêm các tiến trình mới
        for process in processes:
            creation_time = time.strftime("%H:%M:%S", time.localtime(process.creation_time))
            
            # Đặt màu cho các trạng thái khác nhau
            tag = process.state.name.lower()
            
            item_id = tree.insert("", "end", values=(
                process.pid,
                process.name,
                process.state.value,
                process.priority.value,
                process.burst_time,
                process.remaining_time,
                creation_time
            ), tags=(tag,))
            
            # Khôi phục lựa chọn
            if process.pid in selected_items:
                tree.selection_add(item_id)
            
        # Đặt màu cho các trạng thái
        tree.tag_configure('ready', background='lightblue')
        tree.tag_configure('running', background='lightgreen')
        tree.tag_configure('waiting', background='lightyellow')
        tree.tag_configure('terminated', background='lightgray')
        
    def on_closing(self):
        """Xử lý khi đóng ứng dụng"""
        if messagebox.askokcancel("Thoát", "Bạn có muốn thoát không?"):
            self.process_manager.stop_scheduler()
            self.root.destroy()

# Hàm main để chạy ứng dụng
def main():
    root = tk.Tk()
    app = ProcessManagerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()